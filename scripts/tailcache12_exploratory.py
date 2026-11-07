#!/usr/bin/env python3
"""Explicit exploratory matrix; warning-bearing data cannot qualify a primary campaign."""
import argparse
import csv
import json
import math
import os
import pathlib
import re
import shutil
import statistics
import subprocess
import tarfile
from types import SimpleNamespace

import tailcache12 as evidence
import tailcache12_calibrate as calibration
import tailcache12_native_retry as native_retry
from tailcache12_calibration_start import AVAILABLE_MEMORY_RULE,prepare_file_cache
from tailcache12_observer import floor_grid,RULES as FLOOR_RULES
from tailcache12_provenance import measurement_source_hash,archive_measurement_source_hash
from tailcache12_quiet import run_preflight
from tailcache12_study_analysis import every_operation_fork_summary,jmh_fork_summary,validate_lifecycle_preparation
from tailcache12_analysis import compiler_rejection_reasons,histogram,quantile,validate_windows

VERSION='tailcache12-exploratory-e2e-v1'
WARNINGS=('compiler total exceeds 80 ms','compiler iteration exceeds 10 ms',
    'fewer than 100000 retained observations for p99.9','missing measured post-GC occupancy',
    'missing old/humongous-region evidence','Native CPU outside benchmark scope exceeded 10% upper bound',
    'Native observer median read duration exceeded 10 ms')
POLICY=dict(version=VERSION,warningReasons=list(WARNINGS),outsideCpuUpperCeilingPercent=25,
    warmups=30,conditioning=8,measurements=8,workloadReplicas=1,floorReplicas=2,replacements=0,
    quietSeconds=120,quietTimeoutSeconds=300,maxQuietToFirstBlockSeconds=360,
    initialMemoryReadinessRule=AVAILABLE_MEMORY_RULE,primaryEndpointUseAllowed=False,
    uncertainty='unavailable-single-workload-fork',robustness='not-collected')
LIMITS=['Exploratory observations only; no confirmatory crossover or no-crossover claim.',
    'One workload fork per cell/channel: run-to-run variance and confidence intervals are unavailable.',
    'Thirty warmups may leave compilation activity; all original strict reasons remain visible.',
    'Sampled and full observation modes may induce different load/backend ordering.',
    'Occupancy is observed, not source-matched calibrated; no robustness-seed evidence.',
    'Single worker, periodic uniform95/5 trace, fixed512MiB G1 and in-memory Chronicle only.',
    'No outlier trimming, histogram pooling, historical fork reuse or floor subtraction.']


def schedule():
    rows=floor_grid(30,8,evidence.TRANSPORT_WARMUP_VERSION,evidence.LIFECYCLE_WARMUP_VERSION)
    for i,live in enumerate((0,96,208,288)):
        for j,payload in enumerate((256,4096)):
            backends=evidence.BACKENDS if (i+j)%2==0 else tuple(reversed(evidence.BACKENDS))
            for k,backend in enumerate(backends):
                channels=('sample-calibration','every-operation')
                if (i+j+k)%2:channels=tuple(reversed(channels))
                for channel in channels:
                    p=dict(Backend=backend,Payload=payload,Residents=32768,HeapMiB=512,LiveBytes=live*1024**2,
                        ChurnBytesPerSecond=33554432,Seed=24301,Warmups=30,Conditioning=8,Measurements=8,
                        Channel=channel,TransportWarmupVersion=evidence.TRANSPORT_WARMUP_VERSION,
                        LifecycleWarmupVersion=evidence.LIFECYCLE_WARMUP_VERSION)
                    rows.append((f'work-{channel}-{backend}-p{payload}-live{live}',calibration.command_properties(p)))
    return rows


def classify(reasons,cpu_upper=0):
    if not math.isfinite(cpu_upper) or cpu_upper<0:raise ValueError('Invalid exploratory CPU upper bound')
    warnings=[r for r in dict.fromkeys(reasons) if r in WARNINGS]
    fatal=[r for r in dict.fromkeys(reasons) if r not in WARNINGS]
    if cpu_upper>POLICY['outsideCpuUpperCeilingPercent']:fatal.append('Exploratory outside CPU exceeded25% upper bound')
    return warnings,fatal


def compile_verifier(setup):
    setup.mkdir(parents=True,exist_ok=False)
    jars=list(pathlib.Path('/home/y/.gradle/caches/modules-2/files-2.1/org.hdrhistogram/HdrHistogram/2.2.2').glob('*/*.jar'))
    if len(jars)!=1:raise ValueError('Require exact installed HdrHistogram2.2.2 jar')
    origin=jars[0];jar=setup/origin.name;shutil.copyfile(origin,jar)
    source=evidence.ROOT/'scripts/java/TailCache12HdrVerify.java'
    subprocess.run(['javac','-cp',str(jar),'-d',str(setup),str(source)],check=True,capture_output=True,text=True)
    return dict(setup=setup.name,jar=jar.name,jarOrigin=str(origin),jarSha256=evidence.file_sha(jar),
        classSha256=evidence.file_sha(setup/'TailCache12HdrVerify.class'),sourceSha256=evidence.file_sha(source))


def verify_hdr(worker,proof,parent):
    setup=parent/proof['setup'];jar=setup/proof['jar']
    if (evidence.file_sha(jar)!=proof['jarSha256'] or
            evidence.file_sha(setup/'TailCache12HdrVerify.class')!=proof['classSha256']):
        raise ValueError('Offline HDR verifier identity changed')
    result=subprocess.run(['java','-Xmx64m','-cp',str(setup)+os.pathsep+str(jar),'TailCache12HdrVerify',str(worker)],
        capture_output=True,text=True,timeout=60)
    if result.returncode:raise ValueError('Offline HDR verification failed: '+result.stderr[-1500:])
    return json.loads(result.stdout)


def timer_summary(raw,props,runtime):
    worker=raw/'every-operation/worker';text=(worker/'configuration.txt').read_text()
    config=dict(line.split('=',1) for line in text.splitlines() if '=' in line)
    if (config.get('timerFloor')!='true' or config.get('validation')!='none' or config.get('compilerXml')!='false'
            or config.get('compilerCounters')!='true' or any(config.get(k)!=runtime[k] for k in ('jdkVersion','vmName','vmVersion'))):
        raise ValueError('Wrong timer/runtime controls')
    if config.get('backend')!=props['Backend']:raise ValueError('Timer backend identity changed')
    for prop,field in (('Residents','residentEntries'),('Payload','payloadBytes'),('LiveBytes','applicationLiveBytes'),
                       ('Seed','seed'),('ChurnBytesPerSecond','churnBytesPerSecond')):
        if not re.search(r'\b'+field+'='+str(props[prop])+r'(?:,|\])',config['config']):
            raise ValueError('Timer workload controls changed')
    validate_lifecycle_preparation(props,text,config['jvmArgs'])
    from tailcache12_jfr import validate_instrumentation
    validate_instrumentation(config['jvmArgs'],props,False)
    for flag in ('-Xms512m','-Xmx512m','-XX:+UseG1GC'):
        if flag not in config['jvmArgs']:raise ValueError('Missing timer heap/G1 controls')
    for option,value in (('--warmup',30),('--conditioning',8),('--measure',8),('--iteration-ms',1000)):
        if not re.search(re.escape(option)+'='+str(value)+r'(?:,|\})',config['options']):
            raise ValueError('Wrong timer timing controls')
    with (worker/'iterations.csv').open() as stream:rows=list(csv.DictReader(stream))
    expected=[(phase,n) for phase,count in (('WARMUP',30),('CONDITIONING',8),('MEASUREMENT',8)) for n in range(1,count+1)]
    if [(r['phase'],int(r['iteration'])) for r in rows]!=expected:raise ValueError('Incomplete timer phase evidence')
    validate_windows([(int(r['startNs']),int(r['endNs'])) for r in rows])
    bins={};measured=[r for r in rows if r['phase']=='MEASUREMENT']
    for row in rows:
        if int(row['endNs'])-int(row['startNs'])<10**9 or int(row['operations'])<=0:
            raise ValueError('Invalid timer interval/count')
        if row['phase']=='WARMUP':continue
        directory=worker/'conditioning' if row['phase']=='CONDITIONING' else worker
        for channel in ('service','completion-gap'):
            values=histogram(directory/f"iteration-{row['iteration']}-{channel}-bins.csv",int(row['operations']))
            if row['phase']=='MEASUREMENT' and channel=='service':
                for value,count in values:bins[value]=bins.get(value,0)+count
    compiler=[int(r['compilerMs']) for r in measured]
    return dict(kind='timer',operations=sum(int(r['operations']) for r in measured),
        servicePercentilesNs={str(p):quantile(sorted(bins.items()),p) for p in (50,95,99,99.9)},
        compilerPerIterationMs=compiler,rejectionReasons=compiler_rejection_reasons(sum(compiler),compiler))


def audit_row(attempt,manifest,invocation,runtime,trace):
    raw=calibration.verify_invocation(attempt,invocation);p=invocation['properties'];channel=p['Channel']
    if channel in ('floor','sample-calibration'):
        record=json.loads((raw/channel/'results.json').read_text())[0]
        actual={k:record[k] for k in ('jmhVersion','jdkVersion','vmName','vmVersion')}
        if runtime is None:runtime=actual
        text=(raw/channel/'jmh.txt').read_text()+(attempt/invocation['label']/'gradle.log').read_text()
        traces=set(re.findall(r'traceSha256=([0-9a-f]{64})',text))
        if len(traces)!=1:raise ValueError('Missing/ambiguous exploratory workload trace')
        if trace is None:trace=next(iter(traces))
        summary=jmh_fork_summary(raw,channel,dict(p,ConsoleFile=str(attempt/invocation['label']/'gradle.log')),trace,runtime)
    elif channel=='every-operation':
        summary=every_operation_fork_summary(raw/channel,p,trace,runtime_identity=runtime)
    elif channel=='timer':summary=timer_summary(raw,p,runtime)
    else:raise ValueError('Unknown exploratory channel')
    if channel in ('timer','every-operation'):
        summary['offlineHdrVerification']=verify_hdr(raw/'every-operation/worker',manifest['hdrVerifier'],attempt.parent)
    with (attempt/invocation['label']/'host.csv').open() as stream:
        host=[evidence.decode_host_row(r) for r in csv.DictReader(stream)]
    host_reasons,_=evidence.replay_host_gate(manifest,raw,host)
    host_reasons+=invocation.get('hostMonitorErrors',[])
    windows=evidence.measurement_windows(raw);intervals=evidence.native_host.cpu_intervals(host)
    selected=[r for r in intervals if any(r['endNs']>=a-10_000_000_000 and r['startNs']<=b for a,b in windows)]
    if not selected:raise ValueError('No exploratory CPU coverage')
    upper=max(r['outsideUpperPercent'] for r in selected)
    durations=[r['nativeObserverReadDurationNs']/1e6 for r in host]
    reasons=list(summary['rejectionReasons'])+host_reasons
    if statistics.median(durations)>10:reasons.append('Native observer median read duration exceeded 10 ms')
    warnings,fatal=classify(reasons,upper)
    row=dict(summary,label=invocation['label'],inputs=p,hostRejectionReasons=host_reasons,
        strictReasons=list(dict.fromkeys(reasons)),warnings=warnings,fatalReasons=fatal,
        strictQualityPass=not reasons,exploratoryUsable=not fatal,primaryEndpointUseAllowed=False,
        outsideCpuUpperPercent=upper,hostWindowStartNs=host[0]['monotonicNs'],hostWindowEndNs=host[-1]['monotonicNs'])
    return row,runtime,trace


def verify_declaration(attempt,manifest):
    protocol=json.loads((attempt/'protocol.json').read_text());slots=schedule()
    canonical=[dict(label=k,properties=p) for k,p in slots]
    if (manifest.get('schemaVersion')!=VERSION or manifest.get('stage')!='exploratory-e2e'
            or manifest.get('primaryEndpointUseAllowed') is not False or manifest.get('reportable') is not False
            or protocol.get('policy')!=POLICY or protocol.get('schedule')!=canonical
            or manifest['expectedBlocks']!=[k for k,p in slots]
            or evidence.file_sha(attempt/'protocol.json')!=manifest['protocolSha256']
            or evidence.file_sha(attempt/'source.tar.gz')!=manifest['sourceArchiveSha256']
            or archive_measurement_source_hash(attempt/'source.tar.gz')!=manifest['measurementSourceSha256']
            or protocol.get('sourceSha256')!=manifest['sourceSha256']
            or protocol.get('measurementSourceSha256')!=manifest['measurementSourceSha256']
            or protocol.get('hdrVerifier')!=manifest.get('hdrVerifier')
            or manifest.get('initialMemoryReadinessRule')!=AVAILABLE_MEMORY_RULE
            or len(manifest['invocations'])>len(slots)):
        raise ValueError('Changed exploratory protocol/source/schedule')
    for inv,(label,props) in zip(manifest['invocations'],slots):
        if inv['label']!=label or inv['properties']!=props:raise ValueError('Exploratory schedule changed/duplicated')


def describe(rows):
    workload=[r for r in rows if r['label'].startswith('work-')];comparisons=[];disagreements=[];floor_ratios=[]
    for payload in (256,4096):
        for live in (0,96,208,288):
            directions={}
            for channel in ('sample-calibration','every-operation'):
                selected={r['inputs']['Backend']:r for r in workload if r['inputs']['Payload']==payload
                    and r['inputs']['LiveBytes']==live*1024**2 and r['inputs']['Channel']==channel and r['exploratoryUsable']}
                if set(selected)!=set(evidence.BACKENDS):continue
                ratios={p:selected['CHRONICLE_IN_MEMORY']['servicePercentilesNs'][p]/selected['CAFFEINE']['servicePercentilesNs'][p]
                    for p in ('99','99.9')}
                comparisons.append(dict(payloadBytes=payload,liveMiB=live,channel=channel,chronicleToCaffeine=ratios,
                    confidenceInterval=None,warningBearing=any(r['warnings'] for r in selected.values())))
                directions[channel]={p:1 if x>1 else -1 if x<1 else 0 for p,x in ratios.items()}
            if len(directions)==2:
                for p in ('99','99.9'):
                    if directions['sample-calibration'][p]*directions['every-operation'][p]<0:
                        disagreements.append(dict(payloadBytes=payload,liveMiB=live,percentile=p,
                            warning='Opposite descriptive channel directions; no confidence/causal claim'))
    for row in workload:
        if row['inputs']['LiveBytes']!=0 or not row['exploratoryUsable']:continue
        p=row['inputs'];timer=p['Channel']=='every-operation'
        floors=[r['servicePercentilesNs']['50'] for r in rows if r['exploratoryUsable'] and
            (r['inputs']['Channel']=='timer' if timer else r['inputs']['Channel']=='floor'
                and r['inputs']['Backend']==p['Backend'] and r['inputs']['Payload']==p['Payload'])]
        if len(floors)!=2:continue
        ratio=max(floors)/row['servicePercentilesNs']['50']
        limit=FLOOR_RULES['timerMedianToEveryopMedianCeiling' if timer else 'supplyMedianToSampleMedianCeiling']
        floor_ratios.append(dict(label=row['label'],ratio=ratio,ceiling=limit,warning=ratio>limit))
    return dict(comparisons=comparisons,channelDisagreements=disagreements,floorRatios=floor_ratios,
                runToRunVariance=None,confidenceIntervals=None,robustnessCollected=False)


def replay(attempt):
    manifest=json.loads((attempt/'manifest.json').read_text());verify_declaration(attempt,manifest)
    rows=[];runtime=trace=None
    for inv in manifest['invocations']:
        row,runtime,trace=audit_row(attempt,manifest,inv,runtime,trace);rows.append(row)
    quiet=native_retry.verify_initial_quiet(attempt,dict(manifest,nativeHostRetryPolicy=native_retry.declare_policy(2)),rows)
    complete=len(rows)==len(schedule()) and all(r['exploratoryUsable'] for r in rows) and not manifest.get('terminalDriverFailure')
    return dict(schemaVersion=VERSION,taskComplete=False,exploratoryComplete=complete,reportable=False,
        campaignReady=False,primaryEndpointUseAllowed=False,collectedFreshJvms=len(rows),expectedFreshJvms=42,
        missingSlots=[k for k,p in schedule()[len(rows):]],observations=rows,initialQuietReplay=quiet,
        policy=POLICY,limits=LIMITS,**describe(rows))


def export(attempt,result,destination):
    if not result['exploratoryComplete']:raise ValueError('Cannot export partial/hard-rejected cohort as complete')
    rows=result.get('observations',[])
    if len(rows)!=42 or [r['label'] for r in rows]!=[k for k,p in schedule()] or any(not r['exploratoryUsable'] for r in rows):
        raise ValueError('Incomplete/changed exploratory export coverage')
    # Reconstruct acceptance from raw data, never trust a caller-supplied completion flag.
    result=replay(attempt)
    if not result['exploratoryComplete']:raise ValueError('Fresh raw replay rejects complete export')
    if destination.exists() or destination.resolve().is_relative_to(evidence.ROOT/'build'):
        raise ValueError('Require unique outside-build exploratory destination')
    destination.mkdir(parents=True)
    evidence.save(destination/'dataset.json',result)
    shutil.copyfile(attempt/'protocol.json',destination/'protocol.json')
    fields=['label','channel','backend','payloadBytes','applicationLiveMiB','p99Ns','p999Ns','occupancyFraction',
        'strictQualityPass','exploratoryUsable','warnings','fatalReasons']
    with (destination/'coverage.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fields);writer.writeheader()
        for row in result['observations']:
            p=row['inputs'];gc=row.get('gc',row)
            writer.writerow(dict(zip(fields,[row['label'],p['Channel'],p['Backend'],p['Payload'],p['LiveBytes']/1024**2,
                row['servicePercentilesNs']['99'],row['servicePercentilesNs']['99.9'],gc.get('postGcUsedHeapMedianFraction'),
                row['strictQualityPass'],row['exploratoryUsable'],json.dumps(row['warnings']),json.dumps(row['fatalReasons'])])))
    manifest=json.loads((attempt/'manifest.json').read_text());quiet=attempt.parent/manifest['initialQuietRef']['attempt']
    roots=[attempt,quiet,attempt.parent/manifest['hdrVerifier']['setup']]
    roots += [evidence.raw_directory(attempt,inv) for inv in manifest['invocations']]
    files={p for root in roots for p in root.rglob('*') if p.is_file()}
    files.add(attempt.parent/json.loads((quiet/'host-preparation.json').read_text())['inventoryFile'])
    files.add(attempt.parent/(quiet.name+'-cache-preparation.json'))
    if any(p.is_symlink() or not p.resolve().is_relative_to(evidence.REPORTS.resolve()) for p in files):
        raise ValueError('External/symlink exploratory dependency')
    from tailcache12_archive import file_digest,stream_digest,advise
    inventory=[];path=destination/'raw-sources.tar.gz'
    with tarfile.open(path,'x:gz',compresslevel=1) as archive:
        for p in sorted(files):
            name=p.relative_to(evidence.ROOT).as_posix()
            inventory.append(dict(path=name,bytes=p.stat().st_size,sha256=file_digest(p)))
            archive.add(p,arcname=name,recursive=False);advise(p)
    expected={r['path']:r for r in inventory};seen=set()
    with tarfile.open(path,'r:gz') as archive:
        for member in archive:
            if not member.isfile() or member.name in seen or member.name not in expected:raise ValueError('Invalid archive member')
            row=expected[member.name]
            with archive.extractfile(member) as stream:
                if member.size!=row['bytes'] or stream_digest(stream)!=row['sha256']:raise ValueError('Archive verification failed')
            seen.add(member.name)
    if seen!=set(expected):raise ValueError('Missing archive dependency')
    evidence.save(destination/'archive-inventory.json',inventory)
    evidence.save(destination/'archive.json',dict(path=path.name,sha256=file_digest(path),bytes=path.stat().st_size,
        verifiedMembers=len(seen),historicalEvidencePooled=False))
    advise(path)
    (destination/'README.md').write_text('# Exploratory TailCache matrix\n\nAll42 fresh forks were mechanically usable under the declared exploratory warning policy. '
        'Read dataset.json and coverage.csv for every original strict reason, descriptive comparison and limitation. '
        'This is not an accepted primary Task12 campaign. No confidence intervals, run-to-run variance or seed robustness are established. '
        'The verified archive preserves raw observations, controls, protocol, source and initial preparation. Researcher outcome review remains required.\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=('run','audit'))
    parser.add_argument('attempt_id');parser.add_argument('--quiet-id');parser.add_argument('--output',type=pathlib.Path)
    args=parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9._-]+',args.attempt_id):parser.error('Invalid attempt ID')
    attempt=evidence.REPORTS/args.attempt_id
    if args.stage=='audit':
        result=replay(attempt)
        if args.output:export(attempt,result,args.output.resolve())
        print(json.dumps({k:result[k] for k in ('exploratoryComplete','collectedFreshJvms','expectedFreshJvms')}));return 0 if result['exploratoryComplete'] else 1
    if not args.quiet_id or not re.fullmatch('[A-Za-z0-9._-]+',args.quiet_id):parser.error('Require fresh quiet ID')
    quiet=evidence.REPORTS/args.quiet_id;prep=evidence.REPORTS/(args.quiet_id+'-cache-preparation.json')
    setup=evidence.REPORTS/(args.attempt_id+'-setup')
    if any(p.exists() for p in (attempt,quiet,prep,prep.with_suffix('.inventory.jsonl'),setup)):
        raise ValueError('Retained evidence exists; no duplicate or overwrite')
    if any(os.environ.get(k) for k in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS')):
        raise ValueError('Require clean unprofiled JVM options')
    if shutil.disk_usage(evidence.ROOT).free<4*1024**3:raise ValueError('Require4GiB disk')
    current=evidence.host_snapshot()
    if os.environ.get('TAILCACHE_REQUIRE_NATIVE_HOST')!='1' or current.get('nativeScopeQualified')!=1:
        raise ValueError('Exploratory collection requires exclusive native scope')
    source=evidence.source_hash();helper=compile_verifier(setup)
    cache=prepare_file_cache(prep,include_build_outputs=True,stream_inventory=True,available_memory=True)
    if not run_preflight(quiet,120,300)['quietPass'] or source!=evidence.source_hash():
        raise ValueError('Initial quiet rejected/source changed; no cache worker launched')
    evidence.save(quiet/'host-preparation.json',cache)
    options=SimpleNamespace(stage='exploratory-e2e',heap_mib=512,residents=32768,churn_mib=32,live_mib=[0,96,208,288],
        payloads=[256,4096],seed=24301,warmups=30,measurements=8,repeats=1,channels=['sample-calibration','every-operation'],
        conditioning=8,transport_warmup=True,maintenance_warmup=True,resume=False)
    slots=schedule();manifest=calibration.prepare(attempt,options,slots)
    manifest.update(schemaVersion=VERSION,primaryEndpointUseAllowed=False,diagnosticOnly=True,
        initialMemoryReadinessRule=dict(AVAILABLE_MEMORY_RULE),measurementSourceSha256=measurement_source_hash(evidence.ROOT),
        hdrVerifier=helper,nativeEnvironmentVersion=1,nativeEnvironmentDeclaration=evidence.native_host.environment_declaration(evidence.host_snapshot()))
    manifest['initialQuietRef']=native_retry.initial_quiet_reference(quiet,manifest,native_retry.declare_policy(2),evidence.host_snapshot())
    protocol=dict(policy=POLICY,schedule=[dict(label=k,properties=p) for k,p in slots],sourceSha256=source,
        measurementSourceSha256=manifest['measurementSourceSha256'],hdrVerifier=helper,
        plan='docs/TAILCACHE_12_EXPLORATORY_E2E_PLAN.md')
    evidence.save(attempt/'protocol.json',protocol);manifest['protocolSha256']=evidence.file_sha(attempt/'protocol.json')
    evidence.save(attempt/'manifest.json',manifest)
    rows=[];runtime=trace=None
    try:
        verify_declaration(attempt,manifest)
        native_retry.verify_initial_quiet(attempt,dict(manifest,nativeHostRetryPolicy=native_retry.declare_policy(2)),before_launch=True)
        for label,p in slots:
            task='tailCache12SupplyFloor' if p['Channel']=='floor' else 'tailCache12SampleCalibration' if p['Channel']=='sample-calibration' else 'tailCache12EveryOperation'
            evidence.invoke(attempt,manifest,label,task,p)
            row,runtime,trace=audit_row(attempt,manifest,manifest['invocations'][-1],runtime,trace);rows.append(row)
            evidence.save(attempt/(label+'-audit.json'),row)
            print(f"exploratory {len(rows)}/42 {label}: warnings={row['warnings']} fatal={row['fatalReasons']}",flush=True)
            if row['fatalReasons']:raise ValueError('Hard exploratory rejection; no replacements')
        result=replay(attempt);evidence.save(attempt/'exploratory-review.json',result)
        if args.output:export(attempt,result,args.output.resolve())
        return 0 if result['exploratoryComplete'] else 1
    except Exception as error:
        manifest['terminalDriverFailure']=dict(reason=f'{type(error).__name__}: {error}')
        evidence.save(attempt/'manifest.json',manifest);raise


if __name__=='__main__':raise SystemExit(main())
