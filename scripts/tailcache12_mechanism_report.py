#!/usr/bin/env python3
"""Portable mechanism evidence; each fork and quantile stays separate."""
import argparse,collections,csv,hashlib,json,math,pathlib,re,statistics
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'docs/mechanism';QS=('50','99','99.9','99.99','99.999');METHODS=('M0','M1','M2','M3core','M3total','constant')
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,separators=(',',':'))+'\n')
def check(v,m):
 if not v:raise ValueError(m)
def rank(bins,q):
 n=sum(c for _,c in bins)
 if not n:return None
 at=max(1,math.ceil(math.nextafter(q,-math.inf)*n/100.0));s=0
 for upper,c in bins:
  s+=c
  if s>=at:return upper
 raise ValueError('rank')
def errs(values):
 if not values:return dict(n=0)
 a=sorted(abs(x-y) for x,y in values);r=sorted(abs(x-y)/max(1,y) for x,y in values)
 return dict(n=len(a),medianAbsoluteNs=statistics.median(a),p90AbsoluteNs=a[math.ceil(.9*len(a))-1],medianRelativeError=statistics.median(r),p90RelativeError=r[math.ceil(.9*len(r))-1],medianAbsoluteLog2Error=statistics.median(abs(math.log2(max(1,x)/max(1,y))) for x,y in values))
def winner_scores(d):
 fs={r['id']:r for r in d['forks']};out={}
 def sign(x):return (x>0)-(x<0)
 for cohort in d['cohorts']:
  ps=[p for p in d['pairs'] if p['cohort']==cohort and not fs[p['c']]['predictionOutsideCalibration']];out[cohort]={}
  for q in QS[1:]:
   out[cohort][q]={}
   for method in (*METHODS,'alwaysCaffeine','alwaysChronicle','lowerTotalGc'):
    counts=collections.Counter(pairs=len(ps));points=[]
    for p in ps:
     c,h=fs[p['c']],fs[p['h']];actual=sign(h['latency']['response']['percentilesNs'][q]-c['latency']['response']['percentilesNs'][q])
     expected=1 if method=='alwaysCaffeine' else -1 if method=='alwaysChronicle' else sign(h['gc']['pauseOverlapMs']-c['gc']['pauseOverlapMs']) if method=='lowerTotalGc' else sign(h['predictionNs'][method][q]-c['predictionNs'][method][q])
     counts['abstentions' if expected==0 and actual!=0 else 'correct' if expected==actual else 'wrong']+=1;points.append(dict(pair=p['id'],actual=actual,predicted=expected))
    out[cohort][q][method]=dict(counts,points=points)
 return out

# Closed, completed scope: new/partial experiments need a separately versioned package.
COHORTS = ('headroom-confirm','headroom-screen','hotset-repeat','hotset-screen',
           'logging','payload','priming','qualification','transition')
CHANNELS = {'service','read-service','update-service','gap','response'}
THRESHOLDS = {100000,1000000,10000000}

def validate_coverage(d):
    """Validate the declared experiment independently of present histogram rows."""
    check(d.get('version') == 'tailcache-mechanism-portable-v1', 'Package version')
    check(set(d.get('cohorts', {})) == set(COHORTS), 'Complete cohort coverage')
    check(d.get('scope', {}).get('collectionComplete') is True and
          d['scope'].get('researchForks') == 64 and len(d.get('forks', [])) == 64,
          'Complete research scope')
    check(all(d['scope'].get(k)==v for k,v in dict(maxResearchJvms=64,functionalJvms=3,qualificationControls=2,mainControls=4).items()),'Scope accounting')
    check(len(d.get('pairs', [])) == 32, 'Complete pair coverage')
    check(set(d.get('decisions', {})) == {'logging-choice','priming-choice','hotset-worth','headroom-worth'}, 'Decision coverage')
    check(d['decisions']['hotset-worth']['expand'] and d['decisions']['headroom-worth']['expand'], 'Declared expansion coverage')
    ids = [r['id'] for r in d['forks']]
    check(len(set(ids)) == len(ids), 'Fork IDs')
    fs = {r['id']: r for r in d['forks']}
    for cohort, meta in d['cohorts'].items():
        rows = [r for r in d['forks'] if r['cohort'] == cohort]
        specs = meta['protocol']['design']['schedule']
        role='development' if cohort in ('logging','priming') else 'qualification' if cohort=='qualification' else 'prospective transport / mechanism test'
        check(meta['role']==role,'Evidence role contract')
        expected = 0 if cohort == 'qualification' else 8
        check(len(specs) == len(rows) == expected, 'Cohort schedule coverage')
        by_label = {r['label']: r for r in rows}
        check(set(by_label) == {s['label'] for s in specs}, 'Scheduled slot coverage')
        check(meta['audit']['passed'] and meta['audit']['newWorkloadJvms'] == expected, 'Raw audit coverage')
        check((meta['score'] is None) == (cohort == 'qualification'), 'Model score coverage')
        for spec in specs:
            r = by_label[spec['label']]
            check(r['id'] == cohort+'/'+r['label'] and all(r.get(k) == v for k,v in spec.items()), 'Frozen slot contract')
        if meta['score']:
            check(meta['score']['researchForks'] == expected and
                  meta['score']['warningBearing'] == sum(bool(r['warnings']) for r in rows) and
                  meta['score']['outsideCalibrationForks'] == sum(r['payload'] != 4096 for r in rows), 'Score population coverage')
    controls = d.get('controls', [])
    check(collections.Counter(c['cohort'] for c in controls) == {'logging':4,'qualification':2}, 'Control coverage')
    check(len({(c['cohort'],c['result']['label']) for c in controls}) == 6, 'Unique controls')
    for r in d['forks']:
        check(set(r['distributions']) == set(r['latency']) == set(r['stallRates']) == CHANNELS, 'Histogram channel coverage')
        check(r['status'] == 'OK' and r['latencyVerified'] and r['logComplete'], 'Outcome integrity')
        phases=['PRIME'+str(i) for i in range(r['primeCalls'])]+['WARMUP','CONDITIONING','MEASUREMENT']
        check([w['phase'] for w in r['windows']]==phases,'Phase coverage')
        for phase in r['windows']:
            duration=1000 if phase['phase'].startswith('PRIME') else r['warmupMs']-1000*r['primeCalls'] if phase['phase']=='WARMUP' else r['conditioningMs'] if phase['phase']=='CONDITIONING' else r['measureMs']
            check(int(phase['operations'])==int(phase['scheduled'])==duration*r['qps']//1000,'Phase request conservation')
            check(int(phase['offeredEndNs'])-int(phase['startNs'])==duration*1000000 and int(phase['endNs'])>int(phase['startNs']),'Phase timing contract')
        windows = [w for w in r['windows'] if w['phase'] == 'MEASUREMENT']
        check(len(windows) == 1, 'Measurement window coverage')
        w = windows[0]; n = int(w['operations']); writes = int(w['writes'])
        check(n == int(w['scheduled']) == r['qps']*r['measureMs']//1000 and 0 <= writes <= n, 'Request conservation')
        check(r['measurement']['writes'] == writes, 'Update conservation')
        wanted = dict(service=n, gap=n, response=n, **{'read-service':n-writes,'update-service':writes})
        for ch in CHANNELS:
            check(r['latency'][ch]['count'] == wanted[ch], 'Channel request conservation')
            check(set(r['latency'][ch]['percentilesNs']) == set(QS), 'Percentile coverage')
            rates = r['stallRates'][ch]
            check(len(rates) == 3 and {x['thresholdNs'] for x in rates} == THRESHOLDS, 'Threshold coverage')
        check(r['predictionOutsideCalibration'] == (r['payload'] != 4096), 'Calibration contract')
        check(set(r['predictionNs']) == (set(METHODS) if r['payload'] == 4096 else set()), 'Model prediction coverage')
        for values in r['predictionNs'].values():
            check(set(values) == set(QS[1:]) and all(isinstance(x,(int,float)) and math.isfinite(x) and x>=0 for x in values.values()), 'Model endpoint coverage')
    pair_ids = [p['id'] for p in d['pairs']]
    check(len(set(pair_ids)) == 32, 'Unique pair coverage')
    used = [p[k] for p in d['pairs'] for k in ('c','h')]
    check(collections.Counter(used) == collections.Counter(ids), 'Exactly-once pair membership')
    for p in d['pairs']:
        c,h = fs[p['c']],fs[p['h']]
        check(c['cohort'] == h['cohort'] == p['cohort'], 'Pair cohort contract')
        check(p['valid'] and p['labels'] == {'CAFFEINE':c['label'],'CHRONICLE_IN_MEMORY':h['label']}, 'Pair identity contract')
        check(p['warnings'] == {'CAFFEINE':c['warnings'],'CHRONICLE_IN_MEMORY':h['warnings']}, 'Pair warning coverage')
        check(set(p['ratios']) == CHANNELS, 'Ratio channel coverage')
        for ch in CHANNELS:
            wanted = {q for q in QS if c['latency'][ch]['percentilesNs'][q] not in (None,0)}
            check(set(p['ratios'][ch]) == wanted, 'Ratio endpoint coverage')
    check('winnerScores' in d and set(d['winnerScores']) == set(COHORTS), 'Winner score coverage')

def require_archive_coverage():
    """Fail before any output when this completed scope is absent/partial."""
    for cohort in COHORTS:
        base = ROOT/'evidence-archives'/('mechanism-'+cohort+'-20261118-001')
        required = ['study.json','state.json','protocol.json','raw-audit.json','source.tar.gz']
        if cohort != 'qualification': required += ['predictions-v1.json','score-v1.json']
        check(all((base/name).is_file() for name in required), 'Missing completed raw cohort: '+cohort)
        check(load(base/'state.json')['complete'] and load(base/'study.json')['collectionComplete'], 'Incomplete raw cohort: '+cohort)

def save_frozen(path, value):
    """Never replace a frozen output with a different or partially written value."""
    import os,tempfile
    raw = (json.dumps(value,separators=(',',':'))+'\n').encode()
    if path.exists():
        check(path.read_bytes() == raw, 'Refuse changed frozen output: '+str(path))
        return
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as stream:
        temp = pathlib.Path(stream.name)
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    try:
        try:os.link(temp,path)
        except FileExistsError:check(path.read_bytes()==raw,'Concurrent frozen output changed')
    finally:temp.unlink()

def package():
 require_archive_coverage()
 OUT.mkdir(exist_ok=True);forks=[];pairs=[];cohorts={};controls=[]
 for base in sorted((ROOT/'evidence-archives').glob('mechanism-*-20261118-001')):
  if not (base/'study.json').exists() or not (base/'raw-audit.json').exists():continue
  study=load(base/'study.json')
  if study['observations'] and not (base/'score-v1.json').exists():continue
  audit=load(base/'raw-audit.json');check(audit['passed'] and audit['studySha256']==sha(base/'study.json'),'Audit binding')
  cohort=base.name.removeprefix('mechanism-').removesuffix('-20261118-001');preds={r['label']:r for r in load(base/'predictions-v1.json')['observations']} if (base/'predictions-v1.json').exists() else {}
  cohorts[cohort]=dict(attempt=base.name,role='development' if cohort in ('logging','priming') else 'qualification' if cohort=='qualification' else 'prospective transport / mechanism test',inputs={p.name:sha(p) for p in [base/'study.json',base/'protocol.json',base/'raw-audit.json',base/'source.tar.gz']},audit=audit,protocol=load(base/'protocol.json'),score=load(base/'score-v1.json') if (base/'score-v1.json').exists() else None)
  for path in sorted((base/'controls').glob('*/service-result.json')):controls.append(dict(cohort=cohort,result=load(path)))
  for row in study['observations']:
   d=base/'slots'/row['label'];record=dict(row);record['id']=cohort+'/'+row['label'];record['cohort']=cohort;record['distributions']={};record['predictionNs']=preds.get(row['label'],{}).get('predictions',{});record['measuredPauses']=load(d/'measured-gc.json')['pauses'];record['predictionOutsideCalibration']=row['payload']!=4096
   record['gcFailureMessages']=[p['kind'] for p in record['measuredPauses'] if p.get('evacuationFailure') or 'pause full' in p['kind'].lower()]
   record['safepoints']=[]
   for line in (d/'gc-through-measurement.log').read_text().splitlines():
    if '[safepoint' not in line:continue
    stamp=re.search(r'\[([0-9]+)ns\]',line);fields={k:int(v) for k,v in re.findall(r'(Reaching safepoint|Cleanup|At safepoint|Leaving safepoint|Total): ([0-9]+) ns',line)}
    if stamp and 'Total' in fields:record['safepoints'].append(dict(endNs=int(stamp[1]),**fields))
   for channel in row['latency']:
    with (d/'worker'/(channel+'-bins.csv')).open() as stream:record['distributions'][channel]=[[int(b['upperEquivalentNs']),int(b['count'])] for b in csv.DictReader(stream)]
   record['stallRates']={}
   for channel,bins in record['distributions'].items():
    n=sum(c for _,c in bins);record['stallRates'][channel]=[]
    for threshold in (100000,1000000,10000000):
     lower=sum(c for u,c in bins if u-(1<<max(0,u.bit_length()-11))+1>threshold);upper=sum(c for u,c in bins if u>threshold)
     record['stallRates'][channel].append(dict(thresholdNs=threshold,operations=n,countLower=lower,countUpper=upper,probabilityLower=lower/n if n else None,probabilityUpper=upper/n if n else None))
   forks.append(record)
  for p in study['pairs']:
   p=dict(p);p['cohort']=cohort;p['id']=cohort+'/'+p['labels']['CAFFEINE'];p['c']=cohort+'/'+p['labels']['CAFFEINE'];p['h']=cohort+'/'+p['labels']['CHRONICLE_IN_MEMORY'];pairs.append(p)
 decisions={p.stem:load(p) for p in sorted((ROOT/'evidence-archives/mechanism-sequence-20261118-001').glob('*.json'))}
 d=dict(version='tailcache-mechanism-portable-v1',forks=forks,pairs=pairs,cohorts=cohorts,controls=controls,decisions=decisions,scope=dict(plan='docs/TAILCACHE_MECHANISM_PLAN.md',maxResearchJvms=64,researchForks=len(forks),collectionComplete=load(ROOT/'docs/TAILCACHE_MECHANISM_STATUS.json').get('collectionComplete',False),functionalJvms=3,qualificationControls=2,mainControls=4),model=load(OUT/'model-v1.json'),frozenModelFiles={str(p.relative_to(ROOT)):dict(sha256=sha(p),text=p.read_text()) for p in [ROOT/'docs/predictor/model-v1.json',ROOT/'docs/predictor/drain-candidate-v1.json',ROOT/'docs/predictor/numeric-baseline-v1.json',ROOT/'docs/predictor/drain_candidate.py.txt',ROOT/'scripts/tailcache12_pause_model.py']},limits=['One host; G1; paced ordinary get; no pooled quantiles.','Logging and priming select settings and are development cohorts.','Repeat hotset seeds are repeatability, not fresh validation.','Models condition on observed pauses; new costs were never fitted.','256B has no old-cost numerical calibration.','Warnings/evacuation failures remain intrinsic evidence; completion does not imply steady-state qualification.'])
 d['winnerScores']=winner_scores(d)
 verify(d);save_frozen(OUT/'mechanism-data-20261118.json',d);save_frozen(OUT/'winner-scores.json',d['winnerScores'])
 if not (OUT/'portable-verification.json').exists():save_frozen(OUT/'portable-verification.json',verify(d))
 return d

def verify(d):
 validate_coverage(d)
 check(d['winnerScores']==winner_scores(d),'Winner summaries')
 fs={r['id']:r for r in d['forks']};check(len(fs)==len(d['forks']),'Fork IDs');counts=collections.Counter();scores={}
 for r in fs.values():
  for ch,bins in r['distributions'].items():
   check(all(c>0 for _,c in bins) and [x for x,_ in bins]==sorted(set(x for x,_ in bins)),'Bin order/count');check(sum(c for _,c in bins)==r['latency'][ch]['count'],'Count')
   for rate in r['stallRates'][ch]:
    t=rate['thresholdNs'];n=sum(c for _,c in bins);low=sum(c for u,c in bins if u-2**max(0,math.frexp(u)[1]-11)+1>t);high=sum(c for u,c in bins if u>t)
    check((low,high,n)==(rate['countLower'],rate['countUpper'],rate['operations']),'Strict rate bounds');check(rate['probabilityLower']==(low/n if n else None) and rate['probabilityUpper']==(high/n if n else None),'Rate probability');counts['thresholds']+=1
   for q in QS:
    actual=rank(bins,float(q));expected=r['latency'][ch]['percentilesNs'][q]
    check(actual==expected if actual is not None else expected in (0,None),'Rank');counts['quantiles']+=actual is not None
  union=collections.Counter(dict(r['distributions']['read-service']));union.update(dict(r['distributions']['update-service']));check(dict(union)==dict(r['distributions']['service']),'Union');counts['unions']+=1
 for p in d['pairs']:
  c,h=fs[p['c']],fs[p['h']];check(c['backend']=='CAFFEINE' and h['backend']=='CHRONICLE_IN_MEMORY','Arms')
  for k in ('seed','payload','writeBps','hotset','heapMiB','logging','primeCalls','repeat','measureMs'):check(c[k]==h[k],'Pair contract')
  for ch,qs in p['ratios'].items():
   for q,ratio in qs.items():check(math.isclose(h['latency'][ch]['percentilesNs'][q]/c['latency'][ch]['percentilesNs'][q],ratio,rel_tol=1e-12),'Ratio');counts['ratios']+=1
 for cohort in d['cohorts']:
  rr=[r for r in fs.values() if r['cohort']==cohort and not r['predictionOutsideCalibration']]
  scores[cohort]={s:{m:{q:errs([(r['predictionNs'][m][q],r['latency']['response']['percentilesNs'][q]) for r in rr if s=='all' or r['backend']==s]) for q in QS[1:]} for m in METHODS} for s in ('all','CAFFEINE','CHRONICLE_IN_MEMORY')}
  archived=d['cohorts'][cohort]['score']
  if archived:
   for s in scores[cohort]:
    for m in METHODS:
     for q in QS[1:]:
      for k,v in scores[cohort][s][m][q].items():check(math.isclose(v,archived['numerical'][s][m][q][k],rel_tol=1e-12,abs_tol=1e-6),'Numerical summary');counts['modelSummaries']+=1
 counts.update(forks=len(fs),pairs=len(d['pairs']),controls=len(d['controls']))
 return dict(passed=True,counts=dict(counts),limits='Independent portable arithmetic checks; raw decoder/source audits are separately retained. Not independent host replication.')

def reports(d):
 verification=verify(d)
 fs={r['id']:r for r in d['forks']};lines=['# Mechanism experiments — 18 November 2026','','Every completed comparison is retained separately. Values below are scheduled-response latency, not saturated service. Development choices, paired treatment screens, repeats and fresh confirmation have different evidence roles. Warnings and collector failures are retained.','','## Frozen decisions','']
 for k,v in d['decisions'].items():lines+=['- **'+k+'**: `'+json.dumps(v,separators=(',',':'))+'`']
 lines+=['','## Every paired data point','','| Cohort | Seed / repeat | Writes % | Payload B | Update keys | Heap MiB | Logging / priming | p99.9 Caffeine µs | Chronicle µs | Ch/C p99.9 | p99.99 | p99.999 | Conclusion |','| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |']
 table=[]
 for p in d['pairs']:
  c,h=fs[p['c']],fs[p['h']];rat=p['ratios']['response'];outcome='Chronicle lower' if rat['99.9']<1 else 'Caffeine lower' if rat['99.9']>1 else 'Equal';warn=bool(c['warnings'] or h['warnings']);fail=bool(c['gcFailureMessages'] or h['gcFailureMessages'])
  lines.append(f"| {p['cohort']} | {c['seed']} / {c['repeat']} | {c['writeBps']/100:g} | {c['payload']} | {c['hotset']} | {c['heapMiB']} | {c['logging']} / {c['primeCalls']} | {c['latency']['response']['percentilesNs']['99.9']/1000:.3f} | {h['latency']['response']['percentilesNs']['99.9']/1000:.3f} | {rat['99.9']:.4f} | {rat['99.99']:.4f} | {rat['99.999']:.4f} | {outcome}{'; warnings' if warn else ''}{'; GC failure' if fail else ''} |")
  for ch,qq in p['ratios'].items():
   for q,r in qq.items():table.append([p['cohort'],c['seed'],c['repeat'],c['writeBps'],c['payload'],c['hotset'],c['heapMiB'],c['logging'],c['primeCalls'],c['measureMs'],ch,q,c['latency'][ch]['percentilesNs'][q],h['latency'][ch]['percentilesNs'][q],r,warn,fail])
 lines+=['','## Conditional response model / baseline comparison','','All rows retain warnings and near-budget outcomes. Logging/priming are development; other cohorts are separately identified transport tests. The simple lower-total-GC rule is scored even when a fixed-cost model misses. 256B is outside numerical calibration.','','| Cohort | Model | p99.9 correct / pairs | Abstentions | Median absolute error µs | Median relative error % |','| --- | --- | ---: | ---: | ---: | ---: |']
 for cohort in d['cohorts']:
  if not d['cohorts'][cohort]['score']:continue
  for method in (*METHODS,'alwaysCaffeine','alwaysChronicle','lowerTotalGc'):
   win=d['winnerScores'][cohort]['99.9'][method];e=d['cohorts'][cohort]['score']['numerical']['all'].get(method,{}).get('99.9',{})
   lines.append(f"| {cohort} | {method} | {win.get('correct',0)}/{win['pairs']} | {win.get('abstentions',0)} | {e['medianAbsoluteNs']/1000:.3f} | {e['medianRelativeError']*100:.2f} |" if e else f"| {cohort} | {method} | {win.get('correct',0)}/{win['pairs']} | {win.get('abstentions',0)} | — | — |")
 lines+=['','## Limits','']+['- '+s for s in d['limits']]+['','Portable data: [mechanism-data-20261118.json](mechanism-data-20261118.json). Arithmetic verification: [portable-verification.json](portable-verification.json). Frozen protocol: [plan](../TAILCACHE_MECHANISM_PLAN.md). Research interpretation must keep negative and mixed effects.']
 (OUT/'RESULTS.md').write_text('\n'.join(lines)+'\n')
 with (OUT/'point-conclusions.csv').open('w') as stream:
  w=csv.writer(stream);w.writerow(['cohort','seed','repeat','writeBps','payloadBytes','updateKeys','heapMiB','logging','priming','measurementMs','channel','percentile','caffeineNs','chronicleNs','ChOverC','warnings','collectorFailure']);w.writerows(table)
 rates=[]
 for r in d['forks']:
  for ch,bins in r['distributions'].items():
   n=sum(c for _,c in bins)
   for t in (100000,1000000,10000000):
    lower=upper=0
    for hi,c in bins:
     low=hi-(1<<max(0,hi.bit_length()-11))+1
     if low>t:lower+=c
     if hi>t:upper+=c
    rates.append([r['id'],ch,t,n,lower,upper,lower/n if n else None,upper/n if n else None])
 with (OUT/'stall-rates.csv').open('w') as stream:
  w=csv.writer(stream);w.writerow(['fork','channel','thresholdNs','count','strictExceedanceLower','strictExceedanceUpper','rateLower','rateUpper']);w.writerows(rates)
 print(json.dumps(verification))

def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['package','verify','report']);a=p.parse_args()
 if a.command=='package':reports(package())
 else:
  d=load(OUT/'mechanism-data-20261118.json')
  if a.command=='verify':print(json.dumps(verify(d)))
  else:reports(d)
if __name__=='__main__':main()
