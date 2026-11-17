#!/usr/bin/env python3
"""Evaluate the frozen pilot-derived queue-drain candidate after primary collection."""
import argparse,collections,hashlib,json,pathlib,runpy,time
import tailcache12_focused as f
import tailcache12_pause_model as m
ROOT=f.evidence.ROOT

def predictions(base):
    path=ROOT/'docs/predictor/drain-candidate-v1.json';params=f.load(path);code=ROOT/'docs/predictor/drain_candidate.py.txt'
    m.require(f.sha(code)==params['solverSha256'],'Frozen secondary solver changed')
    for p,h in params['calibrationInputs'].items():m.require(f.sha(ROOT/p)==h,'Secondary calibration changed')
    state=f.load(base/'state.json');m.require(state['collectionComplete'],'Wait for complete held-out collection')
    m.require(f.load(base/'independent-audit-001/audit.json')['passed'],'Raw audit first')
    out=base/'drain-predictions-v1.json'
    if out.exists():
        data=f.load(out);m.require(data['modelSha256']==f.sha(path),'Retained secondary model mismatch')
        for r in data['observations']:
            for p,h in r['inputs'].items():m.require(f.sha(base/p)==h,'Retained secondary input mismatch')
        return data
    solver=runpy.run_path(str(code));observations=[];started=time.monotonic()
    for r in state['scheduled']:
        directory=base/'slots'/r['label'];windows=f.rows(directory/'worker/windows.csv');w=next(w for w in windows if w['phase']=='MEASUREMENT');gc=directory/'measured-gc.json'
        backend=r['backend'];cost=solver['interpolate'](params['intrinsicServiceNs'][backend],r['writeBps'])
        sim=solver['simulate']([(p['startNs'],p['endNs']) for p in f.load(gc)['pauses']],int(w['startNs']),int(w['offeredEndNs']),1_000_000_000//r['qps'],cost,params['bookkeepingNs'][backend],m.QS)
        m.require(sim['operations']==int(w['scheduled']),'Simulated request conservation')
        values={q:sim['percentilesNs'][q]+params['timerBaselineNs'][q] for q in m.QS}
        observations.append(dict(label=r['label'],backend=backend,writeBps=r['writeBps'],predictionNs=values,
            simulation=sim,serviceNs=cost,bookkeepingNs=params['bookkeepingNs'][backend],
            inputs={str(gc.relative_to(base)):f.sha(gc),str((directory/'worker/windows.csv').relative_to(base)):f.sha(directory/'worker/windows.csv')}))
    result=dict(modelSha256=f.sha(path),solverSha256=f.sha(code),model=params,observations=observations,
        latencyInputsReadByPredictor=False,elapsedSeconds=time.monotonic()-started,
        scope='Pilot-derived secondary candidate frozen before primary holdout unblinding; not the original pre-collection model.',
        limits='Constant service/recording cost plus fixed timer allowance; simulation drain includes final bookkeeping.')
    # Timing is descriptive; reuse an existing immutable prediction rather than regenerate it.
    m.immutable(out,result);return result

def score(base,data):
    study=f.load(base/'study.json');by={r['label']:r for r in study['observations']};p={r['label']:r['predictionNs'] for r in data['observations']}
    numerical={q:m.error_summary([(p[r['label']][q],r['latency']['response']['percentilesNs'][q]) for r in by.values()]) for q in m.QS}
    perbackend={b:{q:m.error_summary([(p[r['label']][q],r['latency']['response']['percentilesNs'][q]) for r in by.values() if r['backend']==b]) for q in m.QS} for b in ('CAFFEINE','CHRONICLE_IN_MEMORY')}
    counts={q:collections.Counter() for q in m.QS};points=[]
    for pair in study['pairs']:
        c,h=[by[pair['labels'][b]] for b in ('CAFFEINE','CHRONICLE_IN_MEMORY')]
        row=dict(writeBps=c['writeBps'],warmupMs=c['warmupMs'],seed=c['seed'],block=c['block'],warningFree=not(c['warnings'] or h['warnings']),quantiles={})
        for q in m.QS:
            pc,ph=p[c['label']][q],p[h['label']][q];cv,hv=[r['latency']['response']['percentilesNs'][q] for r in (c,h)]
            direction=(ph>pc)-(ph<pc);actual=(hv>cv)-(hv<cv);counts[q]['available']+=1
            if direction==0:counts[q]['abstained']+=1
            else:counts[q]['called']+=1;counts[q]['correct' if direction==actual else 'incorrect']+=1
            row['quantiles'][q]=dict(caffeineNs=cv,chronicleNs=hv,predictedCaffeineNs=pc,predictedChronicleNs=ph,actualRatio=hv/cv)
        points.append(row)
    old=f.load(base/'score-v1.json');prior=old['numericalAllForks']['M1']['99.9'];now=numerical['99.9']
    allowed=now['medianAbsoluteNs']<=.75*prior['medianAbsoluteNs'] and now['p90AbsoluteNs']<=1.1*prior['p90AbsoluteNs']
    result=dict(passedIntegrity=True,forks=len(by),predictionsSha256=f.sha(base/'drain-predictions-v1.json'),
        studySha256=f.sha(base/'study.json'),numericalAllForks=numerical,numericalPerBackend=perbackend,winnerScores=counts,points=points,
        worth=dict(rule='M2 median absolute p99.9 error <=75% M1; p90 <=110% M1',M1=prior,M2=now,allowFresh12=allowed),
        scope='Pilot-derived secondary analysis; independent fresh12 are separately declared if worth rule passes.',
        primaryForecastUnchanged=old.get('beforeRunForecast'),primaryForecastSupported=old.get('forecastSupportedInValidation'))
    m.immutable(base/'drain-score-v1.json',result)
    print(json.dumps(dict(forks=len(by),winnerScores=counts,numerical=numerical,worth=result['worth']),indent=2))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('attempt');args=p.parse_args();base=ROOT/'evidence-archives'/args.attempt
    score(base,predictions(base))
