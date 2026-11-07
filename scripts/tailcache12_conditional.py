#!/usr/bin/env python3
"""Finite Task12 final study, with explicit observer-conditional acceptance/claims."""
import argparse
import collections
import copy
import csv
import datetime
import json
import os
import pathlib
import random
import shutil
import statistics
import subprocess
import sys
import tarfile
from types import SimpleNamespace

import tailcache12 as evidence
import tailcache12_calibrate as calibration
import tailcache12_exploratory as facts
import tailcache12_native_retry as native_retry
import tailcache12_campaign as legacy_analysis
from tailcache12_calibration_start import AVAILABLE_MEMORY_RULE,prepare_file_cache
from tailcache12_observer import floor_grid,RULES as FLOOR_RULES
from tailcache12_provenance import measurement_source_hash,archive_measurement_source_hash
from tailcache12_quiet import run_preflight
from tailcache12_analysis import CHURN_DROP_BUDGET_VERSION

VERSION='tailcache12-final-observer-conditional-v4-qualification-evidence'
CHURN_DROP_WARNING='Minor churn loss within predeclared32KiB/0.1% budget'
STAGES=('functional','pause','compiler-diagnostic','qualification','floors','calibration','pilot','campaign','robustness')
COUNTS={'functional':14,'pause':2,'compiler-diagnostic':8,'qualification':16,'floors':10,'calibration':64,'pilot':32,'campaign':192,'robustness':64}
RULES=dict(version=VERSION,warningReasons=list(facts.WARNINGS)+[evidence.THERMAL_STARTUP_WARNING,CHURN_DROP_WARNING],outsideCpuUpperCeilingPercent=25,
    warmups=30,conditioning=8,measurements=8,passes=2,primaryForksPerPass=3,replacements=0,
    liveMiB=[0,96,208,288],payloads=[256,4096],residents=32768,heapMiB=512,churnMiBPerSecond=32,
    seed=24301,orderSeed=0x1207,robustnessSeeds=[0xC0FFEE,0xBADC0DE],robustnessPasses=1,robustnessForksPerCell=1,
    qualificationCompilerCeilingsHard=False,qualificationCompilerTotalCeilingMs=80,qualificationCompilerIntervalCeilingMs=10,
    qualificationWarningsBlockMatchingClaims=True,minimumSamples=100000,occupancyReplicaTolerance=.05,
    occupancyBandTolerance=.05,lowCaffeine4kCeiling=.40,highCaffeine4kFloor=.75,highCaffeine4kCeiling=.95,
    p99BetweenPassCeiling=1.25,p999BetweenPassCeiling=1.5,bootstrapResamples=50000,familyComparisons=32,familyAlpha=.05,descriptiveConfidence=.95,
    floorRules={k:FLOOR_RULES[k] for k in ('version','timerMedianToEveryopMedianCeiling',
        'supplyMedianToSampleMedianCeiling','nativeReadMedianCeilingMs','floorReplicas')},initialMemoryReadinessRule=AVAILABLE_MEMORY_RULE,
    claimScope='conditional-on-recording-regime',coherence='Report disagreement; prohibit a pooled/unconditional claim',
    stageInvocationCounts=COUNTS,thermalRule=evidence.THERMAL_STARTUP_RULE,
    churnDropBudget=dict(version=CHURN_DROP_BUDGET_VERSION,maximumPerWindowBytes=32768,maximumDemandFraction=.001))


def options(stage):
    levels=[0] if stage in ('compiler-diagnostic','qualification','floors') else [0,288] if stage=='pilot' else RULES['liveMiB']
    return SimpleNamespace(stage=stage,heap_mib=512,residents=32768,churn_mib=32,live_mib=levels,
        payloads=[256,4096],seed=24301,warmups=30,measurements=8,repeats=1 if stage=='robustness' else 2,
        channels=['sample-calibration','every-operation'],conditioning=8,transport_warmup=True,
        maintenance_warmup=True,resume=False)


def work_grid(levels,passes,forks,seed=24301):
    cells=[(p,live) for p in (256,4096) for live in levels]
    random.Random(RULES['orderSeed']^seed).shuffle(cells);result=[]
    for block in range(1,passes+1):
        for payload,live in cells if block%2 else reversed(cells):
            channels=('sample-calibration','every-operation') if block%2 else ('every-operation','sample-calibration')
            for channel in channels:
                for fork in range(1,forks+1):
                    for backend in evidence.BACKENDS if (block+fork)%2==0 else reversed(evidence.BACKENDS):
                        p=dict(Backend=backend,Payload=payload,LiveBytes=live*1024**2,Residents=32768,HeapMiB=512,
                            ChurnBytesPerSecond=33554432,Seed=seed,Warmups=30,Conditioning=8,Measurements=8,
                            Channel=channel,Block=block,ForkOrdinal=fork,TransportWarmupVersion=evidence.TRANSPORT_WARMUP_VERSION,
                            LifecycleWarmupVersion=evidence.LIFECYCLE_WARMUP_VERSION)
                        label=f's{seed}-b{block}-{channel}-p{payload}-live{live}-f{fork}-{backend}'
                        result.append((label,calibration.command_properties(p)))
    return result


def base_grid(stage):
    if stage=='compiler-diagnostic':
        return [(label.replace('sample-calibration','compiler'),dict(p,Channel='compiler')) for label,p in work_grid([0],2,1)
                if p['Channel']=='sample-calibration']
    if stage=='qualification':return work_grid([0],2,1)
    if stage=='floors':return floor_grid(30,8,evidence.TRANSPORT_WARMUP_VERSION,evidence.LIFECYCLE_WARMUP_VERSION)
    if stage=='calibration':return work_grid(RULES['liveMiB'],2,1)
    if stage=='pilot':return work_grid([0,288],2,1)
    if stage=='campaign':return work_grid(RULES['liveMiB'],2,3)
    if stage=='robustness':return [slot for seed in RULES['robustnessSeeds'] for slot in work_grid(RULES['liveMiB'],1,1,seed)]
    if stage=='functional':
        labels=['smoke']+[f'retention-{b}-{n}' for b in evidence.BACKENDS for n in (512,8192)]
        labels += [f'{v}-{b}' for b in evidence.BACKENDS for v in ('long-operation','gc')]
        labels += ['observer-sample']+['observer-every-'+b for b in evidence.BACKENDS]+['supply-floor','timer-floor']
        return [(label,None) for label in labels]
    if stage=='pause':return [('gc-'+b,None) for b in evidence.BACKENDS]
    raise ValueError('Unknown final-study stage')


def grid(stage):
    return [(label,dict(p,ChurnDropBudgetVersion=CHURN_DROP_BUDGET_VERSION) if p is not None else None) for label,p in base_grid(stage)]


def declaration():
    return dict(rules=copy.deepcopy(RULES),stages={s:[dict(label=k,properties=p) for k,p in grid(s)] for s in STAGES},
        plan='docs/TAILCACHE_12_CONDITIONAL_FINAL_PROTOCOL_PLAN.md',
        amendments=['docs/TAILCACHE_12_STARTUP_THERMAL_PLAN.md','docs/TAILCACHE_12_CHURN_BUDGET_PLAN.md',
            'docs/TAILCACHE_12_QUALIFICATION_EVIDENCE_PLAN.md'])


def native_control_reference(identifier,current):
    path=evidence.REPORTS/identifier;result=json.loads((path/'result.json').read_text())
    expected=measurement_source_hash(evidence.ROOT)
    if (result.get('passed') is not True or result.get('sourceUnchanged') is not True
            or evidence.file_sha(path/'source.tar.gz')!=result['sourceArchiveSha256']
            or archive_measurement_source_hash(path/'source.tar.gz')!=expected
            or result.get('measurementSourceSha256')!=expected):raise ValueError('Native control source/acceptance changed')
    for name,wanted in (('inside',[]),('outside',['Native CPU outside benchmark scope exceeded 10% upper bound'])):
        with (path/(name+'.csv')).open() as stream:rows=[evidence.decode_host_row(r) for r in csv.DictReader(stream)]
        if evidence.host_gate(rows,native_required=True,native_version=2)[0]!=wanted:raise ValueError('Native control raw gate changed')
        if evidence.native_host.normalized_environment(evidence.native_host.environment_declaration(rows[0]))!=evidence.native_host.normalized_environment(evidence.native_host.environment_declaration(current)):
            raise ValueError('Native control host environment changed')
        for row in rows:evidence.thermal_values(row)
    cold=evidence.REPORTS/(identifier+'-cold-readiness.json')
    record=json.loads(cold.read_text());evidence.replay_cold_launch(cold,result['sourceSha256'],record['samples'][-1])
    names=['result.json','source.tar.gz','inside.csv','outside.csv']
    return dict(attempt=identifier,sha256={n:evidence.file_sha(path/n) for n in names},
        coldReadiness=cold.name,coldReadinessSha256=evidence.file_sha(cold),measurementSourceSha256=expected)


def reference(path):
    return dict(attempt=path.name,manifestSha256=evidence.file_sha(path/'manifest.json'),
        sourceArchiveSha256=evidence.file_sha(path/'source.tar.gz'),resultSha256=evidence.file_sha(path/'conditional-review.json'))


def verify_refs(parent,refs):
    for stage,ref in refs.items():
        path=parent/ref['attempt']
        if reference(path)!=ref:raise ValueError('Changed final-study prerequisite')
        manifest=json.loads((path/'manifest.json').read_text())
        result=json.loads((path/'conditional-review.json').read_text())
        if (stage not in STAGES or result.get('schemaVersion')!=VERSION or result.get('stage')!=stage
                or result.get('complete') is not True or result.get('sourceSha256')!=manifest['sourceSha256']
                or result.get('collectedInvocations')!=COUNTS[stage] or result.get('expectedInvocations')!=COUNTS[stage]
                or len(manifest['invocations'])!=COUNTS[stage]):
            raise ValueError('Incomplete/rejected final-study prerequisite')
        for inv in manifest['invocations']:calibration.verify_invocation(path,inv)


def verify_master(master,state,source):
    protocol=json.loads((master/'protocol.json').read_text());manifest=json.loads((master/'manifest.json').read_text())
    if (evidence.file_sha(master/'protocol.json')!=state['protocolSha256'] or protocol['declaration']!=declaration()
            or protocol['sourceSha256']!=source or manifest['sourceSha256']!=source
            or evidence.file_sha(master/'source.tar.gz')!=manifest['sourceArchiveSha256']
            or archive_measurement_source_hash(master/'source.tar.gz')!=protocol['measurementSourceSha256']):
        raise ValueError('Changed frozen final master protocol/source')
    if protocol.get('nativeControlRef')!=manifest.get('nativeControlRef'):
        raise ValueError('Changed frozen native control binding')
    if protocol.get('nativeControlRef'):
        ref=protocol['nativeControlRef'];path=master.parent/ref['attempt']
        if (any(evidence.file_sha(path/name)!=value for name,value in ref['sha256'].items())
                or evidence.file_sha(master.parent/ref['coldReadiness'])!=ref['coldReadinessSha256']):
            raise ValueError('Changed native control artifacts')


def host_facts(attempt,manifest,inv):
    raw=calibration.verify_invocation(attempt,inv)
    with (attempt/inv['label']/'host.csv').open() as stream:hosts=[evidence.decode_host_row(r) for r in csv.DictReader(stream)]
    thermal=evidence.replay_settled_thermal(manifest,raw,hosts,attempt/inv['label']/'thermal-readiness.json')
    original=list(thermal['originalReasons'])+inv.get('hostMonitorErrors',[])
    reasons=list(thermal['effectiveReasons'])+inv.get('hostMonitorErrors',[])
    windows=evidence.measurement_windows(raw);intervals=evidence.native_host.cpu_intervals(hosts)
    selected=[r for r in intervals if not windows or any(r['endNs']>=a-10_000_000_000 and r['startNs']<=b for a,b in windows)]
    if not selected:raise ValueError('Missing final-study CPU intervals')
    upper=max(r['outsideUpperPercent'] for r in selected);warnings,fatal=facts.classify(reasons,upper)
    if thermal['startupExceptionUsed']:warnings.append(evidence.THERMAL_STARTUP_WARNING)
    return dict(label=inv['label'],inputs=inv['properties'],strictReasons=original,effectiveReasons=reasons,thermalReview=thermal,warnings=warnings,
        fatalReasons=fatal,finalPolicyUsable=not fatal,primaryEndpointUseAllowed=False,
        outsideCpuUpperPercent=upper,hostWindowStartNs=hosts[0]['monotonicNs'],hostWindowEndNs=hosts[-1]['monotonicNs'])


def apply_policy(original,stage):
    row=copy.deepcopy(original)
    if stage=='qualification':
        row['qualificationCompilerReasons']=[r for r in row['strictReasons'] if r in
            ('compiler total exceeds 80 ms','compiler iteration exceeds 10 ms')]
        row['qualificationCompilerPass']=not row['qualificationCompilerReasons']
    row['finalPolicyUsable']=not row['fatalReasons'];row['conditionalEndpointUseAllowed']=row['finalPolicyUsable']
    if stage=='qualification':
        row['conditionalEndpointUseAllowed'] &= not row['strictReasons'] and not row['warnings']
    return row


def allocation_summary(raw,channel):
    directory=raw/('every-operation' if channel=='timer' else channel)
    sidecar=(directory/'worker/iterations.csv') if channel in ('timer','every-operation') else next(directory.glob('iterations-*.csv'))
    with sidecar.open() as stream:rows=[r for r in csv.DictReader(stream) if r['phase']=='MEASUREMENT']
    operations=sum(int(r['operations']) for r in rows)
    elapsed=sum(int(r.get('envelopeEndNs',r.get('endNs')))-int(r.get('envelopeStartNs',r.get('startNs'))) for r in rows)/1e9
    worker=sum(int(r['workerJvmAllocatedBytes']) for r in rows);churn=sum(int(r['churnJvmAllocatedBytes']) for r in rows)
    if operations<=0 or elapsed<=0 or worker<0 or churn<0:raise ValueError('Invalid allocation exposure')
    return dict(operations=operations,measurementSeconds=elapsed,workerAllocatedBytes=worker,churnAllocatedBytes=churn,
        workerBytesPerOperation=worker/operations,totalObservedBytesPerOperation=(worker+churn)/operations,
        workerBytesPerSecond=worker/elapsed,totalObservedBytesPerSecond=(worker+churn)/elapsed,
        limits='Per-thread JVM allocation counters including observer/window/instrumentation work; not process-wide profiler allocation.')


def read_row(path,manifest,inv,runtime,trace,helper):
    if inv['properties']['Channel']!='compiler':
        summary,runtime,trace=facts.audit_row(path,dict(manifest,hdrVerifier=helper),inv,runtime,trace)
        overhead=[r for r in summary['strictReasons'] if r=='Native observer median read duration exceeded 10 ms']
    else:
        raw=calibration.verify_invocation(path,inv);p=inv['properties']
        record=json.loads((raw/'compiler/results.json').read_text())[0]
        actual={k:record[k] for k in ('jmhVersion','jdkVersion','vmName','vmVersion')}
        if runtime is None:runtime=actual
        text=(raw/'compiler/jmh.txt').read_text()+(path/inv['label']/'gradle.log').read_text()
        traces=set(evidence.re.findall(r'traceSha256=([0-9a-f]{64})',text))
        if len(traces)!=1:raise ValueError('Missing compiler diagnostic trace')
        actual_trace=next(iter(traces))
        if trace is not None and trace!=actual_trace:raise ValueError('Compiler diagnostic trace changed')
        trace=actual_trace
        summary=facts.jmh_fork_summary(raw,'compiler',dict(p,ConsoleFile=str(path/inv['label']/'gradle.log')),trace,runtime)
        summary['diagnosticCompilerXml']=True;overhead=[]
    host=host_facts(path,manifest,inv);reasons=list(summary['rejectionReasons'])+host['effectiveReasons']+overhead
    warnings,fatal=facts.classify(reasons,host['outsideCpuUpperPercent'])
    if host['thermalReview']['startupExceptionUsed']:warnings.append(evidence.THERMAL_STARTUP_WARNING)
    budget=summary.get('churnDropBudgetSummary',{});original_drops=[]
    if budget.get('totalDroppedBytes',0):
        warnings.append(CHURN_DROP_WARNING)
        if budget.get('conditioningDroppedBytes',0):original_drops.append('Original exact-zero conditioning churn gate failed')
        if budget.get('measurementDroppedBytes',0):original_drops.append('Original exact-zero measured churn gate failed')
    strict=list(summary['rejectionReasons'])+host['strictReasons']+overhead+original_drops
    row=dict(summary,**host);row.update(strictReasons=strict,strictQualityPass=not strict,originalExactZeroDropReasons=original_drops,
        effectiveReasons=reasons,warnings=warnings,fatalReasons=fatal,finalPolicyUsable=not fatal,primaryEndpointUseAllowed=False)
    return row,runtime,trace


def audit_stage(path,stage,helper):
    manifest=json.loads((path/'manifest.json').read_text());frozen=json.loads((path/'final-declaration.json').read_text())
    expected=grid(stage)
    if (frozen['protocol']!=declaration() or frozen['stage']!=stage or frozen['sourceSha256']!=manifest['sourceSha256']
            or manifest['stage']!=('validate' if stage=='functional' else stage)
            or set(frozen['prerequisites'])!=set(STAGES[:STAGES.index(stage)])
            or evidence.file_sha(path/'source.tar.gz')!=manifest['sourceArchiveSha256']
            or archive_measurement_source_hash(path/'source.tar.gz')!=frozen['measurementSourceSha256']
            or len(manifest['invocations'])>len(expected)):
        raise ValueError('Changed final stage declaration/source')
    verify_refs(path.parent,frozen['prerequisites'])
    for ref in frozen['prerequisites'].values():
        prior=json.loads((path.parent/ref['attempt']/'manifest.json').read_text())
        if prior['sourceSha256']!=manifest['sourceSha256']:raise ValueError('Final stages used different full source')
    rows=[];runtime=None;traces={}
    for inv,(label,p) in zip(manifest['invocations'],expected):
        if inv['label']!=label or (p is not None and inv['properties']!=p):raise ValueError('Changed final stage order/inputs')
        if stage in ('functional','pause'):row=host_facts(path,manifest,inv)
        else:
            seed=p['Seed'];row,runtime,trace=read_row(path,manifest,inv,runtime,traces.get(seed),helper)
            if p['Channel']!='timer':traces[seed]=trace
            row=apply_policy(row,stage)
            row['allocation']=allocation_summary(evidence.raw_directory(path,inv),p['Channel'])
        rows.append(row)
    complete=len(rows)==len(expected) and all(r['finalPolicyUsable'] for r in rows)
    mechanical=None
    if stage in ('functional','pause') and len(rows)==len(expected):
        evidence.replay(path);audit=json.loads((path/'replayed-audit.json').read_text())
        mechanical=audit.get('mechanicalPass',audit['functionalPass']);complete &= mechanical
    proof=dict(manifest,initialQuietRef=frozen['initialQuietRef'],initialMemoryReadinessRule=AVAILABLE_MEMORY_RULE,
        nativeHostRetryPolicy=native_retry.declare_policy(2))
    quiet=native_retry.verify_initial_quiet(path,proof,rows)
    result=dict(schemaVersion=VERSION,stage=stage,sourceSha256=manifest['sourceSha256'],measurementSourceSha256=frozen['measurementSourceSha256'],
        complete=bool(complete),mechanicalPass=mechanical,collectedInvocations=len(rows),expectedInvocations=len(expected),
        runtimeIdentity=runtime,
        observations=rows,initialQuietReplay=quiet,warningCounts=dict(collections.Counter(w for r in rows for w in r['warnings'])),
        primaryEndpointUseAllowed=False,conditionalEndpointUseAllowed=bool(complete))
    if stage=='calibration':result['pressureBands']=pressure_bands(rows)
    if stage=='qualification':
        result['qualificationEvidence']=qualification_evidence(rows)
        result['jitQualified']=all(r['compilerQualified'] for r in result['qualificationEvidence'])
        result['conditionalEndpointUseAllowed']=bool(complete) and all(r['conditionalQualified'] for r in result['qualificationEvidence'])
    if stage=='pilot' and len(rows)==len(expected):result['betweenPassVariation']=pilot_variation(rows)
    return result


def qualification_evidence(rows):
    result=[]
    for channel in ('sample-calibration','every-operation'):
        for backend in evidence.BACKENDS:
            for payload in (256,4096):
                chosen=[r for r in rows if (r['inputs']['Channel'],r['inputs']['Backend'],r['inputs']['Payload'])==(channel,backend,payload)]
                complete=len(chosen)==2 and {r['inputs']['Block'] for r in chosen}=={1,2}
                issues=[] if complete else ['Missing independent two-pass qualification evidence']
                for r in chosen:
                    issues.extend(r['label']+': qualification: '+x for x in dict.fromkeys(r['strictReasons']+r['warnings']+r['fatalReasons']))
                compiler_reasons=[x for r in chosen for x in r['strictReasons'] if x in
                    ('compiler total exceeds 80 ms','compiler iteration exceeds 10 ms')]
                result.append(dict(channel=channel,backend=backend,payloadBytes=payload,complete=complete,
                    originalCompilerTotalCeilingMs=80,originalCompilerIntervalCeilingMs=10,
                    compilerQualified=complete and not compiler_reasons,conditionalQualified=complete and not issues,
                    invocations=[r['label'] for r in chosen],compilerRejectionReasons=compiler_reasons,
                    claimLimitations=list(dict.fromkeys(issues))))
    return result


def qualification_limitations(qualification,channel,payload):
    selected=[r for r in qualification if r['channel']==channel and r['payloadBytes']==payload]
    if len(selected)!=2 or {r['backend'] for r in selected}!=set(evidence.BACKENDS):
        raise ValueError('Missing qualification comparison cell')
    return [r['backend']+': '+issue for r in selected for issue in r['claimLimitations']]


def pressure_bands(rows):
    result=[]
    for channel in ('sample-calibration','every-operation'):
        for backend in evidence.BACKENDS:
            for payload in (256,4096):
                previous=None
                for live in RULES['liveMiB']:
                    values=[r.get('gc',r).get('postGcUsedHeapMedianFraction') for r in rows if
                        (r['inputs']['Channel'],r['inputs']['Backend'],r['inputs']['Payload'],r['inputs']['LiveBytes'])==
                        (channel,backend,payload,live*1024**2)]
                    issues=[];valid=[v for v in values if v is not None]
                    supporting=[r for r in rows if (r['inputs']['Channel'],r['inputs']['Backend'],r['inputs']['Payload'],r['inputs']['LiveBytes'])==
                        (channel,backend,payload,live*1024**2)]
                    issues += [r['label']+': calibration warning: '+w for r in supporting for w in r['warnings']]
                    median=statistics.median(valid) if valid else None
                    if len(valid)!=2:issues.append('Missing independent occupancy exposure')
                    if len(valid)==2 and max(valid)-min(valid)>.05:issues.append('Occupancy replicas differ by more than5 percentage points')
                    if median is not None and previous is not None and median<previous:issues.append('Occupancy is not monotonic')
                    if backend=='CAFFEINE' and payload==4096 and median is not None:
                        if live==0 and median>.4:issues.append('Low pressure coverage exceeded40% used heap')
                        if live==288 and not .75<=median<=.95:issues.append('High pressure coverage outside75–95% used heap')
                    result.append(dict(channel=channel,backend=backend,payloadBytes=payload,liveMiB=live,median=median,
                        replicas=values,warnings=issues));previous=median
    return result


def analyse_campaign(rows,bands,floor_rows,qualification_rows):
    qualification=qualification_evidence(qualification_rows)
    converted=[dict(r,accepted=r['finalPolicyUsable'],inputs=dict(r['inputs'],Channel='sample' if r['inputs']['Channel']=='sample-calibration'
        else r['inputs']['Channel'])) for r in rows]
    selections={'24301':{str(p):[n*1024**2 for n in RULES['liveMiB']] for p in (256,4096)}}
    comparisons=legacy_analysis.comparison_rows(converted,{},selections)
    floor_ratios=[]
    for row in rows:
        if row['inputs']['LiveBytes']!=0:continue
        p=row['inputs'];timer=p['Channel']=='every-operation'
        matched_rows=[r for r in floor_rows if r['finalPolicyUsable'] and
            (r['inputs']['Channel']=='timer' if timer else r['inputs']['Channel']=='floor'
                and r['inputs']['Backend']==p['Backend'] and r['inputs']['Payload']==p['Payload'])]
        matched=[r['servicePercentilesNs']['50'] for r in matched_rows]
        if len(matched)!=2:raise ValueError('Missing independent matched floor replicas')
        ratio=max(matched)/row['servicePercentilesNs']['50']
        ceiling=FLOOR_RULES['timerMedianToEveryopMedianCeiling' if timer else 'supplyMedianToSampleMedianCeiling']
        floor_ratios.append(dict(label=row['label'],ratio=ratio,ceiling=ceiling,warning=ratio>ceiling,
            floorQualityWarnings=[r['label']+': '+w for r in matched_rows for w in r['warnings']]))
    floor_bad={r['label'] for r in floor_ratios if r['warning']}
    floor_bad.update(r['label'] for r in floor_ratios if r['floorQualityWarnings'])
    floor_bad_keys={(r['inputs']['Channel'],r['inputs']['Backend'],r['inputs']['Payload']) for r in rows if r['label'] in floor_bad}
    for comp in comparisons:
        channel='sample-calibration' if comp['channel']=='sample' else comp['channel']
        chosen=[r for r in rows if r['inputs']['Channel']==channel and r['inputs']['Payload']==comp['payloadBytes']
            and r['inputs']['LiveBytes']==comp['applicationLiveBytes']]
        issues=qualification_limitations(qualification,channel,comp['payloadBytes'])
        issues += [r['label']+': '+w for r in chosen for w in r['warnings']]
        for backend in evidence.BACKENDS:
            b=next(b for b in bands if (b['channel'],b['backend'],b['payloadBytes'],b['liveMiB'])==
                (channel,backend,comp['payloadBytes'],comp['applicationLiveBytes']//1024**2))
            issues += [backend+': '+w for w in b['warnings']]
            for r in chosen:
                if r['inputs']['Backend']==backend:
                    value=r.get('gc',r).get('postGcUsedHeapMedianFraction')
                    if value is None or b['median'] is None or abs(value-b['median'])>.05:
                        issues.append(r['label']+': occupancy outside calibrated±5 point band')
        issues+=comp['varianceRejectionReasons']
        for r in chosen:
            if (r['inputs']['Channel'],r['inputs']['Backend'],r['inputs']['Payload']) in floor_bad_keys:
                issues.append(r['label']+': matched low-pressure floor ratio/quality limitation')
        comp['runVariation']={}
        for backend in evidence.BACKENDS:
            comp['runVariation'][backend]={}
            for endpoint in ('99','99.9'):
                values=[r['servicePercentilesNs'][endpoint] for r in chosen if r['inputs']['Backend']==backend]
                comp['runVariation'][backend][endpoint]=dict(forks=len(values),valuesNs=values,
                    medianNs=statistics.median(values),minimumNs=min(values),maximumNs=max(values),
                    coefficientOfVariation=statistics.stdev(values)/statistics.mean(values))
        comp['claimLimitations']=list(dict.fromkeys(issues));comp['resolvedConditionalClaimAllowed']=comp['complete'] and not issues
        for ratio in comp['ratios'].values():
            ratio['rawBootstrapDirection']=ratio['direction']
            ratio['conditionalDirection']=ratio['direction'] if comp['resolvedConditionalClaimAllowed'] else 'unresolved'
            ratio['direction']=ratio['conditionalDirection']
    disagreements=[]
    for payload in (256,4096):
        for live in RULES['liveMiB']:
            pair=[c for c in comparisons if c['payloadBytes']==payload and c['applicationLiveBytes']==live*1024**2]
            for endpoint in ('99','99.9'):
                directions=[c['ratios'].get(endpoint,{}).get('conditionalDirection','unresolved') for c in pair]
                if set(directions)=={'chronicle-lower','caffeine-lower'}:
                    disagreements.append(dict(payloadBytes=payload,liveMiB=live,percentile=endpoint,interpretation='Opposite conditional directions; no joint claim'))
    return dict(comparisons=comparisons,channelDisagreements=disagreements,floorRatios=floor_ratios,
        limits=['Two outer passes yield coarse nominal bootstrap uncertainty.',
            'Recording regimes and robustness seeds are not pooled; no unconditional crossover claim.'])


def robustness_summary(rows,qualification_rows):
    qualification=qualification_evidence(qualification_rows)
    result=[]
    for seed in RULES['robustnessSeeds']:
        for payload in (256,4096):
            for live in RULES['liveMiB']:
                for channel in ('sample-calibration','every-operation'):
                    chosen={r['inputs']['Backend']:r for r in rows if (r['inputs']['Seed'],r['inputs']['Payload'],
                        r['inputs']['LiveBytes'],r['inputs']['Channel'])==(seed,payload,live*1024**2,channel)}
                    if set(chosen)!=set(evidence.BACKENDS):raise ValueError('Missing robustness cell')
                    limits=qualification_limitations(qualification,channel,payload)
                    result.append(dict(seed=seed,payloadBytes=payload,liveMiB=live,channel=channel,
                        chronicleToCaffeine={p:chosen['CHRONICLE_IN_MEMORY']['servicePercentilesNs'][p]/chosen['CAFFEINE']['servicePercentilesNs'][p]
                            for p in ('99','99.9')},warnings={b:r['warnings'] for b,r in chosen.items()},
                        qualificationLimitations=limits,conditionalSensitivityUsable=not limits and not any(r['warnings'] for r in chosen.values()),
                        confidenceInterval=None))
    return result


def condition_acceptance(comparisons):
    rows=[]
    for payload in (256,4096):
        for live in RULES['liveMiB']:
            selected=[c for c in comparisons if c['payloadBytes']==payload and c['applicationLiveBytes']==live*1024**2]
            if len(selected)!=2:raise ValueError('Missing final condition comparison')
            for backend in evidence.BACKENDS:
                rows.append(dict(backend=backend,payloadBytes=payload,liveMiB=live,
                    originalUnconditionalProtocolAccepted=False,
                    originalRejectionReasons=['Original joint observer-coherence/qualification protocol remains unqualified; do not substitute this revised protocol.'],
                    conditionalRegimes={c['channel']:dict(accepted=c['resolvedConditionalClaimAllowed'],reasons=c['claimLimitations']) for c in selected}))
    return rows


def pilot_variation(rows):
    result=[]
    for channel in ('sample-calibration','every-operation'):
        for payload in (256,4096):
            for live in (0,288):
                for backend in evidence.BACKENDS:
                    chosen=[r for r in rows if (r['inputs']['Channel'],r['inputs']['Payload'],r['inputs']['LiveBytes'],r['inputs']['Backend'])
                        ==(channel,payload,live*1024**2,backend)]
                    if len(chosen)!=2:raise ValueError('Incomplete independent pilot passes')
                    ratios={p:max(r['servicePercentilesNs'][p] for r in chosen)/min(r['servicePercentilesNs'][p] for r in chosen)
                        for p in ('99','99.9')}
                    result.append(dict(channel=channel,payloadBytes=payload,liveMiB=live,backend=backend,betweenPassRatios=ratios,
                        warnings=[p for p,ceiling in (('99',1.25),('99.9',1.5)) if ratios[p]>ceiling],confidenceInterval=None))
    return result


def archive_files(files,path):
    from tailcache12_archive import file_digest,stream_digest,advise
    inventory=[]
    with tarfile.open(path,'x:gz',compresslevel=1) as archive:
        for p in sorted(files):
            if p.is_symlink() or not p.resolve().is_relative_to(evidence.REPORTS.resolve()):raise ValueError('External archive dependency')
            name=p.relative_to(evidence.ROOT).as_posix();inventory.append(dict(path=name,bytes=p.stat().st_size,sha256=file_digest(p)))
            archive.add(p,arcname=name,recursive=False);advise(p)
    expected={r['path']:r for r in inventory};seen=set()
    with tarfile.open(path,'r:gz') as archive:
        for member in archive:
            if not member.isfile() or member.name not in expected or member.name in seen:raise ValueError('Unexpected archive member')
            entry=expected[member.name]
            with archive.extractfile(member) as stream:
                if member.size!=entry['bytes'] or stream_digest(stream)!=entry['sha256']:raise ValueError('Archive checksum mismatch')
            seen.add(member.name)
    if seen!=set(expected):raise ValueError('Missing archive member')
    receipt=dict(path=path.name,bytes=path.stat().st_size,sha256=file_digest(path),verifiedMembers=len(seen),historicalEvidencePooled=False)
    advise(path);return inventory,receipt


def export(master,results,destination):
    if destination.exists():raise ValueError('Final dataset exists; no overwrite')
    if set(results)!=set(STAGES) or any(not r['complete'] for r in results.values()):raise ValueError('Cannot export incomplete final study')
    if destination.resolve().is_relative_to(evidence.ROOT/'build'):raise ValueError('Final export must be outside build')
    state=json.loads((master/'state.json').read_text());protocol=json.loads((master/'protocol.json').read_text())
    verify_master(master,state,protocol['sourceSha256'])
    verify_refs(master.parent,state['completedStages'])
    # Reconstruct final acceptance from each stage's actual raw controls/recordings.
    results={stage:audit_stage(master.parent/(master.name+'-'+stage),stage,protocol['hdrVerifier']) for stage in STAGES}
    if any(not r['complete'] for r in results.values()):raise ValueError('Fresh raw replay rejects final export')
    bands=pressure_bands(results['calibration']['observations'])
    qualification_rows=results['qualification']['observations']
    qualification=qualification_evidence(qualification_rows)
    analysis=analyse_campaign(results['campaign']['observations'],bands,results['floors']['observations'],qualification_rows)
    dataset=dict(schemaVersion=VERSION,taskComplete=False,requiresResearcherReview=True,analysisReady=True,
        reportingScope=RULES['claimScope'],originalPrimaryProtocolQualified=False,stages=results,pressureBands=bands,
        campaign=analysis,primaryConditionAcceptance=condition_acceptance(analysis['comparisons']),
        qualificationEvidence=qualification,qualificationJitQualified=all(r['compilerQualified'] for r in qualification),
        robustness=robustness_summary(results['robustness']['observations'],qualification_rows),rules=RULES,
        limits=['Coarse uncertainty from two outer passes; nominal32-comparison correction.',
            'Single robustness fork per cell/seed is descriptive sensitivity only.',
            'Warning/variance/exposure-limited comparisons are unresolved; no pooled cross-regime claim.',
            'Qualification compiler thresholds remain80ms total/10ms interval; failures block every matching pressure/seed claim, not mechanical collection.',
            'Single worker, periodic uniform95/5, fixed512MiB G1 and in-memory Chronicle; no persisted cold/open claim.'])
    destination.mkdir(parents=True);evidence.save(destination/'dataset.json',dataset)
    shutil.copyfile(master/'protocol.json',destination/'protocol.json')
    with (destination/'coverage.csv').open('x',newline='') as stream:
        columns=['stage','label','backend','payloadBytes','liveMiB','seed','channel','block','fork','p99Ns','p999Ns','warnings','finalPolicyUsable']
        writer=csv.DictWriter(stream,columns);writer.writeheader()
        for stage,result in results.items():
            for row in result['observations']:
                p=row['inputs'];values=[stage,row['label'],p.get('Backend',p.get('Backends')),p.get('Payload',p.get('Payloads')),
                    p.get('LiveBytes',0)/1024**2,p.get('Seed'),p.get('Channel'),p.get('Block'),p.get('ForkOrdinal'),
                    row.get('servicePercentilesNs',{}).get('99'),row.get('servicePercentilesNs',{}).get('99.9'),
                    json.dumps(row['warnings']),row['finalPolicyUsable']]
                writer.writerow(dict(zip(columns,values)))
    roots=[master,master.parent/protocol['hdrVerifier']['setup']]
    extras=set()
    roots.append(master.parent/protocol['nativeControlRef']['attempt'])
    extras.add(master.parent/protocol['nativeControlRef']['coldReadiness'])
    for stage in STAGES:
        p=master.parent/(master.name+'-'+stage);m=json.loads((p/'manifest.json').read_text());f=json.loads((p/'final-declaration.json').read_text())
        quiet=master.parent/f['initialQuietRef']['attempt'];roots.extend([p,quiet])
        extras.add(master.parent/(quiet.name+'-cache-preparation.json'))
        extras.add(master.parent/json.loads((quiet/'host-preparation.json').read_text())['inventoryFile'])
        roots.extend(evidence.raw_directory(p,i) for i in m['invocations'])
    files=extras|{p for root in roots for p in root.rglob('*') if p.is_file()}
    inventory,receipt=archive_files(files,destination/'raw-sources.tar.gz')
    evidence.save(destination/'archive-inventory.json',inventory);evidence.save(destination/'archive.json',receipt)
    (destination/'README.md').write_text('# Task12 observer-conditional final dataset\n\nRead dataset.json/coverage.csv for all nine stages, every original strict reason, warnings, pressure/variance/floor limitations, regime-specific confidence intervals and separate seed sensitivity. '
        'This is an explicitly versioned replacement protocol; the original unconditional coherence gate is not claimed to pass. '
        'The verified archive preserves all raw/source/protocol/control/quiet dependencies. Researcher outcome review is required before task completion.\n')
    return dataset,receipt


def run(prefix,output,native_control):
    master=evidence.REPORTS/prefix;setup=evidence.REPORTS/(prefix+'-setup')
    paths=[evidence.REPORTS/(prefix+'-'+s) for s in STAGES]
    if any(p.exists() for p in [master,setup,*paths]) or output.exists():raise ValueError('Retained final study exists; inspect, do not duplicate')
    if any(os.environ.get(k) for k in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS')):raise ValueError('Require clean VM options')
    host=evidence.host_snapshot()
    if os.environ.get('TAILCACHE_REQUIRE_NATIVE_HOST')!='1' or host.get('nativeScopeQualified')!=1:raise ValueError('Require exclusive native scope')
    if shutil.disk_usage(evidence.ROOT).free<4*1024**3:raise ValueError('Require4GiB disk')
    control_ref=native_control_reference(native_control,host)
    os.environ['TAILCACHE_THERMAL_READINESS']=evidence.THERMAL_STARTUP_RULE['version']
    source=evidence.source_hash();helper=facts.compile_verifier(setup)
    master_manifest=calibration.prepare(master,options('conditional-master'),[])
    master_manifest['nativeControlRef']=control_ref;evidence.save(master/'manifest.json',master_manifest)
    protocol=dict(declaration=declaration(),sourceSha256=source,measurementSourceSha256=measurement_source_hash(evidence.ROOT),hdrVerifier=helper,nativeControlRef=control_ref)
    evidence.save(master/'protocol.json',protocol)
    state=dict(complete=False,taskComplete=False,protocolSha256=evidence.file_sha(master/'protocol.json'),completedStages={},currentStage=None)
    evidence.save(master/'state.json',state);results={}
    try:
        for stage,path in zip(STAGES,paths):
            if evidence.source_hash()!=source:raise ValueError('Source changed during final study')
            verify_master(master,state,source)
            verify_refs(evidence.REPORTS,state['completedStages']);state['currentStage']=stage;evidence.save(master/'state.json',state)
            quiet=evidence.REPORTS/(path.name+'-quiet');prep=evidence.REPORTS/(quiet.name+'-cache-preparation.json')
            cache=prepare_file_cache(prep,include_build_outputs=True,stream_inventory=True,available_memory=True)
            if not run_preflight(quiet,120,300)['quietPass']:raise ValueError('Final-stage initial quiet rejected')
            evidence.save(quiet/'host-preparation.json',cache)
            initial=native_retry.initial_quiet_reference(quiet,dict(sourceSha256=source),native_retry.declare_policy(2),evidence.host_snapshot())
            frozen=dict(protocol=declaration(),stage=stage,sourceSha256=source,measurementSourceSha256=protocol['measurementSourceSha256'],
                initialQuietRef=initial,prerequisites=copy.deepcopy(state['completedStages']))
            if stage in ('functional','pause'):
                # Freeze the parent reference before the original diagnostic script launches its first JVM.
                evidence.save(master/(stage+'-prelaunch.json'),frozen)
                proof=dict(sourceSha256=source,initialQuietRef=initial,initialMemoryReadinessRule=AVAILABLE_MEMORY_RULE,
                    nativeHostRetryPolicy=native_retry.declare_policy(2),nativeEnvironmentDeclaration=evidence.native_host.environment_declaration(evidence.host_snapshot()))
                native_retry.verify_initial_quiet(path,proof,before_launch=True)
                command=[sys.executable,str(evidence.ROOT/'scripts/tailcache12.py'),'validate' if stage=='functional' else 'pause',path.name,
                    '--transport-warmup','--maintenance-warmup']
                result=subprocess.run(command,cwd=evidence.ROOT)
                # A strict-host-only nonzero exit may still be mechanically valid under this new policy.
                if not (path/'manifest.json').exists():raise ValueError('Functional diagnostic failed before retained manifest')
                evidence.save(path/'final-declaration.json',frozen)
            else:
                slots=grid(stage);m=calibration.prepare(path,options(stage),slots)
                m.update(hdrVerifier=helper,initialMemoryReadinessRule=AVAILABLE_MEMORY_RULE,
                    nativeEnvironmentVersion=1,nativeEnvironmentDeclaration=evidence.native_host.environment_declaration(evidence.host_snapshot()))
                m['inputs']['passes']=1 if stage=='robustness' else 2
                m['inputs']['forksPerPass']=3 if stage=='campaign' else 1
                if stage=='robustness':
                    m['inputs'].pop('seed');m['inputs']['seeds']=list(RULES['robustnessSeeds'])
                evidence.save(path/'manifest.json',m);evidence.save(path/'final-declaration.json',frozen)
                proof=dict(m,initialQuietRef=initial,nativeHostRetryPolicy=native_retry.declare_policy(2))
                native_retry.verify_initial_quiet(path,proof,before_launch=True)
                runtime=None;traces={}
                for label,p in slots:
                    task='tailCache12Compiler' if p['Channel']=='compiler' else 'tailCache12SupplyFloor' if p['Channel']=='floor' else 'tailCache12SampleCalibration' if p['Channel']=='sample-calibration' else 'tailCache12EveryOperation'
                    evidence.invoke(path,m,label,task,p)
                    row,runtime,trace=read_row(path,m,m['invocations'][-1],runtime,traces.get(p['Seed']),helper)
                    if p['Channel']!='timer':traces[p['Seed']]=trace
                    fatal=apply_policy(row,stage)['fatalReasons']
                    if fatal:raise ValueError('Hard final-study gate: '+str(fatal))
            reviewed=audit_stage(path,stage,helper);evidence.save(path/'conditional-review.json',reviewed)
            if not reviewed['complete']:raise ValueError('Incomplete or hard-rejected stage: '+stage)
            if reviewed['runtimeIdentity'] is not None:
                if state.get('runtimeIdentity') is not None and state['runtimeIdentity']!=reviewed['runtimeIdentity']:
                    raise ValueError('Exact JVM/JMH identity changed between final stages')
                state['runtimeIdentity']=reviewed['runtimeIdentity']
            results[stage]=reviewed;state['completedStages'][stage]=reference(path);evidence.save(master/'state.json',state)
            print('FINAL_STAGE_COMPLETE '+stage+' '+str(reviewed['collectedInvocations'])+' warnings='+str(reviewed['warningCounts']),flush=True)
        dataset,archive=export(master,results,output)
        state.update(complete=True,requiresResearcherReview=True,output=str(output),archive=archive,currentStage=None)
        evidence.save(master/'state.json',state)
        print('FINAL_DATASET_EXPORTED '+str(output),flush=True)
    except Exception as error:
        state['terminalFailure']=dict(reason=f'{type(error).__name__}: {error}',utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        evidence.save(master/'state.json',state);raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('prefix');parser.add_argument('--output',type=pathlib.Path,required=True)
    parser.add_argument('--native-control',required=True)
    args=parser.parse_args()
    if any(not evidence.re.fullmatch('[A-Za-z0-9._-]+',x) for x in (args.prefix,args.native_control)):parser.error('Invalid final-study prefix')
    run(args.prefix,args.output.resolve(),args.native_control)


if __name__=='__main__':main()
