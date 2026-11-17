#!/usr/bin/env python3
"""Write immutable GC-only predictions, then score against complete retained quantiles."""
import argparse,collections,csv,json,pathlib,statistics
import tailcache12_focused as f
import tailcache12_pause_model as m
ROOT=f.evidence.ROOT

def predict(base):
    model_path=ROOT/'docs/predictor/model-v1.json';model=f.load(model_path);state=f.load(base/'state.json');protocol=f.load(base/'protocol.json')
    m.require(state['collectionComplete'],'Predict only complete retained slots')
    expected=protocol['design']['discoveryInputs']['docs/predictor/model-v1.json']
    m.require(f.sha(model_path)==expected,'Frozen model input changed')
    predictions=[]
    for row in state['scheduled']:
        directory=base/'slots'/row['label'];windows=f.rows(directory/'worker/windows.csv');w=next(w for w in windows if w['phase']=='MEASUREMENT')
        gc=directory/'measured-gc.json';p=m.predict(model,f.load(gc)['pauses'],int(w['startNs']),int(w['offeredEndNs']),row['backend'])
        predictions.append(dict(label=row['label'],backend=row['backend'],prediction=p,inputs={str(gc.relative_to(base)):f.sha(gc),str((directory/'worker/windows.csv').relative_to(base)):f.sha(directory/'worker/windows.csv')}))
    value=dict(modelSha256=f.sha(model_path),modelCodeSha256=protocol['sourceFiles']['scripts/tailcache12_pause_model.py'],model=model,observations=predictions,latencyInputsReadByPredictor=False,
        meaning='Conditional on this run GC; before-run write-ratio forecast is separate.')
    m.immutable(base/'predictions-v1.json',value);return value

def score(base):
    predictions=f.load(base/'predictions-v1.json');study=f.load(base/'study.json');by={r['label']:r for r in study['observations']};pred={r['label']:r['prediction'] for r in predictions['observations']}
    for row in predictions['observations']:
        for file,h in row['inputs'].items():m.require(f.sha(base/file)==h,'Prediction input changed')
    numerical={method:{q:m.error_summary([(pred[r['label']][method][q],r['latency']['response']['percentilesNs'][q]) for r in by.values() if r['status']=='OK']) for q in m.QS} for method in ('M0','M1')}
    rows=[];scores={q:{method:collections.Counter() for method in ('M0','M1','alwaysChronicle','alwaysCaffeine','lowerTotalPause')} for q in m.QS}
    for pair in study['pairs']:
        c,h=[by[pair['labels'][b]] for b in ('CAFFEINE','CHRONICLE_IN_MEMORY')];pc,ph=pred[c['label']],pred[h['label']]
        point=dict(stage=c['stage'],writeBps=c['writeBps'],warmupMs=c['warmupMs'],seed=c['seed'],block=c['block'],warningFree=not(c['warnings'] or h['warnings']),channels={})
        for q in m.QS:
            cv=c['latency']['response']['percentilesNs'][q];hv=h['latency']['response']['percentilesNs'][q];actual=(hv>cv)-(hv<cv)
            calls={method:(ph[method][q]>pc[method][q])-(ph[method][q]<pc[method][q]) for method in ('M0','M1')}
            calls.update(alwaysChronicle=-1,alwaysCaffeine=1,lowerTotalPause=(ph['totalPauseOverlapNs']>pc['totalPauseOverlapNs'])-(ph['totalPauseOverlapNs']<pc['totalPauseOverlapNs']))
            point['channels'][q]=dict(caffeineNs=cv,chronicleNs=hv,ratio=hv/cv,actual='Chronicle lower' if actual<0 else 'Caffeine lower' if actual>0 else 'Equal',predictions={method:dict(caffeineNs=pc[method][q],chronicleNs=ph[method][q]) for method in ('M0','M1')})
            for method,call in calls.items():
                scores[q][method]['available']+=1
                if call==0:scores[q][method]['abstained']+=1
                else:scores[q][method]['called']+=1;scores[q][method]['correct' if call==actual else 'incorrect']+=1
        rows.append(point)
    forecast=[]
    for bps in (0,50,100,200,500):
        selected=[r for r in rows if r['writeBps']==bps];directions=[r['channels']['99.9']['actual'] for r in selected]
        expected=predictions['model']['forecast'][str(bps)]
        forecast.append(dict(writeBps=bps,expected=expected,observedDirections=directions,
                             repeatedDirection=bool(directions) and len(set(directions))==1,
                             allMatchForecast=bool(directions) and all(d==expected for d in directions) if expected!='Unassigned' else None))
    value=dict(passedIntegrity=True,studySha256=f.sha(base/'study.json'),predictionsSha256=f.sha(base/'predictions-v1.json'),
               kind=study['kind'],forks=len(by),pairs=len(rows),numericalAllForks=numerical,winnerScores=scores,beforeRunForecast=forecast,points=rows,
               noRecordedWarnings=sum(not r['warnings'] for r in by.values()),warningBearing=sum(bool(r['warnings']) for r in by.values()),
               limits=['Qualification is development, not held-out validation.','Conditional prediction uses observed GC, not a before-run GC forecast.',
                       'Three pairs/point are descriptive; no significance or exact threshold claim.','No negative/error outcome removed or pooled percentile.'])
    value['forecastSupportedInValidation']=(all(p['allMatchForecast'] and len(p['observedDirections'])==3 for p in forecast if p['expected']!='Unassigned') if study['kind']=='predictor-validation' else None)
    m.immutable(base/'score-v1.json',value)
    print(json.dumps(dict(kind=study['kind'],forks=len(by),forecast=forecast,numerical=value['numericalAllForks'],winnerScores=scores),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['predict','score']);p.add_argument('attempt');a=p.parse_args();base=ROOT/'evidence-archives'/a.attempt
    predict(base) if a.command=='predict' else score(base)
