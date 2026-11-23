#!/usr/bin/env python3
"""Development-only safepoint sensitivity and raw stall-envelope review; no JVMs."""
import collections,csv,hashlib,json,pathlib,re,runpy,statistics,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
import tailcache12_pause_model as model
D=json.loads((ROOT/'docs/predictor/predictor-data-20261118.json').read_text());params=D['models']['drain'];solver=runpy.run_path(str(ROOT/'docs/predictor/drain_candidate.py.txt'));QS=model.QS
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(ROOT/'docs/predictor/drain_candidate.py.txt')==params['solverSha256']
def overlap(ps,a,b):return sum(max(0,min(y,b)-max(x,a)) for x,y in solver['merge'](ps))
def parse(lines):
 out=[]
 for line in lines:
  if '[safepoint' not in line:continue
  stamp=re.search(r'\[([0-9]+)ns\]',line);name=re.search(r'Safepoint "([^"]+)"',line)
  fields={k:int(v) for k,v in re.findall(r'(Reaching safepoint|Cleanup|At safepoint|Leaving safepoint|Total): ([0-9]+) ns',line)}
  if not(stamp and name and 'Total' in fields):continue
  end=int(stamp[1]);assert sum(fields[k] for k in fields if k!='Total')==fields['Total']
  out.append(dict(name=name[1],end=end,**fields))
 return out
results=[];started=time.monotonic()
for row in D['forks']:
 if row['cohort']=='qualification':continue
 base=ROOT/'evidence-archives'/row['sourceAttempt'];directory=base/'slots'/row['label'];assert sha(base/'study.json')==D['cohortInputs'][row['cohort']]['studySha256'];study=json.loads((base/'study.json').read_text());original=next(x for x in study['observations'] if x['label']==row['label'])
 log=directory/'gc-through-measurement.log';eventsfile=directory/'worker/stalls.csv'
 for file in (log,eventsfile):assert sha(file)==original['rawSha256'][str(file.relative_to(directory))]
 a=row['measurement']['startNs'];end=row['measurement']['endNs'];t=row['offeredWindowNs'];gc=row['pauseIntervalsNsRelative'];safe=parse(log.read_text().splitlines())
 assert abs(overlap([(x['end']-x['Total'],x['end']) for x in safe],a,end)/1e6-row['gc']['safepointOverlapMs'])<1e-9
 total=[(x['end']-x['Total']-a,x['end']-a) for x in safe if x['end']>a and x['end']-x['Total']<a+t]
 # Excluding reach time is still only an approximate VM-envelope sensitivity, not a measured worker stop interval.
 core=[(x['end']-(x['Total']-x['Reaching safepoint'])-a,x['end']-a) for x in safe if x['end']>a and x['end']-x['Total']<a+t]
 detail=[];non_gc=[]
 with eventsfile.open() as f:
  for e in csv.DictReader(f):
   p,s,z=(int(e[k])-a for k in ('previousEndNs','operationStartNs','operationEndNs'));ov=overlap(gc,p,z)
   if not ov:non_gc.append(z-p);continue
   matched=[(x,y) for x,y in gc if y>p and x<z]
   detail.append({'spanNs':z-p,'gcOverlapNs':ov,'extraEnvelopeNs':z-p-ov,'beforeGcFromOperationStartNs':max(0,min(x for x,y in matched)-s),'afterLastGcEndNs':max(0,z-max(y for x,y in matched))})
 p={}
 for variant,ps in [('gcPlusSafepointCore',gc+core),('gcPlusSafepointTotal',gc+total)]:
  sim=solver['simulate'](ps,0,t,20000,solver['interpolate'](params['intrinsicServiceNs'][row['backend']],row['writeBps']),params['bookkeepingNs'][row['backend']],QS)
  p[variant]={q:sim['percentilesNs'][q]+params['timerBaselineNs'][q] for q in QS}
 stats=lambda xs:dict(n=len(xs),median=statistics.median(xs) if xs else None,p90=sorted(xs)[min(len(xs)-1,__import__('math').ceil(.9*len(xs))-1)] if xs else None)
 result={'id':row['id'],'cohort':row['cohort'],'backend':row['backend'],'writeBps':row['writeBps'],'seed':row['seed'],'warnings':row['warnings'],'measuredNs':{q:row['latency']['response']['percentilesNs'][q] for q in QS},'frozenM2Ns':row['predictionNs']['M2'],'variants':p,'gcMs':overlap(gc,0,t)/1e6,'safepointMs':overlap(total,0,t)/1e6,'safepointCoreMs':overlap(core,0,t)/1e6,'gcAssociatedSparseEvents':len(detail),'unassociatedSparseEvents':len(non_gc),'unassociatedSparseSpanNs':sum(non_gc),'extraGcEnvelopeNs':stats([x['extraEnvelopeNs'] for x in detail]),'postGcReturnNs':stats([x['afterLastGcEndNs'] for x in detail]),'inputs':{str(x.relative_to(ROOT)):sha(x) for x in (log,eventsfile)}}
 results.append(result);print('REVIEW',len(results),row['cohort'],row['backend'],row['writeBps'],flush=True)
summary={}
for cohort in ('validation','confirmation'):
 summary[cohort]={}
 for backend in ('all','CAFFEINE','CHRONICLE_IN_MEMORY'):
  rs=[r for r in results if r['cohort']==cohort and (backend=='all' or r['backend']==backend)]
  summary[cohort][backend]={method:{q:model.error_summary([(r['frozenM2Ns'][q] if method=='frozenM2' else r['variants'][method][q],r['measuredNs'][q]) for r in rs]) for q in QS} for method in ('frozenM2','gcPlusSafepointCore','gcPlusSafepointTotal')}
schedule_audits={};evacuation={}
for cohort in ('validation','confirmation'):
 attempt=D['cohortInputs'][cohort]['attempt'];base=ROOT/'evidence-archives'/attempt;protocol=json.loads((base/'protocol.json').read_text())
 assert sha(base/'protocol.json')==D['cohortInputs'][cohort]['protocolSha256']
 grouped=collections.defaultdict(list)
 for row in protocol['design']['schedule']:grouped[row['writeBps'],row['seed'],row['block']].append(row['backend'])
 counts=collections.defaultdict(collections.Counter)
 for (w,seed,block),arms in grouped.items():
  assert set(arms)=={'CAFFEINE','CHRONICLE_IN_MEMORY'}
  counts[str(w)]['CaffeineFirst' if arms[0]=='CAFFEINE' else 'ChronicleFirst']+=1
 schedule_audits[cohort]={'protocolSha256':sha(base/'protocol.json'),'byWriteBps':{k:dict(v) for k,v in counts.items()}}
 evacuation[cohort]={}
 for backend in ('CAFFEINE','CHRONICLE_IN_MEMORY'):
  rows=[r for r in D['forks'] if r['cohort']==cohort and r['backend']==backend];by_write={}
  for w in sorted({r['writeBps'] for r in rows}):
   selected=[r for r in rows if r['writeBps']==w];by_write[str(w)]={'forks':len(selected),'forksWithMeasuredEvacuationFailure':sum(bool(r['gc']['measuredEvacuationFailures']) for r in selected),'totalMeasuredEvacuationFailures':sum(r['gc']['measuredEvacuationFailures'] for r in selected),'fullGcs':sum(r['gc']['fullGcCount'] for r in selected)}
  evacuation[cohort][backend]=by_write
qualified=ROOT/'evidence-archives/predictor-qualification-20261118-001/slots';directory=next(qualified.glob('qualification-w50-warm120000*CAFFEINE'));r=json.loads((directory/'service-result.json').read_text());gc=json.loads((directory/'measured-gc.json').read_text());a=r['measurement']['startNs'];end=r['measurement']['endNs'];mid=(a+end)//2;halves=[]
for x,y in ((a,mid),(mid,end)):
 ps=[v for v in gc['pauses'] if x<=v['endNs']<y and v.get('heapAfterBytes') is not None]
 halves.append({'count':len(ps),'postGcMiB':[v['heapAfterBytes']/1048576 for v in ps],'medianHeapFraction':statistics.median(v['heapAfterBytes']/v['heapCapacityBytes'] for v in ps),'collectionKinds':dict(collections.Counter(v['kind'] for v in ps))})
for row in results:
 for variant in row['variants'].values():
  assert all(variant[q]>=row['frozenM2Ns'][q] for q in QS),'Superset pause monotonicity'
output={'developmentOnly':True,'heldOutValidation':False,'newJvms':0,'parametersChanged':False,'frozenModelChanged':False,'elapsedSeconds':time.monotonic()-started,'scriptSha256':sha(pathlib.Path(__file__)),'scheduleAudits':schedule_audits,'evacuationFailures':evacuation,'qualificationHalfWindowKinds':halves,'packageSha256':sha(ROOT/'docs/predictor/predictor-data-20261118.json'),'solverSha256':params['solverSha256'],'observations':results,'summary':summary,'limits':['Posthoc diagnostic selected after seeing all42 results; neither new model nor validation.','Full safepoint envelopes include reaching time while individual workers may still execute. Core excludes reaching but log endpoints are approximate worker-stop proxies.','Union GC and safepoints avoids double counting; never add their totals.','Sparse events retain gaps>=1ms; lack of unassociated events does not rule out shorter non-GC stalls. Extra envelope includes legitimate service, pacing and runtime work; it is not pure overhead.']}
import argparse
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=pathlib.Path,required=True);args=parser.parse_args()
with args.out.open('x') as stream:stream.write(json.dumps(output,indent=2)+'\n')
print('REVIEW_ANALYSIS_COMPLETE',flush=True)
