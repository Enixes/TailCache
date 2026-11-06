#!/usr/bin/env python3
"""Bounded compiler attribution with ordinary channels plus explicit HotSpot event logs.

Never calibration/pilot/primary evidence. Logging may change compilation behavior.
"""
import argparse
import csv
import json
import os
import pathlib
import re
import subprocess
import threading
import time
from types import SimpleNamespace

import tailcache12 as evidence
import tailcache12_calibrate as calibration
import tailcache12_native_retry as retry
from tailcache12_quiet import run_preflight
from tailcache12_study_analysis import every_operation_fork_summary, jmh_fork_summary
from tailcache12_jit_diagnose import classify_tasks

TRACE="3310547f9e5d01436fb54781f8cb50f312c8b3d29079f719694026e43107dfb3"
EVENT=re.compile(r"^\[(\d+)ns\]\[(\d+)ns\]\[debug\]\[jit,compilation\]\s+(.*)$")
TASKS={'every-operation':'tailCache12EveryOperation','sample-calibration':'tailCache12SampleCalibration',
       'floor':'tailCache12SupplyFloor'}


def validate_logging_channels(channels,attach_logs,xml):
    if (not channels or len(set(channels))!=len(channels) or any(c not in TASKS for c in channels)):
        raise ValueError('Unknown or duplicate diagnostic channels')
    if attach_logs and (xml or len(channels)!=1 or channels[0]=='every-operation'):
        raise ValueError('Attached logging requires exactly one JMH channel and no startup XML')
    if xml and (len(channels)!=1 or channels[0]=='every-operation'):
        raise ValueError('Targeted XML requires exactly one JMH channel')


def parse_events(path):
    events=[]
    for number,line in enumerate(path.read_text().splitlines(),1):
        match=EVENT.fullmatch(line)
        if not match:
            raise ValueError("Unknown HotSpot compilation-event format")
        timestamp,uptime,text=match.groups()
        if int(timestamp)<=0 or int(uptime)<0 or "::" not in text:
            raise ValueError("Invalid HotSpot event clock or method evidence")
        events.append(dict(line=number,timestampNs=int(timestamp),uptimeNs=int(uptime),detail=text,
                           kind="invalidation" if "made not entrant" in text or "made zombie" in text else
                                "native-wrapper-event" if "(native)" in text else "compiler-task-start"))
    if not events: raise ValueError("Missing HotSpot compilation events")
    return events


def worker_xml(control,pid):
    # HotSpot's legacy LogFile %p expands to pidNNN; unified -Xlog uses NNN.
    files=[p for p in (control/f"hotspot-compile-pid{pid}.xml",control/f"hotspot-compile-{pid}.xml") if p.exists()]
    if len(files)!=1: raise ValueError("Missing or ambiguous actual-worker XML artifact")
    return files[0]


def worker_identity(pid):
    path=pathlib.Path('/proc')/str(pid)
    if b'org.openjdk.jmh.runner.ForkedMain' not in (path/'cmdline').read_bytes():
        raise ValueError('Attachment target is not the actual JMH fork')
    group=(path/'cgroup').read_text().strip()
    expected=os.environ.get('TAILCACHE_NATIVE_SCOPE','')
    if not expected or group!='0::'+group.partition('0::')[2] or not group.endswith('/'+expected):
        raise ValueError('Attachment target escaped the declared native scope')
    return dict(pid=pid,startTicks=(path/'stat').read_text().rsplit(')',1)[1].split()[19],cgroup=group)


def attach_worker_logging(raw,control,stop,result,delay=20,marker_timeout=60):
    """A bounded setup helper; target arguments/measurement code remain unchanged."""
    record=dict(method='jcmd-VM.log-v1',success=False)
    try:
        deadline=time.monotonic()+marker_timeout
        markers=[]
        while time.monotonic()<deadline and not stop.is_set():
            markers=list(raw.rglob('worker-process-*.properties'))
            if len(markers)>1: raise ValueError('Ambiguous actual worker marker')
            if markers: break
            stop.wait(.2)
        if len(markers)!=1: raise ValueError('No actual worker marker before attachment deadline')
        metadata=dict(line.split('=',1) for line in markers[0].read_text().splitlines() if '=' in line)
        pid=int(metadata['pid'])
        if markers[0].name!=f'worker-process-{pid}.properties': raise ValueError('Worker PID marker mismatch')
        identity=worker_identity(pid)
        if stop.wait(delay): raise ValueError('Diagnostic exited before attachment')
        if worker_identity(pid)!=identity: raise ValueError('Attachment target PID identity changed')
        log=control/f'hotspot-jit-{pid}.log'
        if log.exists(): raise ValueError('Refusing to overwrite diagnostic log')
        command=[str(pathlib.Path(os.environ['JAVA_HOME'])/'bin/jcmd'),str(pid),'VM.log',
                 'output='+str(log),'what=jit+compilation=debug',
                 'decorators=timenanos,uptimenanos,level,tags']
        record.update(identity=identity,pid=pid,command=command,startNs=time.monotonic_ns())
        completed=subprocess.run(command,text=True,capture_output=True,timeout=30)
        record.update(endNs=time.monotonic_ns(),exitCode=completed.returncode,
                      stdout=completed.stdout,stderr=completed.stderr)
        if completed.returncode or worker_identity(pid)!=identity or not log.exists():
            raise ValueError('Attachment failed or target identity/log changed')
        record['success']=True
    except Exception as error:
        record['error']=f'{type(error).__name__}: {error}'
    finally:
        control.mkdir(parents=True,exist_ok=True)
        evidence.save(control/'attachment.json',record)
        result.update(record)


def verify_attachment(control,pid,windows):
    record=__import__('json').loads((control/'attachment.json').read_text())
    if (record.get('method')!='jcmd-VM.log-v1' or record.get('success') is not True
            or record.get('pid')!=int(pid) or record.get('exitCode')!=0
            or not 0<record['startNs']<=record['endNs']<=min(a for a,b in windows)-60*10**9):
        raise ValueError('Missing, failed or late diagnostic attachment')
    return record


def verify_artifacts(control,artifacts):
    if any(pathlib.Path(name).name!=name or calibration.sha(control/name)!=digest
           for name,digest in artifacts.items()):
        raise ValueError('Changed retained diagnostic attachment/log artifacts')


def grid(repeats=4,payloads=(256,4096),channels=("every-operation","sample-calibration"),
         backend="CAFFEINE",live_bytes=0,conditioning=0,transport_warmup=False,maintenance_warmup=False):
    result=[]
    for repeat in range(1,repeats+1):
        for payload in (payloads if repeat%2 else tuple(reversed(payloads))):
            for channel in (channels if repeat%2 else tuple(reversed(channels))):
                props=dict(Backend=backend,Payload=payload,Residents=32768,HeapMiB=512,LiveBytes=live_bytes,
                    ChurnBytesPerSecond=32*1024**2,Seed=24301,Warmups=120,Measurements=8,Channel=channel)
                if channel=="every-operation": props["CompilerDiagnostics"]="false"
                else: props.update(Backends=backend,Payloads=payload,Forks=1)
                result.append((f"r{repeat}-{channel}-p{payload}",props))
    inputs={}
    if conditioning: inputs["conditioning"]=conditioning
    if transport_warmup: inputs["transportWarmupVersion"]=evidence.TRANSPORT_WARMUP_VERSION
    if maintenance_warmup: inputs['lifecycleWarmupVersion']=evidence.LIFECYCLE_WARMUP_VERSION
    return calibration.preparation_controls(result,inputs)


def analyze(attempt,manifest,invocation):
    raw=calibration.verify_invocation(attempt,invocation)
    props=invocation["properties"]
    channel=props["Channel"]
    if channel=="every-operation":
        summary=every_operation_fork_summary(raw/channel,props,TRACE)
    else:
        record=json.loads((raw/channel/"results.json").read_text())[0]
        runtime={k:record[k] for k in ("jmhVersion","jdkVersion","vmName","vmVersion")}
        summary=jmh_fork_summary(raw,channel,dict(props,ConsoleFile=str(attempt/invocation["label"]/"gradle.log")),TRACE,runtime,
                                diagnostic_compiler_xml=manifest.get("diagnosticCompilerXml",False))
    with (attempt/invocation["label"]/"host.csv").open(newline="") as stream:
        host=[evidence.decode_host_row(r) for r in csv.DictReader(stream)]
    reasons,_=evidence.replay_host_gate(manifest,raw,host)
    reasons+=invocation.get("hostMonitorErrors",[])
    markers=list(raw.rglob("worker-process-*.properties"))
    if len(markers)!=1: raise ValueError("Expected one actual worker PID")
    metadata=dict(line.split("=",1) for line in markers[0].read_text().splitlines() if "=" in line)
    events=parse_events(attempt/invocation["label"]/f"hotspot-jit-{metadata['pid']}.log")
    windows=evidence.measurement_windows(raw)
    if manifest.get('attachmentLogging'):
        verify_attachment(attempt/invocation['label'],metadata['pid'],windows)
    artifacts=manifest.get('diagnosticArtifacts',{}).get(invocation['label'])
    if manifest.get('attachmentLogging') and (not artifacts or set(artifacts)!=
            {'attachment.json',f"hotspot-jit-{metadata['pid']}.log"}):
        raise ValueError('Missing declared attachment artifacts')
    if artifacts: verify_artifacts(attempt/invocation['label'],artifacts)
    if len(windows)!=len(summary["compilerPerIterationMs"]):
        raise ValueError("Compiler counter/window counts disagree")
    aligned=[]
    for index,((start,end),counter) in enumerate(zip(windows,summary["compilerPerIterationMs"]),1):
        inside=[e for e in events if start<=e["timestampNs"]<=end]
        near=[e for e in events if start-5_000_000<=e["timestampNs"]<=end+5_000_000 and e not in inside]
        aligned.append(dict(iteration=index,compilerMs=counter,startNs=start,endNs=end,inside=inside,near=near))
    result=dict(label=invocation["label"],inputs=props,hostPass=not reasons,
        rejectionReasons=summary["rejectionReasons"]+reasons,
        compilerViolation=any("compiler" in reason for reason in summary["rejectionReasons"]),
        compilerPerIterationMs=summary["compilerPerIterationMs"],alignedEvents=aligned,
        workerPid=int(metadata["pid"]),eventCount=len(events),primaryEndpointUseAllowed=False)
    if manifest.get("diagnosticCompilerXml"):
        xml=worker_xml(attempt/invocation["label"],metadata['pid'])
        logs=list((attempt/invocation['label']).glob('diagnostic-gc-*.log')) if channel=='floor' else list((raw/channel).glob("gc-*.log"))
        if not xml.exists() or len(logs)!=1: raise ValueError("Missing targeted XML/GC evidence")
        detail=classify_tasks(xml,logs[0],windows)
        result["xmlAttribution"]=dict(
            tasksOverlappingWorker=[t for t in detail["tasks"] if t["location"]=="possible-worker-overlap"],
            guardTasks=[t for t in detail["tasks"] if "VarHandleGuards guard_LI_V" in t["method"]],
            deoptimizationEvents=detail["deoptimizationEvents"],workerWindowsSeconds=detail["workerWindowsSeconds"],
            alignmentUncertaintyMs=detail["alignmentUncertaintyMs"])
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt_id")
    parser.add_argument("--xml",action="store_true")
    parser.add_argument("--repeats",type=int,choices=range(1,17),default=4)
    parser.add_argument('--attach-logs',action='store_true')
    parser.add_argument("--payloads",type=int,nargs="+",choices=(256,4096),default=[256,4096])
    parser.add_argument("--channels",nargs="+",choices=tuple(TASKS),default=["every-operation","sample-calibration"])
    parser.add_argument("--backend",choices=evidence.BACKENDS,default="CAFFEINE")
    parser.add_argument("--live-mib",type=int,choices=(0,96,208,288),default=0)
    parser.add_argument("--conditioning",type=int,choices=range(0,65),default=0)
    parser.add_argument("--transport-warmup",action="store_true")
    parser.add_argument('--maintenance-warmup',action='store_true')
    args=parser.parse_args()
    try: validate_logging_channels(args.channels,args.attach_logs,args.xml)
    except ValueError as error: parser.error(str(error))
    if len(set(args.payloads))!=len(args.payloads) or len(set(args.channels))!=len(args.channels):
        parser.error("Duplicate diagnostic conditions")
    if not re.fullmatch(r"[A-Za-z0-9._-]+",args.attempt_id): parser.error("Invalid attempt ID")
    attempt=evidence.REPORTS/args.attempt_id
    quiet=evidence.REPORTS/(args.attempt_id+"-quiet")
    if attempt.exists() or quiet.exists(): raise ValueError("Diagnostic exists; no duplicate/overwrite allowed")
    if any(key in os.environ for key in ("JAVA_TOOL_OPTIONS","JDK_JAVA_OPTIONS","_JAVA_OPTIONS")):
        raise ValueError("Diagnostic requires a clean JVM-option environment")
    source=evidence.source_hash()
    if not run_preflight(quiet,120,300)["quietPass"]: raise ValueError("Diagnostic quiet preparation failed")
    policy=retry.declare_policy(2)
    initial=retry.initial_quiet_reference(quiet,dict(sourceSha256=source),policy,evidence.host_snapshot())
    options=SimpleNamespace(stage="jit-event-attribution",heap_mib=512,residents=32768,churn_mib=32,
        live_mib=[args.live_mib],payloads=args.payloads,seed=24301,warmups=120,measurements=8,repeats=args.repeats,
        channels=args.channels,resume=False,conditioning=args.conditioning,transport_warmup=args.transport_warmup,
        maintenance_warmup=args.maintenance_warmup)
    plan=grid(args.repeats,args.payloads,args.channels,args.backend,args.live_mib*1024**2,
              args.conditioning,args.transport_warmup,args.maintenance_warmup)
    manifest=calibration.prepare(attempt,options,plan)
    manifest.update(initialQuietRef=initial,diagnosticOnly=True,primaryEndpointUseAllowed=False,
        maxFreshJvms=len(plan),nearEventMarginNs=5_000_000,diagnosticCompilerXml=args.xml,
        schedule=[dict(label=k,properties=v) for k,v in plan],diagnosticJvmOptions={},
        attachmentLogging=args.attach_logs,diagnosticArtifacts={})
    evidence.save(attempt/"manifest.json",manifest)
    rows=[]
    try:
        for label,props in plan:
            # The first block cannot outlive preparation even if archive/build work stalls.
            if not rows:
                retry.verify_initial_quiet(attempt,dict(manifest,nativeHostRetryPolicy=policy,
                    nativeEnvironmentDeclaration=evidence.native_host.environment_declaration(evidence.host_snapshot())),before_launch=True)
            option=f"-Xlog:jit+compilation=debug:file={attempt/label}/hotspot-jit-%p.log:timenanos,uptimenanos,level,tags"
            if args.xml:
                option+=f" -XX:+UnlockDiagnosticVMOptions -XX:+LogCompilation -XX:LogFile={attempt/label}/hotspot-compile-%p.xml"
                if props['Channel']=='floor':
                    option+=f" -Xlog:gc*,safepoint:file={attempt/label}/diagnostic-gc-%p.log:uptimemillis,timenanos,level,tags:filecount=0"
            manifest["diagnosticJvmOptions"][label]='none; jcmd attachment only' if args.attach_logs else option
            evidence.save(attempt/"manifest.json",manifest)
            attachment=None
            if args.attach_logs:
                stop=threading.Event(); attachment={}
                helper=threading.Thread(target=attach_worker_logging,
                    args=(attempt.parent/(attempt.name+'-'+label),attempt/label,stop,attachment),daemon=True)
                helper.start()
            else:
                os.environ["JAVA_TOOL_OPTIONS"]=option
            try:
                evidence.invoke(attempt,manifest,label,TASKS[props['Channel']],props)
            finally:
                if args.attach_logs:
                    stop.set(); helper.join(35)
                    if helper.is_alive(): raise ValueError('Attachment helper failed to terminate')
                else: del os.environ["JAVA_TOOL_OPTIONS"]
            if args.attach_logs:
                if not attachment.get('success'): raise ValueError('Diagnostic attachment failed: '+attachment.get('error','unknown'))
                files=['attachment.json',f"hotspot-jit-{attachment['pid']}.log"]
                manifest['diagnosticArtifacts'][label]={name:calibration.sha(attempt/label/name) for name in files}
                manifest['diagnosticJvmOptions'][label]='none; jcmd attachment only'
                evidence.save(attempt/'manifest.json',manifest)
            elif args.xml:
                files=[p for p in (attempt/label).iterdir()
                       if p.name.startswith(('hotspot-jit-','hotspot-compile-','diagnostic-gc-'))]
                manifest['diagnosticArtifacts'][label]={p.name:calibration.sha(p) for p in files}
                evidence.save(attempt/'manifest.json',manifest)
            row=analyze(attempt,manifest,manifest["invocations"][-1])
            rows.append(row)
            result=dict(diagnosticOnly=True,primaryEndpointUseAllowed=False,observations=rows,
                completedJvms=len(rows),maximumJvms=len(plan),compilerViolationObserved=any(r["compilerViolation"] for r in rows),
                stoppedOnQualityFailure=bool(row["rejectionReasons"]),
                eventInterpretationVersion=2,
                limits=["Regular bytecode events mark compiler task start; native-wrapper/invalidation events are separate. No event is compiler CPU duration or worker pause time.",
                        "Logging can change compilation behavior; non-reproduction is inconclusive."])
            evidence.save(attempt/"attribution.json",result)
            print(f"attribution {label}: compiler={row['compilerPerIterationMs']} reasons={row['rejectionReasons']}",flush=True)
            if row["rejectionReasons"]: break
    except Exception as error:
        manifest["terminalDriverFailure"]=dict(reason=f"{type(error).__name__}: {error}")
        evidence.save(attempt/"manifest.json",manifest)
        raise
    return 0


if __name__=="__main__": raise SystemExit(main())
