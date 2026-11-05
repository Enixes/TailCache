#!/usr/bin/env python3
"""Bounded compiler attribution with ordinary channels plus explicit HotSpot event logs.

Never calibration/pilot/primary evidence. Logging may change compilation behavior.
"""
import argparse
import csv
import json
import os
import re
from types import SimpleNamespace

import tailcache12 as evidence
import tailcache12_calibrate as calibration
import tailcache12_native_retry as retry
from tailcache12_quiet import run_preflight
from tailcache12_study_analysis import every_operation_fork_summary, jmh_fork_summary

TRACE="3310547f9e5d01436fb54781f8cb50f312c8b3d29079f719694026e43107dfb3"
EVENT=re.compile(r"^\[(\d+)ns\]\[(\d+)ns\]\[debug\]\[jit,compilation\]\s+(.*)$")


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
                           kind="invalidation" if "made not entrant" in text or "made zombie" in text else "compilation-completion"))
    if not events: raise ValueError("Missing HotSpot compilation events")
    return events


def grid():
    result=[]
    for repeat in range(1,5):
        for payload in ((256,4096) if repeat%2 else (4096,256)):
            for channel in (("every-operation","sample-calibration") if repeat%2 else ("sample-calibration","every-operation")):
                props=dict(Backend="CAFFEINE",Payload=payload,Residents=32768,HeapMiB=512,LiveBytes=0,
                    ChurnBytesPerSecond=32*1024**2,Seed=24301,Warmups=120,Measurements=8,Channel=channel)
                if channel=="every-operation": props["CompilerDiagnostics"]="false"
                else: props.update(Backends="CAFFEINE",Payloads=payload,Forks=1)
                result.append((f"r{repeat}-{channel}-p{payload}",props))
    return result


def analyze(attempt,manifest,invocation):
    raw=calibration.verify_invocation(attempt,invocation)
    props=invocation["properties"]
    channel=props["Channel"]
    if channel=="every-operation":
        summary=every_operation_fork_summary(raw/channel,props,TRACE)
    else:
        record=json.loads((raw/channel/"results.json").read_text())[0]
        runtime={k:record[k] for k in ("jmhVersion","jdkVersion","vmName","vmVersion")}
        summary=jmh_fork_summary(raw,channel,dict(props,ConsoleFile=str(attempt/invocation["label"]/"gradle.log")),TRACE,runtime)
    with (attempt/invocation["label"]/"host.csv").open(newline="") as stream:
        host=[evidence.decode_host_row(r) for r in csv.DictReader(stream)]
    reasons,_=evidence.replay_host_gate(manifest,raw,host)
    reasons+=invocation.get("hostMonitorErrors",[])
    markers=list(raw.rglob("worker-process-*.properties"))
    if len(markers)!=1: raise ValueError("Expected one actual worker PID")
    metadata=dict(line.split("=",1) for line in markers[0].read_text().splitlines() if "=" in line)
    events=parse_events(attempt/invocation["label"]/f"hotspot-jit-{metadata['pid']}.log")
    windows=evidence.measurement_windows(raw)
    if len(windows)!=len(summary["compilerPerIterationMs"]):
        raise ValueError("Compiler counter/window counts disagree")
    aligned=[]
    for index,((start,end),counter) in enumerate(zip(windows,summary["compilerPerIterationMs"]),1):
        inside=[e for e in events if start<=e["timestampNs"]<=end]
        near=[e for e in events if start-5_000_000<=e["timestampNs"]<=end+5_000_000 and e not in inside]
        aligned.append(dict(iteration=index,compilerMs=counter,startNs=start,endNs=end,inside=inside,near=near))
    return dict(label=invocation["label"],inputs=props,hostPass=not reasons,
        rejectionReasons=summary["rejectionReasons"]+reasons,
        compilerViolation=any("compiler" in reason for reason in summary["rejectionReasons"]),
        compilerPerIterationMs=summary["compilerPerIterationMs"],alignedEvents=aligned,
        workerPid=int(metadata["pid"]),eventCount=len(events),primaryEndpointUseAllowed=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt_id")
    args=parser.parse_args()
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
        live_mib=[0],payloads=[256,4096],seed=24301,warmups=120,measurements=8,repeats=4,
        channels=["every-operation","sample-calibration"],resume=False)
    plan=grid()
    manifest=calibration.prepare(attempt,options,plan)
    manifest.update(initialQuietRef=initial,diagnosticOnly=True,primaryEndpointUseAllowed=False,
        maxFreshJvms=16,nearEventMarginNs=5_000_000,
        schedule=[dict(label=k,properties=v) for k,v in plan],diagnosticJvmOptions={})
    evidence.save(attempt/"manifest.json",manifest)
    rows=[]
    try:
        for label,props in plan:
            # The first block cannot outlive preparation even if archive/build work stalls.
            if not rows:
                retry.verify_initial_quiet(attempt,dict(manifest,nativeHostRetryPolicy=policy,
                    nativeEnvironmentDeclaration=evidence.native_host.environment_declaration(evidence.host_snapshot())),before_launch=True)
            option=f"-Xlog:jit+compilation=debug:file={attempt/label}/hotspot-jit-%p.log:timenanos,uptimenanos,level,tags"
            manifest["diagnosticJvmOptions"][label]=option
            evidence.save(attempt/"manifest.json",manifest)
            os.environ["JAVA_TOOL_OPTIONS"]=option
            try:
                evidence.invoke(attempt,manifest,label,"tailCache12EveryOperation" if props["Channel"]=="every-operation"
                                else "tailCache12SampleCalibration",props)
            finally:
                del os.environ["JAVA_TOOL_OPTIONS"]
            row=analyze(attempt,manifest,manifest["invocations"][-1])
            rows.append(row)
            result=dict(diagnosticOnly=True,primaryEndpointUseAllowed=False,observations=rows,
                completedJvms=len(rows),maximumJvms=16,compilerViolationObserved=any(r["compilerViolation"] for r in rows),
                stoppedOnQualityFailure=bool(row["rejectionReasons"]),
                limits=["Events are compilation completion/invalidation timestamps, not compiler CPU duration or worker pause time.",
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
