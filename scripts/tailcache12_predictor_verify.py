#!/usr/bin/env python3
"""Independent portable model/rank/accounting checks, without raw-host paths."""
import argparse,collections,hashlib,json,math,pathlib,statistics
from fractions import Fraction
import tailcache12_service_verify as base
Q=('99','99.9','99.99','99.999')

def errors(samples):
    if not samples:return {'n':0}
    a=sorted(abs(x-y) for x,y in samples);r=sorted(abs(x-y)/max(1,y) for x,y in samples);z=sorted(abs(math.log2(max(1,x)/max(1,y))) for x,y in samples);idx=math.ceil(.9*len(a))-1
    return dict(n=len(a),medianAbsoluteNs=statistics.median(a),p90AbsoluteNs=a[idx],medianRelativeError=statistics.median(r),p90RelativeError=r[idx],medianAbsoluteLog2Error=statistics.median(z))

def residual(pauses,t,q,clip):
    merged=[]
    for a,b in sorted(pauses):
        base.require(b>=a,'Negative portable pause')
        if b<=0 or a>=t:continue
        a=max(0,a);b=min(t,b) if clip else b
        if merged and a<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],b)
        else:merged.append([a,b])
    budget=(1-Fraction(q)/100)*t
    excess=lambda x:sum(max(0,min(t,b-x)-a) for a,b in merged)
    if excess(0)<=budget:return 0
    low,high=0,max(b-a for a,b in merged)
    while high>low:
        mid=(high+low)//2
        if excess(mid)>budget:low=mid+1
        else:high=mid
    return low

def verify(d):
    out=base.verify(d,final=False);base.require(d['kind']=='tailcache-predictor-v1','Predictor package kind');fs={r['id']:r for r in d['forks']};counts=collections.Counter()
    base.require(collections.Counter(r['cohort'] for r in fs.values())=={'qualification':18,'validation':30,'confirmation':12},'Exact60 research forks')
    for name,file in [('residual','model-v1.json'),('drain','drain-candidate-v1.json'),('constant','numeric-baseline-v1.json')]:
        digest=hashlib.sha256((json.dumps(d['models'][name],indent=2)+'\n').encode()).hexdigest()
        base.require(digest==d['modelInputs'][file],'Frozen model byte identity')
    for r in fs.values():
        base.require(r['transient'] and r['qps']==50000 and r['liveMiB']==0 and r['payload']==4096,'Scope label')
        base.require(r['measurement']['operations']==1500000 and r['offeredWindowNs']==30000000000,'Offered support')
        for q in Q:
            model=d['models']['residual'];p0=residual(r['pauseIntervalsNsRelative'],r['offeredWindowNs'],q,True);p1=residual(r['pauseIntervalsNsRelative'],r['offeredWindowNs'],q,False)+model['timerBaselineNs'][q]+model['serviceOffsetNs'][r['backend']]
            base.same(p0,r['predictionNs']['M0'][q],'Reconstructed M0');base.same(p1,r['predictionNs']['M1'][q],'Reconstructed M1')
            base.same(r['predictionNs']['constant'][q],d['models']['constant']['valuesNs'][r['backend']][q],'Constant comparator')
            counts['reconstructedModelValues']+=3
    for pair in d['pairs']:
        c,h=fs[pair['c']],fs[pair['h']]
        for k in ('writeBps','warmupMs'):
            base.require(c[k]==h[k]==pair[k],'Paired writerate/warmup')
        base.require(c['measurement']['writes']==h['measurement']['writes'],'Paired actual writes')
        counts['matchedStreams']+=1
    for point in d['points']:
        for pair in point['pairs']:
            base.require(all(point[k]==pair[k] for k in ('writeBps','warmupMs')),'Point writerate/warmup')
    for cohort,subsets in d['numerical'].items():
        for subset,methods in subsets.items():
            rows=[r for r in fs.values() if r['cohort']==cohort and (subset=='all' or r['backend']==subset or subset=='noRecordedWarnings' and not r['warnings'] or subset=='warningBearing' and r['warnings'])]
            for method,quantiles in methods.items():
                for q,e in quantiles.items():
                    actual=errors([(r['predictionNs'][method][q],r['latency']['response']['percentilesNs'][q]) for r in rows])
                    base.require(set(e)==set(actual),'Error summary fields')
                    for k in e:base.same(e[k],actual[k],'Independent numerical error')
                    counts['numericalSummaries']+=1
    for cohort in d['cohortInputs']:
        ps=[p for p in d['pairs'] if p['cohort']==cohort]
        for q in Q:
            methods=['M0','M1','alwaysChronicle','alwaysCaffeine','lowerTotalPause']+(['M2'] if cohort!='qualification' else [])
            for method in methods:
                expected=collections.Counter()
                for pair in ps:
                    c,h=fs[pair['c']],fs[pair['h']];cv,hv=c['latency']['response']['percentilesNs'][q],h['latency']['response']['percentilesNs'][q]
                    actual=(hv>cv)-(hv<cv)
                    if method=='alwaysChronicle':call=-1
                    elif method=='alwaysCaffeine':call=1
                    elif method=='lowerTotalPause':call=(h['totalGcPauseOverlapNs']>c['totalGcPauseOverlapNs'])-(h['totalGcPauseOverlapNs']<c['totalGcPauseOverlapNs'])
                    else:call=(h['predictionNs'][method][q]>c['predictionNs'][method][q])-(h['predictionNs'][method][q]<c['predictionNs'][method][q])
                    expected['available']+=1
                    if call==0:expected['abstained']+=1
                    else:expected['called']+=1;expected['correct' if call==actual else 'incorrect']+=1
                recorded=d['winnerScores'][cohort]['M2_byPercentile'][q] if method=='M2' else d['winnerScores'][cohort][q][method]
                base.require(dict(expected)==recorded,'Independent winner/baseline score')
                counts['winnerSummaries']+=1
        for forecast in d['forecasts'][cohort]['original']:
            bps=forecast['writeBps'];rs=[p['ratios']['response']['99.9'] for p in ps if p['writeBps']==bps]
            directions=['Chronicle lower' if v<1 else 'Caffeine lower' if v>1 else 'Equal' for v in rs]
            # Scorer and package preserve different valid schedules; compare directions without sorting away contrary outcomes.
            base.require(collections.Counter(directions)==collections.Counter(forecast['observedDirections']),'Original forecast observations')
            base.require(forecast['expected']==d['models']['residual']['forecast'][str(bps)],'Frozen exante forecast')
            expected=None if forecast['expected']=='Unassigned' else bool(directions) and all(x==forecast['expected'] for x in directions)
            base.require(forecast['allMatchForecast']==expected,'Original forecast success')
            counts['forecastPoints']+=1
    for bps,r in d['forecasts']['confirmation']['updatedReplication'].items():
        rs=[p['ratios']['response']['99.9'] for p in d['pairs'] if p['cohort']=='confirmation' and p['writeBps']==int(bps)]
        directions=['Chronicle lower' if v<1 else 'Caffeine lower' if v>1 else 'Equal' for v in rs]
        base.require(collections.Counter(directions)==collections.Counter(r['observed']),'Fresh replication forecast observations')
        base.require(r['expected']==('Caffeine lower' if int(bps)==0 else 'Chronicle lower'),'Frozen updated forecast')
        counts['forecastPoints']+=1
    out.update(predictorCounts=dict(counts),researchForks=60,controls=4,separateCompilerDiagnostic=1,separateFunctionalJvms=3,
        limits='Independent portable representation/arithmetic and M0/M1 reconstruction. M2 replay uses its separately frozen algorithm, not an independent implementation. Qualification remains transient; no human peer review.')
    return out
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('package',type=pathlib.Path);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args();d=json.loads(a.package.read_text());r=verify(d);r['packageSha256']=hashlib.sha256(a.package.read_bytes()).hexdigest();a.out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
