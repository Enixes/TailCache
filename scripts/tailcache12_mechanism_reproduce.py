#!/usr/bin/env python3
"""Replay frozen conditional models from the portable mechanism dataset only."""
import argparse,hashlib,json,math,pathlib,runpy,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1];DATA=ROOT/'docs/mechanism/mechanism-data-20261118.json'
def check(v,m):
 if not v:raise ValueError(m)
def main():
 a=argparse.ArgumentParser();a.add_argument('--data',type=pathlib.Path,default=DATA);a.add_argument('--out',type=pathlib.Path);args=a.parse_args();raw=args.data.read_bytes();d=json.loads(raw);counts={};Q=('99','99.9','99.99','99.999')
 for name,record in d['frozenModelFiles'].items():check(hashlib.sha256(record['text'].encode()).hexdigest()==record['sha256'],'Portable source hash')
 with tempfile.TemporaryDirectory(prefix='tailcache-mechanism-replay-') as tmp:
  out=pathlib.Path(tmp)
  for name,r in d['frozenModelFiles'].items():(out/pathlib.Path(name).name).write_text(r['text'])
  solver=runpy.run_path(str(out/'drain_candidate.py.txt'));model=runpy.run_path(str(out/'tailcache12_pause_model.py'));params=json.loads((out/'drain-candidate-v1.json').read_text());residual=json.loads((out/'model-v1.json').read_text());constant=json.loads((out/'numeric-baseline-v1.json').read_text())
  for r in d['forks']:
   if r['predictionOutsideCalibration']:check(not r['predictionNs'],'Out-of-calibration target');continue
   w=next(w for w in r['windows'] if w['phase']=='MEASUREMENT');a,b=int(w['startNs']),int(w['offeredEndNs']);ps=[(p['startNs'],p['endNs']) for p in r['measuredPauses']];base=model['predict'](residual,r['measuredPauses'],a,b,r['backend']);expected={k:base[k] for k in ('M0','M1')};expected['constant']=constant['valuesNs'][r['backend']]
   for name,extra in [('M2',[]),('M3core',[(s['endNs']-(s['Total']-s['Reaching safepoint']),s['endNs']) for s in r['safepoints']]),('M3total',[(s['endNs']-s['Total'],s['endNs']) for s in r['safepoints']])]:
    sim=solver['simulate'](ps+extra,a,b,1_000_000_000//r['qps'],solver['interpolate'](params['intrinsicServiceNs'][r['backend']],r['writeBps']),params['bookkeepingNs'][r['backend']],Q);check(sim['operations']==int(w['scheduled']),'Request accounting');expected[name]={q:sim['percentilesNs'][q]+params['timerBaselineNs'][q] for q in Q}
   for name,values in expected.items():
    for q,v in values.items():check(math.isclose(v,r['predictionNs'][name][q],rel_tol=1e-12,abs_tol=1e-6),'Model output');counts[name]=counts.get(name,0)+1
 receipt=dict(passed=True,datasetSha256=hashlib.sha256(raw).hexdigest(),quantilesByMethod=counts,limits='Exact replay uses the same frozen algorithms; independent arithmetic/HDR audits are separate. No independent model implementation or host performance replication.')
 if args.out:args.out.write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt))
if __name__=='__main__':main()
