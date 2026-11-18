#!/usr/bin/env python3
"""Independent predictor stream/HDR/GC/RSS/source reconciliation; zero-write channels remain empty."""
import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import math
import pathlib
import subprocess
import tarfile

ROOT=pathlib.Path(__file__).resolve().parents[1]


def require(value,message):
    if not value:raise ValueError(message)


def load(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def csvrows(path):
    with path.open() as f:return list(csv.DictReader(f))


def same(actual,expected,label):
    require((actual is None and expected is None) or (actual is not None and expected is not None
            and math.isclose(actual,expected,rel_tol=1e-12,abs_tol=1e-6)),label)


def focus_properties(p):return dict(l.split('=',1) for l in p.read_text().splitlines() if '=' in l)

def audit(base,out):
    require(__debug__,'Run without -O: prior independent GC parser uses assertions')
    out.mkdir(parents=True,exist_ok=False)
    study=load(base/'study.json');protocol=load(base/'protocol.json');state=load(base/'state.json')
    require(state['complete'] and len(study['observations'])<=protocol['maxWorkloadJvms'],
            'Incomplete collection or budget exceeded')
    # Verify the archived source/runtime, so a later legitimate checkout edit does not
    # make a previously frozen cohort unverifiable. Never execute arbitrary tar paths.
    archived_source={}
    with tarfile.open(base/'source.tar.gz','r:gz') as archive:
        for member in archive:
            require(member.isfile() and member.name in protocol['sourceFiles'] and member.name not in archived_source,
                    'Unexpected/duplicate source archive member')
            with archive.extractfile(member) as stream:data=stream.read()
            require(hashlib.sha256(data).hexdigest()==protocol['sourceFiles'][member.name],'Archived source changed')
            archived_source[member.name]=data
    require(set(archived_source)==set(protocol['sourceFiles']),'Archived source coverage')
    compiled=load(base/'setup/compilation.json');qualified=load(base/'setup/functional-validation.json')
    require(compiled['passed'] and qualified['passed'] and qualified['compilationSha256']==sha(base/'setup/compilation.json'),'Qualification/compiler binding')
    for name,digest in compiled['sourceSha256'].items():require(hashlib.sha256(archived_source[name]).hexdigest()==digest,'Compiled archived source identity')
    runtime={}
    original_cp=protocol['classpath'].split(':')
    for index,item in enumerate(original_cp):
        original=pathlib.Path(item);destination=base/'runtime'/str(index)
        for file,digest in protocol['runtimeSha256'].items():
            p=pathlib.Path(file)
            if str(p)==item:
                archived=destination/p.name
            elif p.is_relative_to(original):
                archived=destination/p.relative_to(original)
            else:continue
            require(sha(archived)==digest,'Archived runtime changed: '+file);runtime[file]=digest
    require(runtime==protocol['runtimeSha256'],'Archived runtime coverage')
    for file,digest in protocol['preservedPaperInputs'].items():require(sha(ROOT/file)==digest,'Prior paper evidence changed')
    entries=[(r,base/'slots'/r['label']) for r in study['observations']]
    entries += [(load(p),p.parent) for p in sorted((base/'controls').glob('*/service-result.json'))]
    require(len({str(p) for r,p in entries})==len(entries),'Duplicate observation identities')
    counts=collections.Counter();paths=[]
    for row,directory in entries:
        for file,digest in row['rawSha256'].items():
            require(sha(directory/file)==digest,'Raw file changed: '+str(directory/file));counts['rawFiles']+=1
        paths.extend(sorted((directory/'worker').glob('*.hdr')))
    java=pathlib.Path('/usr/lib/jvm/java-21-openjdk/bin')
    cp=':'.join(str(base/p) for p in protocol['archivedClasspath'])
    helper=out/'TailCacheFocusedHdrVerify.java'
    helper.write_bytes(archived_source['scripts/java/TailCacheFocusedHdrVerify.java'])
    subprocess.run([str(java/'javac'),'-cp',cp,'-d',str(out),str(helper)],check=True,capture_output=True)
    decoded=out/'decoded.csv'
    ran=subprocess.run([str(java/'java'),'-Xmx96m','-cp',str(out)+':'+cp,'TailCacheFocusedHdrVerify',str(base),str(decoded)],check=True,capture_output=True,text=True)
    raw={r['path']:r for r in csvrows(decoded)}
    require(set(raw)=={str(p.resolve()) for p in paths},'Available histogram coverage mismatch')
    independent=out/'prior_independent_gc.py'
    independent.write_bytes(archived_source['ops/tailcache12_final_raw_audit.py'])
    spec=importlib.util.spec_from_file_location('independent_original',independent)
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    for row,directory in entries:
        if not row.get('latencyVerified') or row['status']!='OK':
            counts['failureOutcomes']+=1;continue
        windows=csvrows(directory/'worker/windows.csv')
        require(windows==row['windows'],'Raw phase windows changed')
        measured=[w for w in windows if w['phase']=='MEASUREMENT'];require(len(measured)==1,'Window count')
        w=measured[0];n=int(w['operations']);writes=int(w['writes'])
        require(all(not int(v['scheduled']) or int(v['operations'])==int(v['scheduled']) for v in windows),
                'All-phase intended/completed request conservation')
        for channel,data in row['latency'].items():
            r=raw[str((directory/'worker'/(channel+'.hdr')).resolve())]
            scheduled=int(w['scheduled'])
            if scheduled:require(scheduled==n,'Complete paced operation/arrival conservation')
            expected=scheduled if channel=='response' else writes if channel=='update-service' else n-writes if channel=='read-service' else n
            require(int(r['count'])==data['count']==expected,'Per-channel conservation')
            for p,k in [('50','p50Ns'),('99','p99Ns'),('99.9','p999Ns'),('99.99','p9999Ns'),('99.999','p99999Ns')]:
                if expected:same(int(r[k]),data['percentilesNs'][p],'Published/library percentile');counts['quantileEndpoints']+=bool(expected)
            counts['channelCounts']+=1
        def distribution(name):return {int(b['upperEquivalentNs']):int(b['count']) for b in csvrows(directory/'worker'/(name+'-bins.csv'))}
        union=collections.Counter(distribution('read-service'));union.update(distribution('update-service'))
        require(dict(union)==distribution('service'),'Raw per-bin read/update union')
        counts['perBinUnions']+=1
        same(int(w['workerAllocatedBytes'])/n,row['measurement']['workerBytesPerOperation'],'Worker allocation')
        seconds=(int(w['endNs'])-int(w['startNs']))/1e9
        same(n/seconds,row['measurement']['operationsPerSecond'],'Throughput')
        memory=csvrows(directory/'process-memory.csv')
        selected=[r for r in memory if int(r['sampleStartNs'])>=int(w['startNs']) and int(r['sampleEndNs'])<=int(w['endNs']) and r['VmRSSKiB']]
        same(max((int(r['VmRSSKiB']) for r in selected),default=None),row['processMemory']['measuredMaxRssKiB'],'RSS')
        gc=old.gc_audit(directory/'gc-through-measurement.log',[(int(w['startNs']),int(w['endNs']))])
        for key,value in gc.items():
            if key!='occupancyCount':same(value,row['gc'][key],'Independent GC/'+key)
        counts['gcSummaries']+=1;counts['rssSummaries']+=1
        config=dict(line.split('=',1) for line in (directory/'worker/configuration.txt').read_text().splitlines() if '=' in line)
        require(config['traceSha256']==row['trace']['traceSha256'],'Trace identity')
        require(config['streamVersion']=='indexed-splitmix-v1' and config['streamPhaseReset']==config['streamWrap']=='false','Continuous stream contract')
        require(config['traceOperations']==config['traceArrayPayloadBytes']=='0','No finite trace arrays')
        expected_identity='indexed-splitmix-v1:seed='+str(row['seed'])+':residents='+str(row.get('residents',32768))+':writeBps='+str(row['writeBps'])+':updateHotset='+str(row['hotset'])
        require(config['streamIdentity']==expected_identity,'Stream identity treatment')
        require(config['traceSha256']==hashlib.sha256(expected_identity.encode()).hexdigest(),'Stream definition hash')
        previous=0
        for phase in windows:
            props=focus_properties(directory/'worker'/('stream-'+phase['phase']+'.txt'))
            require(int(props['start'])==previous and int(props['writeBps'])==row['writeBps'],'Raw stream continuity')
            require(row.get('floor') or int(props['end'])-previous==int(phase['operations']),'Raw stream progress')
            previous=int(props['end'])
            duration=1000 if phase['phase'].startswith('PRIME') else row['warmupMs']-1000*row['primeCalls'] if phase['phase']=='WARMUP' else row['conditioningMs'] if phase['phase']=='CONDITIONING' else row['measureMs']
            require(int(phase['scheduled'])==duration*50,'Per-slot actual timing')
        if row['backend'].startswith('CAFFEINE'):
            policy={'CAFFEINE':'BOUNDED_DEFAULT','CAFFEINE_BOUNDED_DIRECT':'BOUNDED_DIRECT','CAFFEINE_UNBOUNDED':'UNBOUNDED'}[row['backend']]
            if (protocol.get('design') or {}).get('kind')=='cache-policy-sensitivity-v1':
                require('policy='+policy in config['backendConfig'],'Actual cache policy declaration')
        require('-Dchronicle.analytics.disable=true' in config['jvmArgs'],'Analytics must be disabled')
        require(all(flag in config['jvmArgs'] for flag in (f'-Xms{row["heapMiB"]}m',f'-Xmx{row["heapMiB"]}m','-XX:+UseG1GC')),
                'Actual fixed-heap/collector contract')
        require(int(config['maxHeapBytes'])==row['heapMiB']*1024**2 and int(config['updateHotset'])==row['hotset'],'Actual heap/hotset')
        require(('-Xlog:async' in config['jvmArgs'])==(row['logging']=='async'),'Logging mode')
        require(int(config['primeCalls'])==row['primeCalls'] and int(config['eventThresholdNs'])==100000,'Priming/event contract')
        require(row['logComplete'],'Log drops')
        require(__import__('re').search(r'Heap Region Size:\s*1M',(directory/'gc-through-measurement.log').read_text()),'Expected1MiB regions for independent region parser')
        if row.get('tracePattern'):
            require(config.get('tracePattern')==row['tracePattern'],'Actual raw trace-pattern selection')
    # A confirmation may contain multiple paired forks; each must be complete and correctly matched.
    grouped=collections.defaultdict(dict)
    for row in study['observations']:
        key=tuple(row[k] for k in ('stage','payload','liveMiB','seed','block'))
        require(row['backend'] not in grouped[key],'Duplicate backend');grouped[key][row['backend']]=row
    policy=(protocol.get('design') or {}).get('kind')=='cache-policy-sensitivity-v1'
    require(len(study['pairs'])==len(grouped)*(3 if policy else 1),'Pair coverage')
    seen=set()
    for pair in study['pairs']:
        key=tuple(pair[k] for k in ('stage','payload','liveMiB','seed','block'))
        arms=grouped[key]
        reference=pair.get('referenceBackend','CAFFEINE');treatment=pair.get('comparisonBackend','CHRONICLE_IN_MEMORY')
        require(reference!=treatment and (key,reference,treatment) not in seen,'Duplicate/self contrast')
        seen.add((key,reference,treatment))
        require(set(arms)==({'CAFFEINE','CAFFEINE_BOUNDED_DIRECT','CAFFEINE_UNBOUNDED','CHRONICLE_IN_MEMORY'} if policy else {'CAFFEINE','CHRONICLE_IN_MEMORY'}),'Paired arm coverage')
        chosen={b:arms[b] for b in (reference,treatment)}
        require(pair['labels']=={b:r['label'] for b,r in chosen.items()},'Paired labels changed')
        if pair['valid']:
            require(all(r['status']=='OK' and r.get('latencyVerified') for r in chosen.values()),'Invalid valid pair')
            require(len({r['trace']['traceSha256'] for r in chosen.values()})==1,'Different paired traces')
            if all(r.get('qps',0)>0 for r in chosen.values()):
                require(len({tuple((w['phase'],w['writes']) for w in r['windows']) for r in chosen.values()})==1,'Paired all-phase logical writes')
            for channel,values in pair['ratios'].items():
                for percentile,value in values.items():
                    same(arms[treatment]['latency'][channel]['percentilesNs'][percentile]/
                         arms[reference]['latency'][channel]['percentilesNs'][percentile],value,'Published paired ratio')
                    counts['pairedRatios']+=1
    stream_input=out/'stream-inputs.csv'
    selected=[(r,p) for r,p in entries if r.get('status')=='OK' and not r.get('floor')]
    with stream_input.open('x') as stream:
        writer=csv.writer(stream);writer.writerow(['label','seed','writeBps','residents','hotset','phases'])
        for row,directory in selected:writer.writerow([row['label'],row['seed'],row['writeBps'],row.get('residents',32768),row['hotset'],';'.join(w['phase']+':'+w['operations'] for w in row['windows'])])
    helper=out/'MechanismStreamAudit.java';helper.write_bytes(archived_source['scripts/java/MechanismStreamAudit.java'])
    subprocess.run([str(java/'javac'),'-d',str(out),str(helper)],check=True,capture_output=True)
    replay=out/'stream-replay.csv';subprocess.run([str(java/'java'),'-Xmx64m','-cp',str(out),'MechanismStreamAudit',str(stream_input),str(replay)],check=True,capture_output=True)
    expected={(r['label'],r['phase']):r for r in csvrows(replay)}
    for row,directory in selected:
        for w in row['windows']:require(int(expected[row['label'],w['phase']]['writes'])==int(w['writes']),'Independent stream counts');counts['streamPhaseChecks']+=1
        if not row.get('supply'):require(focus_properties(directory/'worker/integrity.txt')['mutationVersionSha256']==expected[row['label'],'FINAL']['versionSha256'],'Mutation version digest')
    event_diagnostics=[]
    for row,directory in entries:
        if not row.get('latencyVerified'):continue
        pauses=load(directory/'measured-gc.json')['pauses'];extra=[];unassociated=0;events=csvrows(directory/'worker/stalls.csv');w=next(w for w in row['windows'] if w['phase']=='MEASUREMENT');previous=-1
        for e in events:
            x,y,start,index=[int(e[k]) for k in ('previousEndNs','operationEndNs','operationStartNs','operationIndex')]
            require(int(w['startNs'])<=x<=start<=y<=int(w['endNs']) and y-x>=100000 and previous<index<int(w['operations']),'Sparse/index coverage');previous=index
            ov=sum(max(0,min(y,int(p['endNs']))-max(x,int(p['startNs']))) for p in pauses)
            if ov:extra.append(y-x-ov)
            else:unassociated+=1
        require(len(events)==int(w['stallEvents']) and int(w['unexportedStallEvents'])==0,'Event capacity')
        event_diagnostics.append(dict(label=row['label'],medianGcLinkedExcessNs=__import__('statistics').median(extra) if extra else None,gcLinkedEvents=len(extra),unassociatedSparseEvents=unassociated,eventThresholdNs=100000))
    manifest=[dict(path=str(p.relative_to(base)),bytes=p.stat().st_size,sha256=sha(p))
              for p in sorted(base.rglob('*')) if p.is_file() and not p.is_relative_to(out)]
    (out/'inventory.json').write_text(json.dumps(manifest,indent=2)+'\n')
    receipt=dict(eventDiagnostics=event_diagnostics,streamReplay=csvrows(replay),passed=True,newWorkloadJvms=len(study['observations']),controlJvms=len(entries)-len(study['observations']),
                 independentlyDecodedHistograms=len(raw),counts=dict(counts),studySha256=sha(base/'study.json'),
                 protocolSha256=sha(base/'protocol.json'),sourceArchiveSha256=sha(base/'source.tar.gz'),
                 inventoryFiles=len(manifest),runtimeFilesVerified=len(protocol['runtimeSha256']),
                 helper=load(base/'setup/functional-validation.json') if (base/'setup/functional-validation.json').exists() else None,
                 limits='Offline reconciliation reuses pinned HDR decoder and prior independent GC parser; no event-level causal claim or independent new performance replication.')
    (out/'audit.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))


def predictions(base):
    import runpy
    import tailcache12_pause_model as m
    spec=load(ROOT/'docs/mechanism/model-v1.json');params=load(ROOT/'docs/predictor/drain-candidate-v1.json');constant=load(ROOT/'docs/predictor/numeric-baseline-v1.json');residual=load(ROOT/'docs/predictor/model-v1.json')
    for file,h in spec['referenceInputs'].items():require(sha(ROOT/file)==h,'Frozen model reference')
    code=ROOT/'docs/predictor/drain_candidate.py.txt';solver=runpy.run_path(str(code));state=load(base/'state.json');require(state['collectionComplete'],'Wait for complete cohort');require(load(base/'raw-audit.json')['passed'],'Raw audit before model')
    records=[]
    for row in state['scheduled']:
        directory=base/'slots'/row['label'];w=next(w for w in csvrows(directory/'worker/windows.csv') if w['phase']=='MEASUREMENT');a,b=int(w['startNs']),int(w['offeredEndNs']);gc=load(directory/'measured-gc.json')['pauses']
        record=dict(label=row['label'],backend=row['backend'],payload=row['payload'],outsideCalibration=row['payload']!=4096,inputs={str(p.relative_to(base)):sha(p) for p in (directory/'measured-gc.json',directory/'worker/windows.csv',directory/'gc-through-measurement.log')},predictions={})
        if row['payload']==4096:
            record['predictions'].update({k:v for k,v in m.predict(residual,gc,a,b,row['backend']).items() if k in ('M0','M1')});record['predictions']['constant']=constant['valuesNs'][row['backend']]
            intervals=[(p['startNs'],p['endNs']) for p in gc];core=[];total=[]
            for line in (directory/'gc-through-measurement.log').read_text().splitlines():
                if '[safepoint' not in line:continue
                stamp=__import__('re').search(r'\[([0-9]+)ns\]',line);fields={k:int(v) for k,v in __import__('re').findall(r'(Reaching safepoint|Cleanup|At safepoint|Leaving safepoint|Total): ([0-9]+) ns',line)}
                if stamp and 'Total' in fields:
                    end=int(stamp[1]);require(sum(v for k,v in fields.items() if k!='Total')==fields['Total'],'Safepoint components');total.append((end-fields['Total'],end));core.append((end-(fields['Total']-fields['Reaching safepoint']),end))
            for name,ps in [('M2',intervals),('M3core',intervals+core),('M3total',intervals+total)]:
                sim=solver['simulate'](ps,a,b,1_000_000_000//row['qps'],solver['interpolate'](params['intrinsicServiceNs'][row['backend']],row['writeBps']),params['bookkeepingNs'][row['backend']],m.QS)
                require(sim['operations']==int(w['scheduled']),'Model request accounting');record['predictions'][name]={q:sim['percentilesNs'][q]+params['timerBaselineNs'][q] for q in m.QS}
        records.append(record)
    result=dict(specificationSha256=sha(ROOT/'docs/mechanism/model-v1.json'),solverSha256=sha(code),observations=records,latencyTargetsRead=False,meaning='Frozen conditional interval/cost transport; selected logging/priming are development, payload256 outside calibration')
    with (base/'predictions-v1.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')

def score(base):
    import tailcache12_pause_model as m
    study=load(base/'study.json');preds=load(base/'predictions-v1.json');pr={r['label']:r for r in preds['observations']};rows=study['observations']
    for r in pr.values():
        for p,h in r['inputs'].items():require(sha(base/p)==h,'Prediction input changed')
    numerical={}
    for subset in ('all','CAFFEINE','CHRONICLE_IN_MEMORY'):
        selected=[r for r in rows if r['payload']==4096 and (subset=='all' or r['backend']==subset)]
        numerical[subset]={method:{q:m.error_summary([(pr[r['label']]['predictions'][method][q],r['latency']['response']['percentilesNs'][q]) for r in selected]) for q in m.QS} for method in ('M0','M1','M2','M3core','M3total','constant')}
    data=dict(passedIntegrity=True,studySha256=sha(base/'study.json'),predictionsSha256=sha(base/'predictions-v1.json'),researchForks=len(rows),numerical=numerical,warningBearing=sum(bool(r['warnings']) for r in rows),outsideCalibrationForks=sum(r['payload']!=4096 for r in rows),limits='Numerical scoring transports fixed old costs; no refitting or claims of precise exante prediction')
    with (base/'score-v1.json').open('x') as stream:json.dump(data,stream,indent=2);stream.write('\n')
    print(json.dumps(data,indent=2))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['raw','predict','score']);parser.add_argument('attempt');args=parser.parse_args();base=ROOT/'evidence-archives'/args.attempt
    if args.command=='raw':
        if (base/'raw-audit.json').exists():require(load(base/'raw-audit.json')['studySha256']==sha(base/'study.json'),'Audit study binding');return
        index=1
        while (base/f'independent-audit-{index:03}').exists():index+=1
        out=base/f'independent-audit-{index:03}';audit(base,out);receipt=load(out/'audit.json');receipt['auditDirectory']=out.name
        with (base/'raw-audit.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
    elif args.command=='predict':predictions(base)
    else:score(base)
if __name__=='__main__':main()
