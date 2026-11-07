#!/usr/bin/env python3
"""Twelve unprofiled, diagnostic-only sparse/common/every-operation forks."""
import argparse
import csv
import json
import os
import pathlib
import re
import shutil
from types import SimpleNamespace

import tailcache12 as evidence
import tailcache12_calibrate as calibration
import tailcache12_native_retry as native_retry
from tailcache12_calibration_start import prepare_file_cache
from tailcache12_provenance import archive_measurement_source_hash,measurement_source_hash
from tailcache12_quiet import run_preflight
from tailcache12_sample_selection import VERSION,DENSE_VERSION
from tailcache12_study_analysis import jmh_fork_summary,every_operation_fork_summary


def grid():
    result=[]
    for block in (1,2):
        backends=evidence.BACKENDS if block==1 else tuple(reversed(evidence.BACKENDS))
        modes=('sparse','common','every') if block==1 else ('every','common','sparse')
        for backend in backends:
            for mode in modes:
                p=dict(Backend=backend,Backends=backend,Payload=256,Payloads=256,Residents=32768,
                    HeapMiB=512,LiveBytes=0,ChurnBytesPerSecond=33554432,Seed=24301,
                    Warmups=120,Conditioning=16,Measurements=8,Forks=1,
                    Channel='every-operation' if mode=='every' else 'sample-calibration',ObservationMode=mode,
                    TransportWarmupVersion=evidence.TRANSPORT_WARMUP_VERSION,LifecycleWarmupVersion=evidence.LIFECYCLE_WARMUP_VERSION)
                if mode=='common':p.update(DenseObserver='true',ObserverDiagnosticOnly='true')
                result.append((f'r{block}-{mode}-{backend}-p256-live0',p))
    return result


def compare(rows):
    comparisons=[]
    for block in (1,2):
        for backend in evidence.BACKENDS:
            selected={r['inputs']['ObservationMode']:r for r in rows
                      if r['label'].startswith(f'r{block}-') and r['inputs']['Backend']==backend}
            if set(selected)!=set(('sparse','common','every')):raise ValueError('Missing diagnostic comparison')
            common,reference=selected['common'],selected['every']
            rate=common['observedOperationsPerSecond']/reference['observedOperationsPerSecond']
            ratios={p:common['servicePercentilesNs'][p]/reference['servicePercentilesNs'][p] for p in ('99','99.9')}
            comparisons.append(dict(block=block,backend=backend,commonToEveryThroughput=rate,
                commonToEveryTailRatios=ratios,criteriaPass=abs(rate-1)<=.15 and all(abs(x-1)<=.25 for x in ratios.values()),
                sparse=selected['sparse']['servicePercentilesNs'],common=common['servicePercentilesNs'],
                every=reference['servicePercentilesNs'],rates={k:r['observedOperationsPerSecond'] for k,r in selected.items()}))
    return comparisons


def replay(attempt,review_id):
    manifest=json.loads((attempt/'manifest.json').read_text());expected=grid()
    if (manifest.get('schemaVersion')!='tailcache12-common-observer-probe-v1'
            or manifest.get('stage')!='common-observer-probe' or manifest.get('replacements')!=0
            or manifest.get('diagnosticOnly') is not True or manifest.get('cachePreparationVersion')!=4
            or manifest.get('maxFreshJvms')!=12 or manifest.get('primaryEndpointUseAllowed') is not False
            or manifest['expectedBlocks']!=[k for k,p in expected]
            or calibration.sha(attempt/'source.tar.gz')!=manifest['sourceArchiveSha256']
            or archive_measurement_source_hash(attempt/'source.tar.gz')!=manifest['measurementSourceSha256']):
        raise ValueError('Changed diagnostic declaration/source')
    if len(manifest['invocations'])!=12:raise ValueError('Incomplete diagnostic collection')
    if not manifest.get('initialQuietRef',{}).get('hostPreparationSha256'):
        raise ValueError('Missing frozen diagnostic cache preparation')
    preparation=json.loads((attempt.parent/manifest['initialQuietRef']['attempt']/'host-preparation.json').read_text())
    if preparation.get('version')!=4:raise ValueError('Diagnostic requires its declared streaming preparation')
    if manifest.get('toolCachePreparationVersion')==1 and not preparation.get('toolCachePreparationSha256'):
        raise ValueError('Missing declared task-tooling cache preparation')
    if manifest.get('dependencyCachePreparationVersion')==1 and not preparation.get('dependencyCachePreparationSha256'):
        raise ValueError('Missing declared inactive dependency preparation')
    destination=attempt/review_id;destination.mkdir();rows=[];runtime=None;trace=None
    for invocation,(label,props) in zip(manifest['invocations'],expected):
        if invocation['label']!=label or invocation['properties']!=props:raise ValueError('Changed diagnostic order/controls')
        raw=calibration.verify_invocation(attempt,invocation);channel=props['Channel'];mode=props['ObservationMode']
        directory=raw/channel
        if mode=='every':
            summary=every_operation_fork_summary(directory,props,trace,runtime_identity=runtime)
            rate=summary['workloadOperationsPerSecond']
        else:
            record=json.loads((directory/'results.json').read_text())[0]
            current={k:record[k] for k in ('jmhVersion','jdkVersion','vmName','vmVersion')}
            if runtime is None:runtime=current
            text=(directory/'jmh.txt').read_text()+(attempt/label/'gradle.log').read_text()
            traces=set(re.findall(r'traceSha256=([0-9a-f]{64})',text))
            if len(traces)!=1:raise ValueError('Missing diagnostic trace identity')
            actual=next(iter(traces))
            if trace is None:trace=actual
            if actual!=trace:raise ValueError('Diagnostic traces differ')
            summary=jmh_fork_summary(raw,channel,dict(props,ConsoleFile=str(attempt/label/'gradle.log')),
                trace,runtime,diagnostic_dense_observer=mode=='common')
            if summary['sampleSelection']['sampleSelectionVersion']!=(DENSE_VERSION if mode=='common' else VERSION):
                raise ValueError('Diagnostic loaded the wrong sparse/common sampler')
            if mode=='common':rate=summary['denseCapture']['operationsPerSecond']
            else:
                with next(directory.glob('iterations-*.csv')).open() as stream:
                    iterations=[r for r in csv.DictReader(stream) if r['phase']=='MEASUREMENT']
                rate=summary['operations']/(sum(int(r['envelopeEndNs'])-int(r['envelopeStartNs']) for r in iterations)/1e9)
        with (attempt/label/'host.csv').open() as stream:
            host=[evidence.decode_host_row(r) for r in csv.DictReader(stream)]
        reasons,_=evidence.replay_host_gate(manifest,raw,host);reasons+=invocation.get('hostMonitorErrors',[])
        rows.append(dict(summary,label=label,inputs=props,observedOperationsPerSecond=rate,
            hostRejectionReasons=reasons,hostWindowStartNs=host[0]['monotonicNs'],hostWindowEndNs=host[-1]['monotonicNs'],
            primaryEndpointUseAllowed=False,reportable=False))
    quiet=native_retry.verify_initial_quiet(attempt,dict(manifest,nativeHostRetryPolicy=native_retry.declare_policy(2)),rows)
    checked=compare(rows);quality=all(not r['rejectionReasons'] and not r['hostRejectionReasons'] for r in rows)
    result=dict(observations=rows,comparisons=checked,qualityPass=quality,
        diagnosticCriteriaPass=quality and all(c['criteriaPass'] for c in checked),collectedFreshJvms=12,
        expectedFreshJvms=12,reportable=False,campaignReady=False,primaryEndpointUseAllowed=False,
        initialQuietReplay=quiet,limits=['Subset/full capture within a fork is not independent replication.',
            'Raw sparse/full diagnostic failures remain historical; no automatic protocol adoption.',
            'Common throughput uses actual captured stub windows; sparse uses the broader JMH worker envelope.'])
    evidence.save(destination/'review.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=('run','audit'))
    parser.add_argument('attempt_id');parser.add_argument('--quiet-id');parser.add_argument('--review-id',default='common-review-001')
    parser.add_argument('--task-tool-cache',action='store_true')
    parser.add_argument('--inactive-dependency-cache',action='store_true')
    args=parser.parse_args()
    if any(not re.fullmatch(r'[A-Za-z0-9._-]+',s) for s in (args.attempt_id,args.review_id)):parser.error('Invalid IDs')
    attempt=evidence.REPORTS/args.attempt_id
    if args.stage=='audit':return 0 if replay(attempt,args.review_id)['diagnosticCriteriaPass'] else 1
    if not args.quiet_id or not re.fullmatch(r'[A-Za-z0-9._-]+',args.quiet_id):parser.error('Require fresh quiet ID')
    quiet=evidence.REPORTS/args.quiet_id;cache_path=evidence.REPORTS/(args.quiet_id+'-cache-preparation.json')
    tool_path=evidence.REPORTS/(args.quiet_id+'-tool-cache-preparation.json')
    dependency_path=evidence.REPORTS/(args.quiet_id+'-dependency-cache-preparation.json')
    if any(p.exists() for p in (attempt,quiet,cache_path,tool_path,dependency_path)):raise ValueError('Retained diagnostic exists; no duplicate')
    if any(os.environ.get(k) for k in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS')):
        raise ValueError('Diagnostic requires clean unprofiled VM options')
    if shutil.disk_usage(evidence.ROOT).free<4*1024**3:raise ValueError('Require4GiB disk before diagnostic')
    source=evidence.source_hash();tool=None;dependency=None
    if args.inactive_dependency_cache:
        current=evidence.host_snapshot()
        if os.environ.get('TAILCACHE_REQUIRE_NATIVE_HOST')!='1' or current.get('nativeScopeQualified')!=1:
            raise ValueError('Dependency preparation requires exclusive native scope')
    if args.task_tool_cache:
        from tailcache12_tool_cache import prepare as prepare_tool_cache
        tool=prepare_tool_cache(tool_path)
    if args.inactive_dependency_cache:
        from tailcache12_dependency_cache import prepare as prepare_dependency_cache
        dependency=prepare_dependency_cache(dependency_path)
    cache=prepare_file_cache(cache_path,include_build_outputs=True,stream_inventory=True)
    if cache.get('version')!=4:raise ValueError('Wrong diagnostic preparation version')
    if not run_preflight(quiet,120,300)['quietPass'] or source!=evidence.source_hash():
        raise ValueError('Diagnostic preparation failed/source changed')
    if tool:
        evidence.save(quiet/'tool-cache-preparation.json',tool)
        cache['toolCachePreparationSha256']=calibration.sha(quiet/'tool-cache-preparation.json')
    if dependency:
        evidence.save(quiet/'dependency-cache-preparation.json',dependency)
        cache['dependencyCachePreparationSha256']=calibration.sha(quiet/'dependency-cache-preparation.json')
    evidence.save(quiet/'host-preparation.json',cache)
    options=SimpleNamespace(stage='common-observer-probe',heap_mib=512,residents=32768,churn_mib=32,live_mib=[0],
        payloads=[256],seed=24301,warmups=120,measurements=8,repeats=2,channels=['sample-calibration','every-operation'],
        conditioning=16,transport_warmup=True,maintenance_warmup=True,resume=False)
    slots=grid();manifest=calibration.prepare(attempt,options,slots);current=evidence.host_snapshot()
    if os.environ.get('TAILCACHE_REQUIRE_NATIVE_HOST')!='1' or current.get('nativeScopeQualified')!=1:
        raise ValueError('Diagnostic requires exclusive native scope')
    manifest.update(schemaVersion='tailcache12-common-observer-probe-v1',diagnosticOnly=True,
        primaryEndpointUseAllowed=False,maxFreshJvms=12,replacements=0,cachePreparationVersion=4,
        nativeEnvironmentVersion=1,nativeEnvironmentDeclaration=evidence.native_host.environment_declaration(current),
        measurementSourceSha256=measurement_source_hash(evidence.ROOT),plan='docs/TAILCACHE_12_COMMON_OBSERVER_PLAN.md')
    if tool:manifest['toolCachePreparationVersion']=1
    if dependency:manifest['dependencyCachePreparationVersion']=1
    policy=native_retry.declare_policy(2)
    manifest['initialQuietRef']=native_retry.initial_quiet_reference(quiet,manifest,policy,current)
    evidence.save(attempt/'manifest.json',manifest)
    for index,(label,props) in enumerate(slots):
        if index==0:native_retry.verify_initial_quiet(attempt,dict(manifest,nativeHostRetryPolicy=policy),before_launch=True)
        evidence.invoke(attempt,manifest,label,'tailCache12EveryOperation' if props['ObservationMode']=='every'
                        else 'tailCache12SampleCalibration',props)
    return 0 if replay(attempt,args.review_id)['diagnosticCriteriaPass'] else 1


if __name__=='__main__':raise SystemExit(main())
