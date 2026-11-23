#!/usr/bin/env python3
"""Package audited prospective cohorts; original packages stay immutable."""
import argparse,collections,csv,hashlib,json,pathlib,statistics,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
import tailcache12_service_package as p
import tailcache12_service_verify as v
import tailcache12_pause_model as m
COHORTS={'qualification':'predictor-qualification-20261118-001','validation':'predictor-validation-20261118-001','confirmation':'predictor-drain-confirm-20261118-001'}
Q=('99','99.9','99.99','99.999')

def load(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def build():
    p.COHORTS=COHORTS.copy();data=p.build(list(COHORTS))
    # Fix serialization order without touching inherited immutable historical packages.
    for pair in data['pairs']:pair['ratios']={ch:pair['ratios'][ch] for ch in ('response','service','read-service','gap','update-service') if ch in pair['ratios']}
    constant=load(ROOT/'docs/predictor/numeric-baseline-v1.json')
    data.update(kind='tailcache-predictor-v1',scope='Prospective adaptive study: qualification, primary validation and fresh secondary holdout remain separate; finite-window/transient qualified')
    data['models']={name:load(ROOT/'docs/predictor'/file) for name,file in [('residual','model-v1.json'),('drain','drain-candidate-v1.json'),('constant','numeric-baseline-v1.json')]}
    data['modelInputs']={file:sha(ROOT/'docs/predictor'/file) for file in ('model-v1.json','drain-candidate-v1.json','drain_candidate.py.txt','numeric-baseline-v1.json')}
    data['freezeCommits']={'originalModelAndStream':'a330849','secondaryDrainBeforePrimaryUnblinding':'afe73bd','freshConfirmation':'bc02258'}
    data['planCompletion']={'allDeclaredCohortsPresent':True,'researchForks':60,'qualificationForks':18,'primaryValidationForks':30,'secondaryConfirmationForks':12,'controlJvms':4,'compilerDiagnosticJvms':1,'functionalJvms':3,'newExpansionAllowed':False,'originalTask12UnconditionalStatus':'NO_GO; unchanged','publicationStatus':'Agent-reviewed working draft; author approval and public release pending'}
    data['limits']=['Qualification is development, primary30 is the original holdout, fresh12 is a separate secondary holdout. No pooled percentiles or successful-only replacement.',
        '120-second warmup did not pass the declared low-write occupancy-stability criterion; transient=true for all new research results. Recorded compiler/host warnings remain visible.',
        'Conditional predictions use measured GC intervals. They do not forecast future GC or guarantee latency. Original before-run crossover forecast failed.',
        'Scalar generator removes a replayed trace array; changes generator work and warmup as well as logical pattern. No isolated lifetime/promotion causal claim.',
        'One host, G1,512MiB heap,4KiB values,32768 residents,50k/s,zero ballast,32MiB/s churn. Paced service is not saturated service.',
        'p99.999 has only about15 nominal upper-tail observations per fork, potentially from shared stall episodes. Ranges are descriptive, not confidence intervals.',
        'M2 uses pilot-derived constant service/bookkeeping; variable service/non-GC stalls/endogenous GC and baseline convolution remain approximations.']
    numerical={};winners={};forecasts={}
    for name,attempt in COHORTS.items():
        base=ROOT/'evidence-archives'/attempt;study=load(base/'study.json');orig=load(base/'predictions-v1.json');score=load(base/'score-v1.json')
        old={r['label']:r for r in study['observations']};pr={r['label']:r['prediction'] for r in orig['observations']}
        dr=load(base/'drain-predictions-v1.json') if (base/'drain-predictions-v1.json').exists() else None
        dp={r['label']:r for r in dr['observations']} if dr else {}
        inputs=data['cohortInputs'][name];inputs.update(primaryChannel='response',transient=True,qualificationRole='Development' if name=='qualification' else 'Original holdout' if name=='validation' else 'Fresh secondary holdout',java=load(base/'setup/environment.json')['java'])
        inputs['derivedInputs']={file:sha(base/file) for file in ('predictions-v1.json','score-v1.json','drain-predictions-v1.json','drain-score-v1.json') if (base/file).exists()}
        inputs['measurementPlan']={'regime':'arrival','qps':50000,'warmupMs':'Per-fork12/60/120s' if name=='qualification' else 120000,'conditioningMs':4000,'measureMs':30000,'continuousScalarStream':True}
        for r in data['forks']:
            if r['cohort']!=name:continue
            source=old[r['label']]
            for k in ('writeBps','warmupMs','conditioningMs','measureMs'):r[k]=source[k]
            r['transient']=True;r['predictionNs']={method:pr[r['label']][method] for method in ('M0','M1')}
            r['predictionNs']['constant']=constant['valuesNs'][r['backend']]
            r['totalGcPauseOverlapNs']=pr[r['label']]['totalPauseOverlapNs']
            gcfile=base/'slots'/r['label']/'measured-gc.json';t0=r['measurement']['startNs'];r['pauseIntervalsNsRelative']=[[int(x['startNs'])-t0,int(x['endNs'])-t0] for x in load(gcfile)['pauses']];r['gcInputSha256']=sha(gcfile);r['offeredWindowNs']=pr[r['label']]['offeredWindowNs']
            if r['label'] in dp:r['predictionNs']['M2']=dp[r['label']]['predictionNs'];r['simulation']=dp[r['label']]['simulation']
        rows=[r for r in data['forks'] if r['cohort']==name];numerical[name]={}
        for subset in ('all','CAFFEINE','CHRONICLE_IN_MEMORY','noRecordedWarnings','warningBearing'):
            selected=[r for r in rows if subset=='all' or r['backend']==subset or subset=='noRecordedWarnings' and not r['warnings'] or subset=='warningBearing' and r['warnings']]
            methods=set.intersection(*(set(r['predictionNs']) for r in rows))
            numerical[name][subset]={method:{q:m.error_summary([(r['predictionNs'][method][q],r['latency']['response']['percentilesNs'][q]) for r in selected]) for q in Q} for method in sorted(methods)} if selected else {}
        winners[name]=dict(score['winnerScores']);forecasts[name]={'original':score['beforeRunForecast'],'originalForecastSupportedInValidation':score['forecastSupportedInValidation']}
        if dr:
            ds=load(base/'drain-score-v1.json');winners[name]['M2_byPercentile']=ds['winnerScores'];inputs['secondaryWorthResult']=ds['worth']
        if name=='confirmation':forecasts[name]['updatedReplication']={str(b):{'expected':'Caffeine lower' if b==0 else 'Chronicle lower','observed':[x['channels']['99.9']['actual'] for x in score['points'] if x['writeBps']==b]} for b in (0,50,500)}
    by={r['id']:r for r in data['forks']}
    for pair in data['pairs']:
        c,h=by[pair['c']],by[pair['h']]
        for k in ('writeBps','warmupMs'):pair[k]=c[k];assert c[k]==h[k]
    for point in data['points']:
        for k in ('writeBps','warmupMs'):point[k]=point['pairs'][0][k];assert all(x[k]==point[k] for x in point['pairs'])
    data.update(numerical=numerical,winnerScores=winners,forecasts=forecasts)
    return data

def main():
    a=argparse.ArgumentParser();a.add_argument('--out',type=pathlib.Path,required=True);x=a.parse_args();d=build();x.out.parent.mkdir(parents=True,exist_ok=True)
    with x.out.open('x') as f:json.dump(d,f,separators=(',',':'));f.write('\n')
    print(json.dumps({'forks':len(d['forks']),'pairs':len(d['pairs']),'points':len(d['points']),'sha256':sha(x.out),'bytes':x.out.stat().st_size}))
if __name__=='__main__':main()
