#!/usr/bin/env python3
"""Final independent export/raw/archive/order binding; no performance JVMs."""
import argparse,collections,hashlib,json,pathlib,tarfile
ROOT=pathlib.Path(__file__).resolve().parents[1];BASE=ROOT/'docs/mechanism'
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def need(v,m):
 if not v:raise ValueError(m)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--out',type=pathlib.Path,default=BASE/'final-evidence-review.json');args=parser.parse_args()
 import tailcache12_mechanism_report as portable
 d=load(BASE/'mechanism-data-20261118.json');portable.verify(d);fs={r['id']:r for r in d['forks']};counts=collections.Counter();orders={};functional={};smokes={}
 for cohort,meta in d['cohorts'].items():
  root=ROOT/'evidence-archives'/meta['attempt'];protocol=load(root/'protocol.json');study=load(root/'study.json');state=load(root/'state.json');need(state['complete'] and study['collectionComplete'],'Complete cohort')
  for name,digest in meta['inputs'].items():need(sha(root/name)==digest,'Export input hash '+name)
  with tarfile.open(root/'source.tar.gz','r:gz') as t:
   sources={m.name:hashlib.sha256(t.extractfile(m).read()).hexdigest() for m in t if m.isfile()}
  need(sources==protocol['sourceFiles'],'Archived source coverage');counts['sourceFiles']+=len(sources)
  for index,item in enumerate(protocol['classpath'].split(':')):
   original=pathlib.Path(item);dest=root/'runtime'/str(index)
   for name,digest in protocol['runtimeSha256'].items():
    p=pathlib.Path(name)
    if name==item:target=dest/p.name
    elif p.is_relative_to(original):target=dest/p.relative_to(original)
    else:continue
    need(sha(target)==digest,'Runtime hash');counts['runtimeFiles']+=1
  for name,digest in protocol['preservedPaperInputs'].items():need(sha(ROOT/name)==digest,'Historical evidence changed')
  for name,target in [('functional-validation.json',functional),('runner-smoke-receipt.json',smokes)]:
   path=root/'setup'/name;target[sha(path)]=load(path)
  observations=[(r,root/'slots'/r['label']) for r in study['observations']]+[(load(p),p.parent) for p in (root/'controls').glob('*/service-result.json')]
  for row,directory in observations:
   for name,digest in row['rawSha256'].items():need(sha(directory/name)==digest,'Raw source changed');counts['rawFiles']+=1
   if (directory/'worker/windows.csv').exists():
    need(all(int(w['unexportedStallEvents'])==0 for w in row['windows']),'Sparse overflow')
   need(row['status']=='OK' and row['latencyVerified'] and row['logComplete'],'Preserved invalid/drop outcome requires adjudication')
  if meta['score']:
   need(load(root/'score-v1.json')==meta['score'] and sha(root/'predictions-v1.json')==meta['score']['predictionsSha256'],'Model scoring binding')
   for pr in load(root/'predictions-v1.json')['observations']:
    for name,digest in pr['inputs'].items():need(sha(root/name)==digest,'Model input hash')
    need(fs[cohort+'/'+pr['label']]['predictionNs']==pr['predictions'],'Portable model output')
  exported=[r for r in fs.values() if r['cohort']==cohort];need(len(exported)==len(study['observations']),'Export coverage')
  for row in study['observations']:
   r=fs[cohort+'/'+row['label']]
   for key,value in row.items():need(r[key]==value,'Exported raw-derived field changed: '+key)
   need(r['measuredPauses']==load(root/'slots'/row['label']/'measured-gc.json')['pauses'],'Portable GC');counts['researchForks']+=1
  need(state['scheduled']==protocol['design']['schedule'],'Actual schedule differs')
  for i in range(0,len(state['scheduled']),2):
   a,b=state['scheduled'][i:i+2];need(a['backend']!=b['backend'],'Pair order');orders[cohort,a['seed'],a['hotset'],a['heapMiB'],a['writeBps'],a['primeCalls'],a['logging'],a['repeat']]=a['backend'];counts['pairedOrders']+=1
  for p in study['pairs']:
   a,b=[next(r for r in study['observations'] if r['label']==p['labels'][backend]) for backend in ('CAFFEINE','CHRONICLE_IN_MEMORY')];need([(w['phase'],w['writes']) for w in a['windows']]==[(w['phase'],w['writes']) for w in b['windows']],'Paired writes')
 for seed in (54821,54822):
  for hot in (2048,32768):need(orders['hotset-screen',seed,hot,512,500,0,'async',1]!=orders['hotset-repeat',seed,hot,512,500,0,'async',2],'Hotset order reversal')
 for seed in (54831,54832):need(orders['transition',seed,32768,512,50,0,'async',1]!=orders['transition',seed,32768,512,50,0,'async',2],'Transition order reversal')
 for heap in (512,1024):
  for write in (50,500):need(orders['headroom-screen',54841,32768,heap,write,0,'async',1]!=orders['headroom-confirm',54842,32768,heap,write,0,'async',1],'Fresh headroom reverse')
 preserved={'docs/predictor/predictor-data-20261118.json':'739f320069368711d62b4882aa3fc2a354fc8e787063cc7818cae4c9d2ea36cc','docs/preprint/paper-data.json':'a733eee906a863be68e7fd09ef9e6d3b51cf148ae69f5401c4a0706912ea50b7','docs/service-followup/followup-data-20261117.json':'8d6468c0b7615f0afe03841b8992cd6ea8a0e14ca2b4f00da383e4aa36222aef'}
 for name,h in preserved.items():need(sha(ROOT/name)==h,'Prior published package changed')
 need(counts['researchForks']==64 and counts['pairedOrders']==32,'Scope counts')
 manifest=load(BASE/'render-manifest-20261118.json');need(manifest['inputSha256']==sha(BASE/'mechanism-data-20261118.json'),'Figure data binding')
 for name,h in manifest['outputs'].items():need(sha(BASE/name)==h,'Figure hash')
 warnings=collections.Counter(w for r in fs.values() for w in r['warnings']);receipt=dict(sharedFunctionalSetup=dict(uniqueFunctionalReceipts=len(functional),uniqueSmokeReceipts=len(smokes),actualFunctionalJvms=sum(r['functionalJvms'] for r in functional.values())+sum(r['functionalJvms'] for r in smokes.values()),metadataClarification='Frozen qualification/logging functionalValidationJvms=3 describe the same shared setup; functionalReceiptReused=false is incorrect metadata. Functional commands ran once before qualification, not again in logging. All copied receipt identities and source branches are retained.'),passed=True,datasetSha256=sha(BASE/'mechanism-data-20261118.json'),counts=dict(counts),warningBearingForks=sum(bool(r['warnings']) for r in fs.values()),warnings=dict(warnings),evacuationFailureForks=sum(bool(r['gc']['measuredEvacuationFailures']) for r in fs.values()),fullGcForks=sum(bool(r['gc']['fullGcCount']) for r in fs.values()),historicalPackageSha256=preserved,limits='Fresh byte/archive/export/order reconciliation; uses already decoded source-bound raw HDR receipts. Agent-assisted review is not independent human peer review or host replication.')
 args.out.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
