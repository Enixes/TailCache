#!/usr/bin/env python3
"""Offline audit and synthesis of separately declared midpoint/seed cohorts."""
import argparse,collections,csv,datetime,hashlib,json,math,pathlib,shutil,statistics,subprocess,sys

ROOT=pathlib.Path.cwd()
sys.path.insert(0,str(ROOT/'scripts'))
import tailcache12_focus_report as independent
import tailcache12_tail_curves as curves

PERCENTILES=('99','99.9','99.99','99.999')
BACKENDS=('CAFFEINE','CHRONICLE_IN_MEMORY')

def load(p):return json.loads(p.read_text())
def save(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def sha(p):return independent.sha(p)
def rows(p):return independent.csvrows(p)


def conclusions(observations,stages):
    output=[]
    for stage in stages:
        for live in stage['levelsMiB']:
            selected=[r for r in observations if r['batch']==stage['attempt'] and r['liveMiB']==live]
            pairs=[]
            for block in range(1,stage['passes']+1):
                by={r['backend']:r for r in selected if r['block']==block}
                valid=set(by)==set(BACKENDS) and all(r['status']=='OK' and r['latencyVerified'] for r in by.values())
                pairs.append(dict(block=block,valid=valid,clean=valid and not any(r['warnings'] for r in by.values()),by=by))
            for channel in ('response','service','gap'):
                for percentile in PERCENTILES:
                    good=[p for p in pairs if p['valid']]
                    ratios=[p['by'][BACKENDS[1]]['latency'][channel]['percentilesNs'][percentile]/p['by'][BACKENDS[0]]['latency'][channel]['percentilesNs'][percentile] for p in good]
                    clean=[v for p,v in zip(good,ratios) if p['clean']]
                    def direction(values,expected):
                        if len(values)!=expected or not values:return 'incomplete'
                        return 'Chronicle lower' if max(values)<1 else 'Caffeine lower' if min(values)>1 else 'Equal' if all(v==1 for v in values) else 'Mixed'
                    bounds={b:[min(v),max(v)] if (v:=[p['by'][b]['latency'][channel]['percentilesNs'][percentile] for p in good]) else None for b in BACKENDS}
                    output.append(dict(batch=stage['attempt'],cohort=stage['label'],seed=stage['seed'],ballastMiB=live,channel=channel,percentile=percentile,
                        expectedPairs=stage['passes'],validPairs=len(good),warningFreePairs=len(clean),pairedRatios=ratios,backendRangesNs=bounds,
                        pairedBlocks=[p['block'] for p in good],
                        direction=direction(ratios,stage['passes']),cleanDirection=direction(clean,len(clean)),
                        cleanPairedRatios=clean,replication='three paired forks' if stage['passes']==3 else 'single pair; descriptive seed check',
                        adaptive=stage['label'].startswith('adaptive'),confidenceInterval=None))
    return output


def run(master,out):
    state=load(master/'state.json')
    assert state['complete'] and state['sourceUnchanged'] and state['collectedWorkloadForks']<=36
    out.mkdir(exist_ok=False);setup=out/'setup';setup.mkdir();forks=[];tails=[];decoded=[];gc_checks=0;raw_checks=0;inventory_checks=0
    for path,digest in state['historicalDeliveries'].items():assert sha(ROOT/path)==digest
    runtime=None
    for stage in state['stages']:
        base=ROOT/'evidence-archives'/stage['attempt'];summary=load(base/'summary.json');protocol=load(base/'protocol.json')
        assert summary['completeCollection'] and summary['sourceUnchanged']
        assert protocol['sourceSha256']==state['sourceSha256'] and protocol['seed']==stage['seed']
        assert len(summary['results'])==stage['passes']*len(stage['levelsMiB'])*2
        assert [r['label'] for r in summary['results']]==[r['label'] for r in protocol['schedule']]
        assert (protocol['warmupMs'],protocol['conditioningMs'],protocol['measureMs'])==(12000,2000,30000)
        if runtime is None:runtime=protocol['runtimeSha256']
        else:assert runtime==protocol['runtimeSha256']
        for item in load(base/'inventory.json'):
            p=base/item['path'];assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'];inventory_checks+=1
        endpoint_csv=out/(stage['label']+'-hdr-percentiles.csv')
        cmd=['/usr/lib/jvm/java-21-openjdk/bin/java','-Xmx96m','-cp',str(base/'setup')+':'+protocol['classpath'],
            'TailCacheFocusedHdrVerify',str(base),str(endpoint_csv)]
        done=subprocess.run(cmd,capture_output=True,text=True,check=True)
        direct={r['path']:r for r in rows(endpoint_csv)}
        decoded.append(dict(stage=stage['label'],**json.loads(done.stdout)))
        for r in summary['results']:
            raw=base/r['label']
            for path,digest in r['rawSha256'].items():assert sha(raw/path)==digest;raw_checks+=1
            r=dict(r,batch=stage['attempt'],cohort=stage['label'],measureMs=30000,runtimeGroup=hashlib.sha256(json.dumps(runtime,sort_keys=True).encode()).hexdigest())
            if r['status']=='OK' and r['latencyVerified']:
                m=r['measurement'];assert m['operations']==m['scheduled']==1_500_000
                assert r['completion']['unserved']=='0'
                config=dict(line.split('=',1) for line in (raw/'worker/configuration.txt').read_text().splitlines() if '=' in line)
                assert f'seed={stage["seed"]},' in config['config']
                command=load(raw/'command.json')['command'];assert '-Dchronicle.analytics.disable=true' in command
                if r['backend']==BACKENDS[1]:assert 'allowSegmentTiering=true' in config['backendConfig']
                gc=independent.audit_gc(raw/'gc.log',m['startNs'],m['endNs'])
                for k,v in gc.items():assert v==r['gc'][k] or (v is not None and r['gc'][k] is not None and math.isclose(v,r['gc'][k],rel_tol=1e-12,abs_tol=1e-6)),(r['label'],k,v,r['gc'][k])
                gc_checks+=1
                channel_tails={}
                for channel in ('service','gap','response'):
                    p=raw/'worker'/(channel+'.hdr');entry=direct[str(p.resolve())]
                    assert int(entry['count'])==r['latency'][channel]['count']==m['operations']
                    for percent,key in zip(PERCENTILES,('p99Ns','p999Ns','p9999Ns','p99999Ns')):
                        assert int(entry[key])==r['latency'][channel]['percentilesNs'][percent]
                    t=curves.summarize(rows(p.with_name(channel+'-bins.csv')),int(entry['count']))
                    t['hdrPath']=str(p);channel_tails[channel]=t
                    bins=rows(p.with_name(channel+'-bins.csv'))
                    r['latency'][channel]['tailSupport']={percent:dict(
                        nominalUpperTailObservations=m['operations']*(100-float(percent))/100,
                        strictlyAboveSelectedBin=sum(int(v['count']) for v in bins if int(v['upperEquivalentNs'])>r['latency'][channel]['percentilesNs'][percent])) for percent in PERCENTILES}
                tails.append(dict(batch=r['batch'],label=r['label'],channels=channel_tails))
            forks.append(r)
    # The same pinned HDR library independently verifies every bin and threshold bound.
    hdr_paths=[t['hdrPath'] for f in tails for t in f['channels'].values()]
    (setup/'hdr-paths.txt').write_text(''.join(p+'\n' for p in hdr_paths))
    jar=ROOT/'evidence-archives/focused-rq-results-20261108-001/runtime-libraries/HdrHistogram-2.2.2.jar'
    assert sha(jar)=='22d1d4316c4ec13a68b559e98c8256d69071593731da96136640f864fa14fad8'
    helper=ROOT/'scripts/java/TailCacheTailVerify.java'
    subprocess.run(['/usr/lib/jvm/java-21-openjdk/bin/javac','-cp',str(jar),'-d',str(setup),str(helper)],check=True,capture_output=True)
    subprocess.run(['/usr/lib/jvm/java-21-openjdk/bin/java','-Xmx96m','-cp',str(setup)+':'+str(jar),'TailCacheTailVerify',str(setup/'hdr-paths.txt'),str(out/'hdr-threshold-check.csv')],check=True,capture_output=True)
    check={r['path']:r for r in rows(out/'hdr-threshold-check.csv')};threshold_checks=0
    for f in tails:
        for channel,t in f['channels'].items():
            v=check[t['hdrPath']];assert t['binBoundsSha256']==v['binBoundsSha256'] and t['count']==int(v['count'])
            for threshold,label in zip(curves.THRESHOLDS,('gt100us','gt1ms','gt10ms')):
                p=t['rates'][str(threshold)];assert p['lowerCount']==int(v[label+'Lower']) and p['upperCount']==int(v[label+'Upper']);threshold_checks+=1
    by_tail={(t['batch'],t['label']):t for t in tails}
    for r in forks:
        t=by_tail.get((r['batch'],r['label']))
        if t:r['stallRates']={ch:dict(count=v['count'],rates=v['rates']) for ch,v in t['channels'].items()}
    comparisons=conclusions(forks,state['stages'])
    data=dict(kind='fresh-midpoint-follow-up',collectionComplete=True,analysisComplete=True,master=str(master.relative_to(ROOT)),
        sourceSha256=state['sourceSha256'],stages=state['stages'],runtimeFiles=runtime,observations=forks,conclusions=comparisons,
        adaptiveDecision=state['adaptiveDecision'],adaptiveBallastMiB=state['adaptiveBallastMiB'],
        limits=['Cohorts and seeds remain separate; no pooled histograms or confidence intervals.',
                'Warning-bearing observations remain visible. A clean subset does not replace them.',
                '30-second scheduled windows have only about15 nominal p99.999 tail observations, possibly correlated.',
                'Sampled RSS is not total native allocation or an equal-total-memory experiment.',
                'Historical conditional acceptance and original unconditional NO_GO remain unchanged.'])
    save(out/'study.json',data);save(out/'tails.json',dict(forks=tails,thresholdsNs=curves.THRESHOLDS))
    with (out/'conclusions.csv').open('x',newline='') as f:
        fields=['cohort','seed','ballastMiB','channel','percentile','expectedPairs','validPairs','warningFreePairs','direction','cleanDirection','pairedRatios','cleanPairedRatios','adaptive']
        w=csv.DictWriter(f,fields);w.writeheader()
        for r in comparisons:w.writerow({k:r[k] for k in fields})
    with (out/'stall-rates.csv').open('x',newline='') as f:
        w=csv.writer(f);w.writerow(['cohort','seed','ballastMiB','block','backend','channel','count','thresholdNs','definiteCount','possibleCount','lowerProbability','upperProbability','warnings'])
        for r in forks:
            for ch,v in r.get('stallRates',{}).items():
                for threshold,t in v['rates'].items():w.writerow([r['cohort'],r['seed'],r['liveMiB'],r['block'],r['backend'],ch,v['count'],threshold,t['lowerCount'],t['upperCount'],t['lowerProbability'],t['upperProbability'],json.dumps(r['warnings'])])
    blobs=out/'runtime-files';blobs.mkdir()
    for path,digest in runtime.items():
        assert sha(pathlib.Path(path))==digest
        target=blobs/digest
        if not target.exists():shutil.copyfile(path,target)
    shutil.copyfile(pathlib.Path(__file__),out/'analysis-source.py');shutil.copyfile(helper,setup/helper.name)
    audit=dict(passed=True,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),workloadForks=len(forks),
        statusCounts=dict(collections.Counter(r['status'] for r in forks)),warningForks=sum(bool(r['warnings']) for r in forks),
        warnings=dict(collections.Counter(w for r in forks for w in r['warnings'])),decodedHistograms=decoded,
        independentGcChecks=gc_checks,independentThresholdChecks=threshold_checks,rawFilesVerified=raw_checks,inventoryFilesVerified=inventory_checks,
        runtimeFilesVerified=len(runtime),historicalDeliveriesUnchanged=state['historicalDeliveries'],
        studySha256=sha(out/'study.json'),tailsSha256=sha(out/'tails.json'),replacementForks=0)
    save(out/'audit.json',audit)
    for p,digest in state['historicalDeliveries'].items():assert sha(ROOT/p)==digest
    print(json.dumps(audit,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--master',type=pathlib.Path,default=ROOT/'evidence-archives/midpoint-study-20261110-001')
    p.add_argument('--out',type=pathlib.Path,default=ROOT/'evidence-archives/midpoint-results-20261110-001')
    args=p.parse_args();run(args.master.resolve(),args.out.resolve())
