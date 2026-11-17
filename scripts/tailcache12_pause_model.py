#!/usr/bin/env python3
"""Frozen residual-pause models; predictions take GC/schedule/backend, never latency."""
import argparse,collections,csv,hashlib,json,math,pathlib,statistics
from fractions import Fraction

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/predictor'
QS=('99','99.9','99.99','99.999')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(v,m):
    if not v:raise ValueError(m)
def immutable(p,d):
    if p.exists():require(json.loads(p.read_text())==d,'Frozen model differs')
    else:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2)+'\n')

def merge(intervals):
    out=[]
    for a,b in sorted(intervals):
        require(b>=a,'Negative pause interval')
        if a==b:continue
        if out and a<=out[-1][1]:out[-1]=(out[-1][0],max(b,out[-1][1]))
        else:out.append((a,b))
    return out

def residual_quantile(intervals,start,end,q):
    """Finite offered-window, residual-only fluid approximation, integer-ns output."""
    require(end>start and 0<float(q)<100,'Window/quantile')
    ps=[(max(start,a),b) for a,b in merge(intervals) if b>start and a<end]
    budget=(1-Fraction(q)/100)*(end-start)
    def excess(x):return sum(max(0,min(end,b-x)-a) for a,b in ps)
    if excess(0)<=budget:return 0
    lo,hi=0,max(b-a for a,b in ps)
    while lo<hi:
        mid=(lo+hi)//2
        if excess(mid)>budget:lo=mid+1
        else:hi=mid
    return lo

def predict(model,pauses,start,end,backend):
    """M0 clips each pause to offered window; M1 retains actual end and adds frozen offset."""
    require(backend in model['serviceOffsetNs'],'Backend calibration missing')
    intervals=[(int(p['startNs']),int(p['endNs'])) for p in pauses]
    clipped=[(max(a,start),min(b,end)) for a,b in intervals if b>start and a<end]
    m0={q:residual_quantile(clipped,start,end,q) for q in QS}
    residual={q:residual_quantile(intervals,start,end,q) for q in QS}
    m1={q:residual[q]+model['timerBaselineNs'][q]+model['serviceOffsetNs'][backend] for q in QS}
    return dict(M0=m0,M1=m1,residualOnlyNs=residual,
                offeredWindowNs=end-start,totalPauseOverlapNs=sum(b-a for a,b in merge(clipped)),
                limits='GC-conditioned approximation; omits queue drain, non-GC stalls and a full baseline convolution.')

def freeze():
    timer=[];inputs={}
    for attempt in ('service-paced-20261117-001','service-trace-20261117-001','service-geometry-20261117-001'):
        files=[]
        for p in (ROOT/'evidence-archives'/attempt/'controls').glob('*/result.json'):
            r=json.loads(p.read_text())
            if r.get('floor') and not r.get('inject') and r.get('qps')==50000:files.append(p)
        require(len(files)==1,'Exactly one retained timer-only calibration control')
        p=files[0];r=json.loads(p.read_text());inputs[str(p.relative_to(ROOT))]=sha(p)
        timer.append(r['latency']['response']['percentilesNs'])
    path=ROOT/'docs/service-followup/followup-data-20261117.json';inputs[str(path.relative_to(ROOT))]=sha(path)
    old=json.loads(path.read_text())
    offsets={b:statistics.median(r['latency']['service']['percentilesNs']['50'] for r in old['forks']
        if r['cohort']=='paced' and r['payload']==4096 and r['liveMiB']==0 and r['backend']==b)
        for b in ('CAFFEINE','CHRONICLE_IN_MEMORY')}
    model=dict(version='residual-pause-v1',timerBaselineNs={q:statistics.median(t[q] for t in timer) for q in QS},
        serviceOffsetNs=offsets,calibrationInputs=inputs,primary='response p99.9',secondary='response p99.99',
        forecast={'0':'Caffeine lower','50':'Caffeine lower','100':'Unassigned','200':'Chronicle lower','500':'Chronicle lower'},
        distinctions=['Forecast is before-run, GC-conditioned quantiles are after-run explanatory validation.',
                      'Fixed additive timer/service baseline is a heuristic, not exact convolution or floor subtraction.',
                      'M0 residual-only gives zero below budget; score that numerical outcome rather than hide it.'])
    immutable(BASE/'model-v1.json',model);return model

def error_summary(samples):
    if not samples:return dict(n=0)
    absolute=sorted(abs(p-y) for p,y in samples);relative=sorted(abs(p-y)/max(1,y) for p,y in samples)
    logs=sorted(abs(math.log2(max(1,p)/max(1,y))) for p,y in samples)
    def p90(v):return v[min(len(v)-1,math.ceil(.9*len(v))-1)]
    return dict(n=len(samples),medianAbsoluteNs=statistics.median(absolute),p90AbsoluteNs=p90(absolute),
                medianRelativeError=statistics.median(relative),p90RelativeError=p90(relative),medianAbsoluteLog2Error=statistics.median(logs))

def development(model):
    """A development-only audit; never relabel historical data as validation."""
    rows=[];inputs={}
    manifest=BASE/'development-inputs-v1.json'
    if manifest.exists():paths=[ROOT/p for p in json.loads(manifest.read_text())]
    else:
        paths=[]
        for p in sorted((ROOT/'evidence-archives').rglob('result.json')):
            r=json.loads(p.read_text())
            if r.get('regime')=='arrival' and r.get('status')=='OK' and (p.parent/'measured-gc.json').exists() and r.get('measurement',{}).get('offeredEndNs',0)-r.get('measurement',{}).get('startNs',0)>=8_000_000_000:paths.append(p)
        immutable(manifest,[str(p.relative_to(ROOT)) for p in paths])
    for p in paths:
        r=json.loads(p.read_text());gc=p.parent/'measured-gc.json'
        if r.get('regime')!='arrival' or r.get('status')!='OK' or not gc.exists():continue
        m=r['measurement'];start=m['startNs'];end=m['offeredEndNs']
        if end-start<8_000_000_000:continue
        inputs[str(p.relative_to(ROOT))]=sha(p);inputs[str(gc.relative_to(ROOT))]=sha(gc)
        pred=predict(model,json.loads(gc.read_text())['pauses'],start,end,r['backend'])
        row=dict(attempt=p.relative_to(ROOT/'evidence-archives').parts[0],label=r['label'],backend=r['backend'],
            block=r['block'],payload=r['payload'],liveMiB=r['liveMiB'],seed=r.get('seed',24301),
            stage=r.get('stage','historical'),reuse=r.get('reuse',False),warnings=r['warnings'],prediction=pred,
            measured=r['latency']['response']['percentilesNs'])
        rows.append(row)
    numerical={method:{q:error_summary([(r['prediction'][method][q],r['measured'][q]) for r in rows if r['measured'].get(q)])
                       for q in QS} for method in ('M0','M1')}
    groups=collections.defaultdict(dict)
    for r in rows:
        # Labels preserve trace/write/phase treatments in the prefix; strip only the backend suffix.
        import re
        key=(r['attempt'],re.sub(r'-(CAFFEINE|CHRONICLE_IN_MEMORY)(-getUsing)?$','',r['label']))
        groups[key][r['backend']]=r
    scores={}
    for q in QS:
        counts={name:collections.Counter() for name in ('M0','M1','alwaysChronicle','alwaysCaffeine','lowerTotalPause')}
        for arms in groups.values():
            if set(arms)!={'CAFFEINE','CHRONICLE_IN_MEMORY'}:continue
            c,h=[arms[b] for b in ('CAFFEINE','CHRONICLE_IN_MEMORY')]
            if not c['measured'].get(q) or not h['measured'].get(q):continue
            actual=(h['measured'][q]>c['measured'][q])-(h['measured'][q]<c['measured'][q])
            predictions={method:(h['prediction'][method][q]>c['prediction'][method][q])-(h['prediction'][method][q]<c['prediction'][method][q]) for method in ('M0','M1')}
            predictions.update(alwaysChronicle=-1,alwaysCaffeine=1,lowerTotalPause=(h['prediction']['totalPauseOverlapNs']>c['prediction']['totalPauseOverlapNs'])-(h['prediction']['totalPauseOverlapNs']<c['prediction']['totalPauseOverlapNs']))
            for name,direction in predictions.items():
                counts[name]['available']+=1
                if direction==0:counts[name]['abstained']+=1
                else:counts[name]['called']+=1;counts[name]['correct' if direction==actual else 'incorrect']+=1
        scores[q]=counts
    return dict(developmentOnly=True,forks=len(rows),modelSha256=sha(BASE/'model-v1.json'),inputs=inputs,
                numericalAllForks=numerical,pairedScores=scores,observations=rows,
                limits='Posthoc development diagnostics; available raw endpoint coverage differs by percentile. Reuse cohorts labelled separately by attempt; no pooled latency distributions.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['freeze','development']);args=parser.parse_args()
    model=freeze()
    if args.command=='development':
        d=development(model);immutable(BASE/'development-audit-v1.json',d)
        print(json.dumps(dict(forks=d['forks'],scores=d['pairedScores'],errors=d['numericalAllForks']),indent=2))
    else:print(json.dumps(model,indent=2))
