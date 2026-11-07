#!/usr/bin/env python3
"""Four worker-only JFR diagnostics; never ordinary qualification/primary evidence."""
import argparse
import csv
import hashlib
import json
import os
import pathlib
import re
import shutil
import sys
import tarfile
from types import SimpleNamespace

import tailcache12 as evidence
import tailcache12_calibrate as calibration
import tailcache12_native_retry as native_retry
from tailcache12_calibration_start import prepare_file_cache
from tailcache12_quiet import run_preflight
from tailcache12_provenance import archive_measurement_source_hash, measurement_source_hash
from tailcache12_study_analysis import every_operation_fork_summary, jmh_fork_summary
from tailcache12_analysis import parse_gc
from tailcache12_jfr import print_events, recording_file, verify_metadata, verify_single_chunk

SETTINGS = 'src/main/resources/tailcache12-observer-profile.jfc'


def grid():
    slots=[]
    for block in (1,2):
        for channel in (('sample-calibration','every-operation') if block==1 else ('every-operation','sample-calibration')):
            props=dict(Backend='CHRONICLE_IN_MEMORY',Backends='CHRONICLE_IN_MEMORY',Payload=256,Payloads=256,
                Residents=32768,HeapMiB=512,LiveBytes=0,ChurnBytesPerSecond=33554432,Seed=24301,
                Warmups=120,Conditioning=16,Measurements=8,Forks=1,Channel=channel,
                TransportWarmupVersion=evidence.TRANSPORT_WARMUP_VERSION,LifecycleWarmupVersion=evidence.LIFECYCLE_WARMUP_VERSION,
                FlightRecorder='true',DiagnosticOnly='true')
            slots.append((f'r{block}-{channel}-CHRONICLE_IN_MEMORY-p256-live0',props))
    return slots


def replay(attempt, review_id):
    manifest=json.loads((attempt/'manifest.json').read_text())
    expected=grid()
    if (manifest.get('schemaVersion')!='tailcache12-worker-profile-v1'
            or manifest.get('stage')!='observer-profile' or not manifest.get('diagnosticOnly')
            or manifest.get('cachePreparationVersion')!=3
            or manifest.get('primaryEndpointUseAllowed') is not False or manifest['expectedBlocks']!=[k for k,v in expected]
            or calibration.sha(attempt/'source.tar.gz')!=manifest['sourceArchiveSha256']):
        raise ValueError('Changed worker-profile declaration/source')
    with tarfile.open(attempt/'source.tar.gz','r:gz') as archive:
        settings_sha=hashlib.sha256(archive.extractfile(SETTINGS).read()).hexdigest()
    if settings_sha!=manifest['profileSettingsSha256']:
        raise ValueError('Profile settings differ from frozen source')
    if archive_measurement_source_hash(attempt/'source.tar.gz')!=manifest['measurementSourceSha256']:
        raise ValueError('Profile measurement-source identity changed')
    native_retry.verify_initial_quiet(attempt,dict(manifest,nativeHostRetryPolicy=native_retry.declare_policy(2)))
    preparation=json.loads((attempt.parent/manifest['initialQuietRef']['attempt']/'host-preparation.json').read_text())
    if preparation.get('version')!=3:raise ValueError('Profile requires its declared private-cache preparation')
    destination=attempt/review_id;destination.mkdir()
    rows=[];runtime=None;trace=None
    for index,invocation in enumerate(manifest['invocations']):
        label,props=expected[index]
        if invocation['label']!=label or invocation['properties']!=props:
            raise ValueError('Changed profile slot/order/controls')
        raw=calibration.verify_invocation(attempt,invocation);channel=props['Channel'];directory=raw/channel
        control=destination/label;control.mkdir()
        marker=list(raw.rglob('worker-process-*.properties'))
        if len(marker)!=1:raise ValueError('Ambiguous actual worker')
        worker=dict(line.split('=',1) for line in marker[0].read_text().splitlines() if '=' in line)
        pid=int(worker['pid'])
        if not all(worker.get(k) for k in ('javaThreadId','osThreadId','javaThreadName')):
            raise ValueError('Missing actual worker thread identity')
        if int(worker['javaThreadId'])<=0 or int(worker['osThreadId'])<=0:
            raise ValueError('Invalid actual worker thread identity')
        if channel=='sample-calibration':
            record=json.loads((directory/'results.json').read_text())[0]
            actual={k:record[k] for k in ('jmhVersion','jdkVersion','vmName','vmVersion')}
            if runtime is None:runtime=actual
            text=(directory/'jmh.txt').read_text()+(attempt/label/'gradle.log').read_text()
            traces=set(re.findall(r'traceSha256=([0-9a-f]{64})',text))
            if len(traces)!=1:raise ValueError('Missing profile trace')
            current=next(iter(traces))
            if trace is None:trace=current
            if trace!=current:raise ValueError('Profile trace differs')
            summary=jmh_fork_summary(raw,channel,dict(props,ConsoleFile=str(attempt/label/'gradle.log')),
                trace,runtime,diagnostic_flight_recording=True)
            with next(directory.glob('iterations-*.csv')).open() as stream:
                iterations=list(csv.DictReader(stream))
            windows=[(int(r['envelopeStartNs']),int(r['envelopeEndNs'])) for r in iterations if r['phase']=='MEASUREMENT']
            worker_main='org.openjdk.jmh.runner.ForkedMain'
        else:
            summary=every_operation_fork_summary(directory,props,trace,runtime_identity=runtime,
                diagnostic_flight_recording=True)
            with (directory/'worker/iterations.csv').open() as stream:iterations=list(csv.DictReader(stream))
            windows=[(int(r['startNs']),int(r['endNs'])) for r in iterations if r['phase']=='MEASUREMENT']
            worker_main='io.github.enixes.tailcache.workload.CrossoverLatencyRunner'
        recording=recording_file(directory,settings_sha)
        layout=verify_single_chunk(pathlib.Path(os.environ['JAVA_HOME'])/'bin/jfr',recording,control)
        events=[]
        for event in print_events(pathlib.Path(os.environ['JAVA_HOME'])/'bin/jfr',recording,
                ['jdk.JVMInformation','jdk.GarbageCollection','jdk.Shutdown','jdk.DataLoss'],control/'metadata.stderr'):
            events.append(event)
            if len(events)>10000:raise ValueError('Unexpectedly large profile metadata inventory')
        evidence.save(control/'metadata.json',events)
        gc=parse_gc(directory/f'gc-{pid}.log')
        profile=verify_metadata(events,pid,worker_main,gc['pauses'],windows,runtime_identity=runtime)
        phases=[dict(phase=r['phase'],startNs=int(r.get('envelopeStartNs',r.get('startNs'))),
                     endNs=int(r.get('envelopeEndNs',r.get('endNs')))) for r in iterations]
        with (attempt/label/'host.csv').open() as stream:
            host=[evidence.decode_host_row(row) for row in csv.DictReader(stream)]
        reasons,_=evidence.replay_host_gate(manifest,raw,host)
        reasons+=invocation.get('hostMonitorErrors',[])
        row=dict(summary,label=label,worker=worker,profile=profile,recordingLayout=layout,windows=windows,phaseWindows=phases,
                 hostRejectionReasons=reasons,hostWindowStartNs=host[0]['monotonicNs'],hostWindowEndNs=host[-1]['monotonicNs'],
                 reportable=False,primaryEndpointUseAllowed=False)
        rows.append(row)
    quiet=native_retry.verify_initial_quiet(attempt,dict(manifest,nativeHostRetryPolicy=native_retry.declare_policy(2)),rows)
    result=dict(observations=rows,expectedFreshJvms=4,collectedFreshJvms=len(rows),reportable=False,
        primaryEndpointUseAllowed=False,profileAndQualityPass=len(rows)==4 and all(
            not r['rejectionReasons'] and not r['hostRejectionReasons'] for r in rows),
        initialQuietReplay=quiet,requiresWorkerStackAndAllocationSiteReview=True)
    evidence.save(destination/'review.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('run','audit'))
    parser.add_argument('attempt_id');parser.add_argument('--quiet-id');parser.add_argument('--review-id',default='profile-review-001')
    args=parser.parse_args()
    if any(not re.fullmatch(r'[A-Za-z0-9._-]+',x) for x in (args.attempt_id,args.review_id)):
        parser.error('Invalid identifiers')
    attempt=evidence.REPORTS/args.attempt_id
    if args.stage=='audit':return 0 if replay(attempt,args.review_id)['profileAndQualityPass'] else 1
    if not args.quiet_id or not re.fullmatch(r'[A-Za-z0-9._-]+',args.quiet_id):parser.error('Require distinct quiet identifier')
    quiet=evidence.REPORTS/args.quiet_id;cache_path=evidence.REPORTS/(args.quiet_id+'-cache-preparation.json')
    if any(p.exists() for p in (attempt,quiet,cache_path)):raise ValueError('Retained profile/preparation exists; no duplicate')
    if any(os.environ.get(k) for k in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS')):
        raise ValueError('Worker profiles require a clean parent JVM-option environment')
    if shutil.disk_usage(evidence.ROOT).free<4*1024**3:
        raise ValueError('Require4GiB free disk for bounded recordings/review/preservation')
    source=evidence.source_hash();cache=prepare_file_cache(cache_path,include_build_outputs=True)
    if cache.get('version')!=3:raise ValueError('Unexpected profile cache preparation version')
    if not run_preflight(quiet,120,300)['quietPass'] or source!=evidence.source_hash():
        raise ValueError('Profile preparation failed or source changed')
    evidence.save(quiet/'host-preparation.json',cache)
    options=SimpleNamespace(stage='observer-profile',heap_mib=512,residents=32768,churn_mib=32,
        live_mib=[0],payloads=[256],seed=24301,warmups=120,measurements=8,repeats=2,
        channels=['sample-calibration','every-operation'],conditioning=16,transport_warmup=True,maintenance_warmup=True,resume=False)
    slots=grid();manifest=calibration.prepare(attempt,options,slots)
    current=evidence.host_snapshot()
    if os.environ.get('TAILCACHE_REQUIRE_NATIVE_HOST')!='1' or current.get('nativeScopeQualified')!=1:
        raise ValueError('Worker profile requires its exclusive native accounting scope')
    manifest.update(schemaVersion='tailcache12-worker-profile-v1',diagnosticOnly=True,primaryEndpointUseAllowed=False,maxFreshJvms=4,
        replacements=0,cachePreparationVersion=3,nativeEnvironmentVersion=1,nativeEnvironmentDeclaration=evidence.native_host.environment_declaration(current),
        measurementSourceSha256=measurement_source_hash(evidence.ROOT),
        profileSettingsSha256=calibration.sha(evidence.ROOT/SETTINGS),
        plan='docs/TAILCACHE_12_JFR_PROFILE_PLAN.md')
    # Reuse only quiet-validation fields; this creates no replacement policy or retry slots.
    manifest['initialQuietRef']=native_retry.initial_quiet_reference(quiet,manifest,native_retry.declare_policy(2),current)
    evidence.save(attempt/'manifest.json',manifest)
    for index,(label,props) in enumerate(slots):
        if index==0:native_retry.verify_initial_quiet(attempt,dict(manifest,nativeHostRetryPolicy=native_retry.declare_policy(2)),before_launch=True)
        evidence.invoke(attempt,manifest,label,'tailCache12SampleCalibration' if props['Channel']=='sample-calibration'
                        else 'tailCache12EveryOperation',props)
    return 0 if replay(attempt,args.review_id)['profileAndQualityPass'] else 1


if __name__=='__main__':raise SystemExit(main())
