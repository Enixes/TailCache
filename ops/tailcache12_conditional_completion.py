#!/usr/bin/env python3
"""Complete only the unattempted suffix; retain original stopping-rule rejection."""
import argparse
import collections
import copy
import csv
import datetime
import json
import os
import pathlib
import shutil
import statistics
import sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import tailcache12_conditional as c

VERSION='tailcache12-completion-supplement-v1'
CPU_REJECTION='Exploratory outside CPU exceeded25% upper bound'
PARENT='native-final-conditional-20261107-005'
OFFSET=143
NATIVE='native-final-startup-thermal-control-20261107-002'


def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def load(path):return json.loads(path.read_text())
def digest(path):return c.evidence.file_sha(path)
def save(path,value):c.evidence.save(path,value)


def allowed_rejection(row):
    return bool(row['fatalReasons']) and set(row['fatalReasons'])=={CPU_REJECTION}


def validate_suffix(invocations,stage,offset):
    slots=c.grid(stage)[offset:]
    if len(invocations)>len(slots):raise ValueError('Extra completion invocation')
    for inv,(label,p) in zip(invocations,slots):
        if inv['label']!=label or inv['properties']!=p:raise ValueError('Changed or duplicate suffix slot')
    return slots


def mark(row,segment):
    row=copy.deepcopy(row);row['executionSegment']=segment
    row['excludedFromStatistics']=not row['finalPolicyUsable']
    return row


def replay_rows(path,stage,helper,segment,offset=0,runtime=None,trace=None):
    manifest=load(path/'manifest.json');validate_suffix(manifest['invocations'],stage,offset)
    if digest(path/'source.tar.gz')!=manifest['sourceArchiveSha256']:raise ValueError('Changed fragment source archive')
    rows=[];traces={} if trace is None else dict(trace)
    for inv in manifest['invocations']:
        p=inv['properties'];row,runtime,actual=c.read_row(path,manifest,inv,runtime,traces.get(p['Seed']),helper)
        traces[p['Seed']]=actual;row=c.apply_policy(row,stage)
        if row['fatalReasons'] and not allowed_rejection(row):raise ValueError('Unhandled hard completion rejection: '+str(row['fatalReasons']))
        row['allocation']=c.allocation_summary(c.evidence.raw_directory(path,inv),p['Channel'])
        rows.append(mark(row,segment))
    return rows,runtime,traces


def analyse(rows,bands,floors,qualification):
    valid=[r for r in rows if r['finalPolicyUsable']]
    converted=[dict(r,accepted=True,inputs=dict(r['inputs'],Channel='sample' if r['inputs']['Channel']=='sample-calibration'
        else r['inputs']['Channel'])) for r in valid]
    selections={'24301':{str(p):[n*1024**2 for n in c.RULES['liveMiB']] for p in (256,4096)}}
    comparisons=c.legacy_analysis.comparison_rows(converted,{},selections)
    qual=c.qualification_evidence(qualification);floor_ratios=[];floor_bad=set()
    for r in valid:
        p=r['inputs']
        if p['LiveBytes']!=0:continue
        timer=p['Channel']=='every-operation'
        matched=[f for f in floors if f['finalPolicyUsable'] and
            (f['inputs']['Channel']=='timer' if timer else f['inputs']['Channel']=='floor'
                and f['inputs']['Backend']==p['Backend'] and f['inputs']['Payload']==p['Payload'])]
        if len(matched)!=2:raise ValueError('Missing two matched floor replicas')
        ratio=max(f['servicePercentilesNs']['50'] for f in matched)/r['servicePercentilesNs']['50']
        ceiling=c.FLOOR_RULES['timerMedianToEveryopMedianCeiling' if timer else 'supplyMedianToSampleMedianCeiling']
        warnings=[f['label']+': '+w for f in matched for w in f['warnings']]
        floor_ratios.append(dict(label=r['label'],ratio=ratio,ceiling=ceiling,warning=ratio>ceiling,floorQualityWarnings=warnings))
        if ratio>ceiling or warnings:floor_bad.add((p['Channel'],p['Backend'],p['Payload']))
    for comp in comparisons:
        channel='sample-calibration' if comp['channel']=='sample' else comp['channel']
        chosen=[r for r in rows if (r['inputs']['Channel'],r['inputs']['Payload'],r['inputs']['LiveBytes'])==
            (channel,comp['payloadBytes'],comp['applicationLiveBytes'])]
        usable=[r for r in chosen if r['finalPolicyUsable']]
        invalid=[r for r in chosen if not r['finalPolicyUsable']]
        issues=c.qualification_limitations(qual,channel,comp['payloadBytes'])
        issues += [r['label']+': rejected: '+reason for r in invalid for reason in r['fatalReasons']]
        issues += [r['label']+': '+w for r in usable for w in r['warnings']]
        if len(chosen)!=12 or len(usable)!=12:issues.append('Incomplete accepted scheduled cell; no bootstrap interval')
        comp['executionSegmentsByPass']={str(block):sorted({r['executionSegment'] for r in chosen if r['inputs']['Block']==block}) for block in (1,2)}
        if any(len(s)>1 for s in comp['executionSegmentsByPass'].values()):issues.append('Interrupted paired condition within an outer pass')
        for backend in c.evidence.BACKENDS:
            band=next(b for b in bands if (b['channel'],b['backend'],b['payloadBytes'],b['liveMiB'])==
                (channel,backend,comp['payloadBytes'],comp['applicationLiveBytes']//1024**2))
            issues += [backend+': '+w for w in band['warnings']]
            for r in usable:
                if r['inputs']['Backend']!=backend:continue
                occupancy=r.get('gc',r).get('postGcUsedHeapMedianFraction')
                if occupancy is None or band['median'] is None or abs(occupancy-band['median'])>.05:
                    issues.append(r['label']+': occupancy outside calibrated±5 point band')
                if (channel,backend,comp['payloadBytes']) in floor_bad:issues.append(r['label']+': matched low-pressure floor limitation')
        issues += comp['varianceRejectionReasons']
        comp['runVariation']={}
        for backend in c.evidence.BACKENDS:
            comp['runVariation'][backend]={}
            for endpoint in ('99','99.9'):
                values=[r['servicePercentilesNs'][endpoint] for r in usable if r['inputs']['Backend']==backend]
                comp['runVariation'][backend][endpoint]=dict(forks=len(values),valuesNs=values,
                    medianNs=statistics.median(values) if values else None,minimumNs=min(values,default=None),maximumNs=max(values,default=None),
                    coefficientOfVariation=statistics.stdev(values)/statistics.mean(values) if len(values)>1 else None)
        comp['rejectedInvocations']=[r['label'] for r in invalid]
        comp['acceptedInvocations']=[r['label'] for r in usable]
        comp['claimLimitations']=list(dict.fromkeys(issues));comp['resolvedConditionalClaimAllowed']=comp['complete'] and not issues
        for ratio in comp['ratios'].values():
            ratio['rawBootstrapDirection']=ratio['direction']
            ratio['conditionalDirection']=ratio['direction'] if comp['resolvedConditionalClaimAllowed'] else 'unresolved'
            ratio['direction']=ratio['conditionalDirection']
    disagreements=[]
    for payload in (256,4096):
        for live in c.RULES['liveMiB']:
            pair=[x for x in comparisons if x['payloadBytes']==payload and x['applicationLiveBytes']==live*1024**2]
            for endpoint in ('99','99.9'):
                directions=[x['ratios'].get(endpoint,{}).get('conditionalDirection','unresolved') for x in pair]
                if set(directions)=={'chronicle-lower','caffeine-lower'}:disagreements.append(dict(payloadBytes=payload,liveMiB=live,percentile=endpoint))
    return dict(comparisons=comparisons,floorRatios=floor_ratios,channelDisagreements=disagreements,
        statisticsInputLabels=[r['label'] for r in valid],excludedLabels=[r['label'] for r in rows if not r['finalPolicyUsable']])


def robustness(rows,qualification):
    result=[];qual=c.qualification_evidence(qualification)
    for seed in c.RULES['robustnessSeeds']:
        for payload in (256,4096):
            for live in c.RULES['liveMiB']:
                for channel in ('sample-calibration','every-operation'):
                    pair=[r for r in rows if (r['inputs']['Seed'],r['inputs']['Payload'],r['inputs']['LiveBytes'],r['inputs']['Channel'])==
                        (seed,payload,live*1024**2,channel)]
                    if len(pair)!=2 or {r['inputs']['Backend'] for r in pair}!=set(c.evidence.BACKENDS):raise ValueError('Missing robustness scheduled pair')
                    accepted=all(r['finalPolicyUsable'] for r in pair);by_backend={r['inputs']['Backend']:r for r in pair}
                    limits=c.qualification_limitations(qual,channel,payload)
                    result.append(dict(seed=seed,payloadBytes=payload,liveMiB=live,channel=channel,
                        acceptedPair=accepted,confidenceInterval=None,qualificationLimitations=limits,
                        warnings={b:r['warnings'] for b,r in by_backend.items()},rejected={b:r['fatalReasons'] for b,r in by_backend.items() if not r['finalPolicyUsable']},
                        conditionalSensitivityUsable=accepted and not limits and not any(r['warnings'] for r in pair),
                        chronicleToCaffeine={p:by_backend['CHRONICLE_IN_MEMORY']['servicePercentilesNs'][p]/by_backend['CAFFEINE']['servicePercentilesNs'][p]
                            for p in ('99','99.9')} if accepted else None))
    return result


def bind_parent(parent):
    state=load(parent/'state.json');protocol=load(parent/'protocol.json');campaign=parent.parent/(parent.name+'-campaign')
    if state.get('complete') or not state.get('terminalFailure') or state['currentStage']!='campaign':raise ValueError('Require original terminal partial campaign')
    if set(state['completedStages'])!=set(c.STAGES[:7]):raise ValueError('Missing completed original prerequisites')
    if c.evidence.source_hash()!=protocol['sourceSha256']:raise ValueError('Original full source changed')
    c.verify_master(parent,state,protocol['sourceSha256']);c.verify_refs(parent.parent,state['completedStages'])
    manifest=load(campaign/'manifest.json')
    if len(manifest['invocations'])!=OFFSET:raise ValueError('Unexpected partial campaign offset')
    if digest(campaign/'source.tar.gz')!=manifest['sourceArchiveSha256']:raise ValueError('Changed original campaign source')
    for inv,(label,p) in zip(manifest['invocations'],c.grid('campaign')):
        if (inv['label'],inv['properties'])!=(label,p):raise ValueError('Original prefix changed')
        c.calibration.verify_invocation(campaign,inv)
    paths=[parent/n for n in ('state.json','protocol.json','manifest.json','source.tar.gz')]+[campaign/n for n in ('manifest.json','source.tar.gz','final-declaration.json')]
    return dict(parent=parent.name,sourceSha256=protocol['sourceSha256'],measurementSourceSha256=protocol['measurementSourceSha256'],
        fixedFiles={str(p.relative_to(parent.parent)):digest(p) for p in paths},completedStageRefs=state['completedStages'],
        originalTerminalFailure=state['terminalFailure'],originalCampaignInvocations=OFFSET)


def verify_binding(binding):
    if c.evidence.source_hash()!=binding['sourceSha256']:raise ValueError('Source changed during supplement')
    for relative,value in binding['fixedFiles'].items():
        if digest(c.evidence.REPORTS/relative)!=value:raise ValueError('Original frozen evidence changed')
    c.verify_refs(c.evidence.REPORTS,binding['completedStageRefs'])


def quiet(path,source):
    prep_path=path.parent/(path.name+'-cache-preparation.json')
    cache=c.prepare_file_cache(prep_path,include_build_outputs=True,stream_inventory=True,available_memory=True)
    if not c.run_preflight(path,120,300)['quietPass']:raise ValueError('Supplement quiet failed')
    save(path/'host-preparation.json',cache)
    ref=c.native_retry.initial_quiet_reference(path,dict(sourceSha256=source),c.native_retry.declare_policy(2),c.evidence.host_snapshot())
    return ref


def proof(manifest,ref):
    return dict(manifest,initialQuietRef=ref,initialMemoryReadinessRule=c.AVAILABLE_MEMORY_RULE,
        nativeHostRetryPolicy=c.native_retry.declare_policy(2))


def run_fragment(control,stage,offset,binding,helper,runtime,traces):
    path=control.parent/(control.name+'-'+stage);slots=c.grid(stage)[offset:]
    if path.exists():raise ValueError('Supplement fragment exists; no duplicate launch')
    ref=quiet(control.parent/(path.name+'-quiet'),binding['sourceSha256'])
    verify_binding(binding)
    manifest=c.calibration.prepare(path,c.options(stage),slots)
    manifest.update(hdrVerifier=helper,initialMemoryReadinessRule=c.AVAILABLE_MEMORY_RULE,nativeEnvironmentVersion=1,
        nativeEnvironmentDeclaration=c.evidence.native_host.environment_declaration(c.evidence.host_snapshot()))
    manifest['inputs']['passes']=1 if stage=='robustness' else 2;manifest['inputs']['forksPerPass']=1 if stage=='robustness' else 3
    if stage=='robustness':manifest['inputs'].pop('seed');manifest['inputs']['seeds']=list(c.RULES['robustnessSeeds'])
    save(path/'manifest.json',manifest)
    frozen=dict(version=VERSION,parentBinding=binding,stage=stage,offset=offset,slots=[dict(label=k,properties=p) for k,p in slots],
        initialQuietRef=ref,rejectionQuietRefs={},controllerSha256=digest(control/'controller.py'),declarationSha256=digest(control/'declaration.json'))
    save(path/'fragment.json',frozen);c.native_retry.verify_initial_quiet(path,proof(manifest,ref),before_launch=True)
    for index,(label,p) in enumerate(slots):
        verify_binding(binding);task='tailCache12SampleCalibration' if p['Channel']=='sample-calibration' else 'tailCache12EveryOperation'
        c.evidence.invoke(path,manifest,label,task,p)
        row,runtime,trace=c.read_row(path,manifest,manifest['invocations'][-1],runtime,traces.get(p['Seed']),helper)
        traces[p['Seed']]=trace;row=c.apply_policy(row,stage)
        if row['fatalReasons']:
            if not allowed_rejection(row):raise ValueError('Hard supplement stop: '+str(row['fatalReasons']))
            print('SUPPLEMENT_REJECTED '+label+' '+str(row['fatalReasons']),flush=True)
            if index+1<len(slots):
                next_label=slots[index+1][0]
                ref2=quiet(control.parent/(path.name+'-quiet-after-'+str(index+1)),binding['sourceSha256'])
                frozen['rejectionQuietRefs'][next_label]=ref2;save(path/'fragment.json',frozen)
                c.native_retry.verify_initial_quiet(path,proof(manifest,ref2),before_launch=True)
    rows,runtime,traces=replay_fragment(control,path,stage,offset,binding,helper,runtime,traces)
    save(path/'completion-review.json',dict(completeCollection=len(rows)==len(slots),observations=rows,rejected=sum(not r['finalPolicyUsable'] for r in rows)))
    print('SUPPLEMENT_STAGE_COMPLETE '+stage+' '+str(len(rows)),flush=True)
    return path,rows,runtime,traces


def replay_fragment(control,path,stage,offset,binding,helper,runtime,traces):
    frozen=load(path/'fragment.json');m=load(path/'manifest.json');slots=c.grid(stage)[offset:]
    if (frozen['version']!=VERSION or frozen['parentBinding']!=binding or frozen['stage']!=stage or frozen['offset']!=offset
            or frozen['slots']!=[dict(label=k,properties=p) for k,p in slots] or m['expectedBlocks']!=[k for k,p in slots]
            or m['sourceSha256']!=binding['sourceSha256'] or frozen['controllerSha256']!=digest(control/'controller.py')
            or frozen['declarationSha256']!=digest(control/'declaration.json')):raise ValueError('Changed supplement declaration')
    if c.archive_measurement_source_hash(path/'source.tar.gz')!=binding['measurementSourceSha256']:
        raise ValueError('Changed supplement measurement source')
    rows,runtime,traces=replay_rows(path,stage,helper,'completion',offset,runtime,traces)
    if len(rows)!=len(slots):raise ValueError('Incomplete supplement fragment')
    c.native_retry.verify_initial_quiet(path,proof(m,frozen['initialQuietRef']),rows)
    refs=frozen['rejectionQuietRefs'];required={}
    for a,b in zip(rows,rows[1:]):
        if not a['finalPolicyUsable']:required[b['label']]=b
    if set(refs)!=set(required):raise ValueError('Missing or extra post-rejection quiet')
    for label,row in required.items():c.native_retry.verify_initial_quiet(path,proof(m,refs[label]),[row])
    return rows,runtime,traces


def archive_dependencies(control,parent,stages,fragments,destination):
    roots=[control,parent,parent.parent/load(parent/'protocol.json')['hdrVerifier']['setup'],parent.parent/NATIVE]
    extras={parent.parent/(NATIVE+'-cold-readiness.json')}
    for stage,result in stages.items():
        path=parent.parent/(parent.name+'-'+stage);roots.append(path)
        frozen=load(path/'final-declaration.json');q=parent.parent/frozen['initialQuietRef']['attempt'];roots.append(q)
        extras.add(parent.parent/(q.name+'-cache-preparation.json'));extras.add(parent.parent/load(q/'host-preparation.json')['inventoryFile'])
        roots += [c.evidence.raw_directory(path,i) for i in load(path/'manifest.json')['invocations']]
    for path in fragments:
        roots.append(path);frozen=load(path/'fragment.json')
        for ref in [frozen['initialQuietRef'],*frozen['rejectionQuietRefs'].values()]:
            q=parent.parent/ref['attempt'];roots.append(q);extras.add(parent.parent/(q.name+'-cache-preparation.json'))
            extras.add(parent.parent/load(q/'host-preparation.json')['inventoryFile'])
        roots += [c.evidence.raw_directory(path,i) for i in load(path/'manifest.json')['invocations']]
    roots += list(parent.parent.glob(control.name+'-audit-*'))
    files=extras|{p for root in roots for p in root.rglob('*') if p.is_file()}
    inventory,receipt=c.archive_files(files,destination/'raw-sources.tar.gz')
    save(destination/'archive-inventory.json',inventory);save(destination/'archive.json',receipt)
    return receipt


def run(prefix,output):
    parent=c.evidence.REPORTS/PARENT;control=c.evidence.REPORTS/prefix
    if control.exists() or output.exists():raise ValueError('Retained completion exists; do not duplicate')
    if os.environ.get('TAILCACHE_REQUIRE_NATIVE_HOST')!='1' or c.evidence.host_snapshot().get('nativeScopeQualified')!=1:raise ValueError('Require exclusive native scope')
    binding=bind_parent(parent);native=c.native_control_reference(NATIVE,c.evidence.host_snapshot())
    control.mkdir();shutil.copyfile(__file__,control/'controller.py')
    shutil.copyfile(ROOT/'ops/TAILCACHE_12_PARTIAL_COMPLETION_PLAN.md',control/'plan.md')
    shutil.copyfile(ROOT/'ops/TAILCACHE_12_PARTIAL_COMPLETION_IMPLEMENTATION_REVIEW.md',control/'implementation-review.md')
    save(control/'declaration.json',dict(version=VERSION,parentBinding=binding,nativeControlRef=native,
        controllerSha256=digest(control/'controller.py'),planSha256=digest(control/'plan.md'),
        implementationReviewSha256=digest(control/'implementation-review.md'),declaredUtc=now(),
        suffixes={stage:[dict(label=k,properties=p) for k,p in c.grid(stage)[offset:]] for stage,offset in (('campaign',OFFSET),('robustness',0))},
        changedStoppingOnly=True,unchangedCpuCeilingPercent=25,replacements=0,rejectedRowsExcludedFromStatistics=True))
    state=dict(completeCollection=False,taskComplete=False,currentStage='original-replay',startedUtc=now(),fragments={})
    save(control/'state.json',state);os.environ['TAILCACHE_THERMAL_READINESS']=c.evidence.THERMAL_STARTUP_RULE['version']
    try:
        protocol=load(parent/'protocol.json');helper=protocol['hdrVerifier'];stages={}
        for stage in c.STAGES[:7]:
            path=parent.parent/(parent.name+'-'+stage)
            if stage in ('functional','pause'):
                audit=parent.parent/(control.name+'-audit-'+stage);shutil.copytree(path,audit);path=audit
            stages[stage]=c.audit_stage(path,stage,helper)
            if not stages[stage]['complete']:raise ValueError('Original completed prerequisite failed fresh replay')
            save(control/(stage+'-replay.json'),stages[stage])
        path=parent.parent/(parent.name+'-campaign')
        original,runtime,traces=replay_rows(path,'campaign',helper,'original')
        if len(original)!=OFFSET or not allowed_rejection(original[-1]):raise ValueError('Original rejection facts changed')
        save(control/'original-campaign-replay.json',dict(observations=original,originalComplete=False))
        stages['campaign']=dict(complete=False,observations=original)
        fragments=[];all_rows={}
        for stage,offset in (('campaign',OFFSET),('robustness',0)):
            state['currentStage']=stage;save(control/'state.json',state)
            path,rows,runtime,traces=run_fragment(control,stage,offset,binding,helper,runtime,traces)
            fragments.append(path);all_rows[stage]=rows;state['fragments'][stage]=dict(path=path.name,manifestSha256=digest(path/'manifest.json'),reviewSha256=digest(path/'completion-review.json'))
            save(control/'state.json',state)
        verify_binding(binding)
        # Fresh replay after all collection; recorded hashes and acceptance are authoritative.
        original,runtime,traces=replay_rows(parent.parent/(parent.name+'-campaign'),'campaign',helper,'original')
        for stage,path in zip(('campaign','robustness'),fragments):
            offset=OFFSET if stage=='campaign' else 0
            all_rows[stage],runtime,traces=replay_fragment(control,path,stage,offset,binding,helper,runtime,traces)
        campaign=original+all_rows['campaign'];validate_suffix([dict(label=r['label'],properties=r['inputs']) for r in campaign],'campaign',0)
        if len(campaign)!=192 or len(all_rows['robustness'])!=64:raise ValueError('Incomplete full physical schedule')
        analysis=analyse(campaign,stages['calibration']['pressureBands'],stages['floors']['observations'],stages['qualification']['observations'])
        output.mkdir(parents=True)
        dataset=dict(schemaVersion=VERSION,taskComplete=False,requiresResearcherReview=True,analysisReady=True,completeExecution=True,
            originalStudyComplete=False,originalStudyTerminalFailure=binding['originalTerminalFailure'],originalPrimaryProtocolQualified=False,
            reportingScope='conditional-on-recording-regime-with-explicit-rejections',originalRules=c.RULES,completionDeclaration=load(control/'declaration.json'),
            stages=stages,campaignObservations=campaign,robustnessObservations=all_rows['robustness'],campaign=analysis,
            primaryConditionAcceptance=c.condition_acceptance(analysis['comparisons']),
            robustness=robustness(all_rows['robustness'],stages['qualification']['observations']),
            expectedInvocations=402,collectedInvocations=sum(len(stages[s]['observations']) for s in c.STAGES[:7])+len(campaign)+len(all_rows['robustness']),
            limits=['Original v5 stopping rule rejected the study; supplement changes stopping only, never acceptance.',
                'Rejected observations are absent from all ratios, bootstrap and run-variation inputs; incomplete accepted cells have no CI.',
                'One unrandomized interruption; segments and split paired conditions are recorded. Only two outer passes give coarse uncertainty.',
                'Recording regimes and robustness seeds remain separate; no unconditional crossover/no-crossover or persisted cold/open claim.'])
        if dataset['collectedInvocations']!=402:raise ValueError('Incomplete total invocation coverage')
        save(output/'dataset.json',dataset);shutil.copyfile(parent/'protocol.json',output/'original-protocol.json')
        shutil.copyfile(control/'declaration.json',output/'completion-declaration.json')
        observations={**{s:stages[s]['observations'] for s in c.STAGES[:7]},'campaign':campaign,'robustness':all_rows['robustness']}
        with (output/'coverage.csv').open('x',newline='') as stream:
            writer=csv.DictWriter(stream,['stage','label','backend','payloadBytes','liveMiB','channel','seed','block','fork','executionSegment','acceptedForStatistics','p99Ns','p999Ns','warnings','fatalReasons']);writer.writeheader()
            for stage,rows in observations.items():
                for row in rows:
                    p=row['inputs'];accepted=row['finalPolicyUsable'];tails=row.get('servicePercentilesNs',{}) if accepted else {}
                    writer.writerow(dict(stage=stage,label=row['label'],backend=p.get('Backend',p.get('Backends')),payloadBytes=p.get('Payload',p.get('Payloads')),
                        liveMiB=p.get('LiveBytes',0)/1024**2,channel=p.get('Channel'),seed=p.get('Seed'),block=p.get('Block'),fork=p.get('ForkOrdinal'),
                        executionSegment=row.get('executionSegment','original'),acceptedForStatistics=accepted,p99Ns=tails.get('99'),p999Ns=tails.get('99.9'),
                        warnings=json.dumps(row['warnings']),fatalReasons=json.dumps(row['fatalReasons'])))
        archive=archive_dependencies(control,parent,stages,fragments,output)
        verify_binding(binding)
        state.update(completeCollection=True,requiresResearcherReview=True,currentStage=None,finishedUtc=now(),output=str(output),
            datasetSha256=digest(output/'dataset.json'),archive=archive)
        save(control/'state.json',state)
        print('SUPPLEMENT_DATASET_EXPORTED '+str(output),flush=True)
    except Exception as error:
        state['terminalFailure']=dict(reason=f'{type(error).__name__}: {error}',utc=now());save(control/'state.json',state);raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('prefix');parser.add_argument('--output',type=pathlib.Path,required=True);args=parser.parse_args()
    if not c.evidence.re.fullmatch('[A-Za-z0-9._-]+',args.prefix):parser.error('Invalid completion prefix')
    run(args.prefix,args.output.resolve())
