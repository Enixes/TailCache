#!/usr/bin/env python3
"""Offline fairness/chronology/coverage review; never launches performance JVMs."""
import argparse,collections,hashlib,json,pathlib
import tailcache12_mechanism_report as portable
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--out',type=pathlib.Path,required=True);args=parser.parse_args();raw=(ROOT/'docs/mechanism/mechanism-data-20261118.json').read_bytes();d=json.loads(raw);verification=portable.verify(d)
 forks=d['forks'];fs={r['id']:r for r in forks};checks=collections.Counter();chronology=[]
 for cohort,meta in d['cohorts'].items():
  scheduled=meta['protocol']['design']['schedule'];rows=[r for r in forks if r['cohort']==cohort]
  ordered=sorted(rows,key=lambda r:int(r['windows'][0]['startNs']))
  portable.check([r['label'] for r in ordered]==[s['label'] for s in scheduled],'Physical phase chronology vs declared schedule');checks['chronologicalForks']+=len(rows)
  chronology.extend((int(r['windows'][0]['startNs']),int(r['windows'][-1]['endNs']),r['id']) for r in rows)
 chronology.sort();portable.check(all(a[1]<b[0] for a,b in zip(chronology,chronology[1:])),'Overlapping benchmark windows')
 fair=[]
 for cohort in ('hotset-screen','hotset-repeat'):
  for seed in (54821,54822):
   by={(r['hotset'],r['backend']):r for r in forks if r['cohort']==cohort and r['seed']==seed}
   for backend in ('CAFFEINE','CHRONICLE_IN_MEMORY'):
    a,b=[by[h,backend] for h in (2048,32768)]
    portable.check([(w['phase'],w['writes'],w['operations']) for w in a['windows']]==[(w['phase'],w['writes'],w['operations']) for w in b['windows']],'Cross-treatment logical write/operation demand')
    fair.append(dict(cohort=cohort,seed=seed,backend=backend,workerBytesPerOperation=[a['measurement']['workerBytesPerOperation'],b['measurement']['workerBytesPerOperation']],absoluteBytesPerOperationDifference=abs(a['measurement']['workerBytesPerOperation']-b['measurement']['workerBytesPerOperation'])))
 hot={}
 for keys in (2048,32768):
  pairs=[p for p in d['pairs'] if p['cohort'].startswith('hotset-') and fs[p['c']]['hotset']==keys]
  hot[str(keys)]=dict(pairs=len(pairs),entirelyWarningFree=sum(not(fs[p['c']]['warnings'] or fs[p['h']]['warnings']) for p in pairs),directions={q:{'caffeineLower':sum(p['ratios']['response'][q]>1 for p in pairs),'chronicleLower':sum(p['ratios']['response'][q]<1 for p in pairs)} for q in ('99.9','99.99','99.999')})
 churn=[r['measurement']['achievedChurnPayloadBytesPerSecond']/(32*1024**2) for r in forks]
 result=dict(passed=True,datasetSha256=hashlib.sha256(raw).hexdigest(),verification=verification,chronology=dict(checkedForks=checks['chronologicalForks'],nonOverlapping=True),crossTreatmentFairness=fair,realizedChurnDemandFractionRange=[min(churn),max(churn)],hotsetWarningCoverageAndTails=hot,durationComparison=dict(longWindowSeeds=sorted({r['seed'] for r in forks if r['cohort']=='transition'}),contraryShortWindowSeed=54842,durationEffectIsolated=False,reason='Seeds, collection time and cohort differ; no matched30/90-second intervention'),limits='Descriptive re-analysis of frozen data, not new performance evidence or independent human review.')
 with args.out.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
 print(json.dumps(result))
if __name__=='__main__':main()
