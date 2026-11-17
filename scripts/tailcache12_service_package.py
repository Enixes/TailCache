#!/usr/bin/env python3
"""Build separately identified per-point summaries from audited follow-up cohorts."""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import math
import pathlib
import base64

ROOT=pathlib.Path(__file__).resolve().parents[1]
COHORTS={
 'screen':'service-followup-20261117-001',
 'replication':'service-rq-extension-20261117-001',
 'paced':'service-paced-20261117-001',
 'observer':'service-observer-20261117-001',
 'policy':'service-policy-20261117-001',
 'trace':'service-trace-20261117-001',
 'largePilot':'service-large-payload-pilot-20261117-001',
 'geometry':'service-geometry-20261117-001',
}
Q=('50','99','99.9','99.99','99.999')


def load(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(test,message):
 if not test:raise ValueError(message)
def csvrows(path):
 with path.open() as stream:return list(csv.DictReader(stream))
def rank(bins,p):
 target=max(1,math.ceil(math.nextafter(float(p),-math.inf)*sum(n for _,n in bins)/100));cumulative=0
 for value,count in bins:
  cumulative+=count
  if cumulative>=target:return value
 raise ValueError('Missing histogram rank')
def direction(ratios):
 return 'Chronicle lower' if all(v<1 for v in ratios) else 'Caffeine lower' if all(v>1 for v in ratios) else 'Equal' if all(v==1 for v in ratios) else 'Mixed'


def build(names):
 require(len(names)==len(set(names)) and bool(names),'Nonempty unique cohort selection required')
 forks=[];pairs=[];inputs={};distributions={}
 for name in names:
  attempt=COHORTS[name];base=ROOT/'evidence-archives'/attempt
  study=load(base/'study.json');protocol=load(base/'protocol.json');audit=load(base/'independent-audit-001/audit.json')
  require(audit['passed'] and audit['studySha256']==sha(base/'study.json'),'Unaudited study '+name)
  require(audit['protocolSha256']==sha(base/'protocol.json'),'Protocol identity '+name)
  require(load(base/'state.json').get('collectionComplete') or load(base/'state.json').get('complete'),'Incomplete cohort')
  inputs[name]=dict(attempt=attempt,studySha256=sha(base/'study.json'),protocolSha256=sha(base/'protocol.json'),
    sourceArchiveSha256=sha(base/'source.tar.gz'),sourceSha256=protocol['sourceSha256'],
    runtimeFingerprint=hashlib.sha256(json.dumps(protocol['runtimeSha256'],sort_keys=True).encode()).hexdigest(),
    auditSha256=sha(base/'independent-audit-001/audit.json'),audit=audit,
    primaryChannel='response' if name in ('trace','geometry') else 'service',
    genericControllerDurationsMs=dict(warmup=protocol['warmupMs'],conditioning=protocol['conditioningMs'],measurement=protocol['measureMs']),
    measurementPlan=(dict(regime='JMH SampleTime',warmupIterations=14,measurementIterations=8,iterationMs=1000,
        note='Generic 30-second base-controller measurement field is unused by JMH; actual nominal measurement is eight seconds.')
        if name=='observer' else dict(regime='contiguous',warmupMs=protocol['warmupMs'],conditioningMs=protocol['conditioningMs'],measureMs=protocol['measureMs'])))
  mechanism=None if name=='observer' else load(base/'mechanism-audit-001/report.json')
  if mechanism is not None:require(mechanism['passed'] and mechanism['studySha256']==sha(base/'study.json'),'Mechanism audit identity')
  mechanism_by={r['label']:r for r in mechanism['observations']} if mechanism else {}
  if mechanism:inputs[name]['mechanismAuditSha256']=sha(base/'mechanism-audit-001/report.json')
  inputs[name]['workloadJvms']=len(study['observations'])
  grouped=collections.defaultdict(dict)
  for row in study['observations']:
   identity=attempt+'/'+row['label'];directory=base/'slots'/row['label']
   record={k:row.get(k) for k in ('label','stage','backend','payload','liveMiB','seed','block','regime','qps','status','warnings','measurement','gc','processMemory','trace','latency')}
   record.update(id=identity,cohort=name,sourceAttempt=attempt,latencyVerified=bool(row.get('latencyVerified')),
                 curveKind='JMH reported samples' if name=='observer' else 'HDR upper-equivalent bins')
   record['windows']=row.get('windows',[])
   if row['label'] in mechanism_by:
    m=mechanism_by[row['label']]
    record['mechanism']={k:m[k] for k in ('largeGcPauseCount','largeGcOverlapNs','largeGcServiceOverlapNs','largeGcBetweenCallOverlapNs','largeGcUnmappedNs','largeGcAffectedServiceCalls','largeGcAffectedCallFraction','churnLostDemandFraction','materializationFloorPassed','serviceExceedance','mixtureAboveP999')}
   forks.append(record)
   group=grouped[row['stage'],row['payload'],row['liveMiB'],row['seed'],row['block']]
   require(row['backend'] not in group,'Duplicate paired backend')
   group[row['backend']]=record
   if not record['latencyVerified'] or row['status']!='OK':continue
   distributions[identity]={}
   for channel,latency in row['latency'].items():
    if not latency['count']:continue
    p=directory/'sample-bins.csv' if name=='observer' else directory/'worker'/(channel+'-bins.csv')
    key='valueNs' if name=='observer' else 'upperEquivalentNs'
    bins=[(int(r[key]),int(r['count'])) for r in csvrows(p)]
    require(sum(n for _,n in bins)==latency['count'] and all(n>0 for _,n in bins),'Histogram support')
    require(all(a[0]<b[0] for a,b in zip(bins,bins[1:])),'Histogram order')
    for percentile in Q:require(rank(bins,percentile)==latency['percentilesNs'][percentile],'Portable quantile mismatch')
    distributions[identity][channel]=bins
  for key,arms in sorted(grouped.items()):
   references=['CAFFEINE','CAFFEINE_BOUNDED_DIRECT','CAFFEINE_UNBOUNDED'] if name=='policy' else ['CAFFEINE']
   for reference in references:
    require(reference in arms and 'CHRONICLE_IN_MEMORY' in arms,'Missing matched arm')
    c,h=arms[reference],arms['CHRONICLE_IN_MEMORY'];valid=all(r['status']=='OK' and r['latencyVerified'] for r in (c,h))
    pair=dict(cohort=name,stage=key[0],payload=key[1],liveMiB=key[2],seed=key[3],block=key[4],
      referenceBackend=reference,valid=valid,c=c['id'],h=h['id'],ratios={},
      warningFree=not(c['warnings'] or h['warnings']))
    if valid:
     require(c['trace']['traceSha256']==h['trace']['traceSha256'],'Matched trace identity')
     for channel in set(c['latency'])&set(h['latency']):
      if not(c['latency'][channel]['count'] and h['latency'][channel]['count']):continue
      pair['ratios'][channel]={p:h['latency'][channel]['percentilesNs'][p]/c['latency'][channel]['percentilesNs'][p] for p in Q}
    pairs.append(pair)
 points=[];grouped=collections.defaultdict(list)
 for pair in pairs:
  grouped[tuple(pair[k] for k in ('cohort','stage','payload','liveMiB','seed','referenceBackend'))].append(pair)
 for key,ps in sorted(grouped.items()):
  point={k:v for k,v in zip(('cohort','stage','payload','liveMiB','seed','referenceBackend'),key)}
  point.update(id='cell-'+str(len(points)+1),pairs=ps,completePairs=sum(p['valid'] for p in ps),
    warningFreePairs=sum(p['valid'] and p['warningFree'] for p in ps),conclusions={})
  channels=set.intersection(*(set(p['ratios']) for p in ps))
  for channel in sorted(channels):
   point['conclusions'][channel]={}
   for percentile in Q:
    ratios=[p['ratios'][channel][percentile] for p in ps]
    point['conclusions'][channel][percentile]=dict(direction=direction(ratios),ratios=ratios,range=[min(ratios),max(ratios)],
      limits='Observed paired ratios; descriptive range, not a confidence interval or significance test.')
  points.append(point)
 require(len({r['id'] for r in forks})==len(forks),'Duplicate fork identities')
 packed=bytearray();directory={}
 def put(value):
  while value>=128:packed.append((value&127)|128);value>>=7
  packed.append(value)
 for identity,channels in distributions.items():
  directory[identity]={}
  for channel,bins in channels.items():
   offset=len(packed);previous=0
   for upper,count in bins:put(upper-previous);put(count);previous=upper
   directory[identity][channel]=dict(offset=offset,bytes=len(packed)-offset,bins=len(bins),count=sum(n for _,n in bins))
 curve_text=bytes(packed)
 compressed=gzip.compress(curve_text,mtime=0)
 return dict(schema='tailcache-service-followup-v1',scope='Exploratory, separately identified cohorts; no pooled fork percentiles',
  cohortInputs=inputs,forks=forks,pairs=pairs,points=points,
  planCompletion=dict(allDeclaredCohortsPresent=set(names)==set(COHORTS),largerPayloadExpansion='Not triggered by frozen service-p99.9 rule; zero confirmation JVMs',
      originalTask12UnconditionalStatus='NO_GO; unchanged',publicationStatus='Agent-reviewed working draft; human approval and public artifact release pending'),
  curves=dict(encoding='gzip-base64-delta-varint-v1',directory=directory,sha256=hashlib.sha256(curve_text).hexdigest(),
              compressedSha256=hashlib.sha256(compressed).hexdigest(),data=base64.b64encode(compressed).decode()),
  limits=['JMH curves describe retained reported samples, not all completed operations or raw unquantized times.',
          'Trace lengths change coverage, lifetime and primitive-array geometry together.',
          'Policies and observers are different complete contracts; no causal heap-placement claim.',
          'Warnings and failures are retained; min–max ranges are not confidence intervals.'])


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cohorts',nargs='+',choices=COHORTS,default=list(COHORTS))
 parser.add_argument('--out',type=pathlib.Path,required=True);args=parser.parse_args();data=build(args.cohorts)
 args.out.parent.mkdir(parents=True,exist_ok=True)
 with args.out.open('x') as f:json.dump(data,f,separators=(',',':'));f.write('\n')
 md=args.out.with_suffix('.md')
 lines=['# Per-point follow-up conclusions','',
  'Ratios divide Chronicle by the explicitly named Caffeine configuration. Each listed ratio is a separate paired fork. No quantiles are pooled; ranges are descriptive. All warning-bearing outcomes remain included. This file summarizes only the named completed/audited cohorts, not an unconditional acceptance.','',
  '| Cohort / stage | Payload B | Ballast MiB | Seed | Caffeine reference | Pairs (warning-free) | Primary p99.9 Ch/C | Descriptive conclusion |',
  '| --- | ---: | ---: | ---: | --- | --- | --- | --- |']
 for p in data['points']:
  channel=data['cohortInputs'][p['cohort']]['primaryChannel'];con=p['conclusions'].get(channel,{}).get('99.9')
  ratios=', '.join(f'{v:.4f}' for v in con['ratios']) if con else 'Incomplete'
  lines.append(f"| {p['cohort']} / {p['stage']} | {p['payload']} | {p['liveMiB']} | {p['seed']} | {p['referenceBackend']} | {p['completePairs']}/{len(p['pairs'])} ({p['warningFreePairs']}) | {ratios} | {con['direction'] if con else 'Incomplete; do not rank'} |")
 with md.open('x') as f:f.write('\n'.join(lines)+'\n')
 print(json.dumps(dict(forks=len(data['forks']),pairs=len(data['pairs']),points=len(data['points']),bytes=args.out.stat().st_size)))


if __name__=='__main__':main()
