#!/usr/bin/env python3
"""Independent portable count/rank/rate/contrast reconciliation; no collector imports."""
import argparse
import base64
import collections
import gzip
import hashlib
import json
import math
import pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
EXPECTED={'screen','replication','paced','observer','policy','trace','largePilot','geometry'}
Q=('50','99','99.9','99.99','99.999')


def require(test,message):
    if not test:raise ValueError(message)


def same(a,b,message):
    require(math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9),message)


def decode(data):
    section=data['curves']
    require(section['encoding']=='gzip-base64-delta-varint-v1','Curve encoding')
    compressed=base64.b64decode(section['data'],validate=True)
    require(hashlib.sha256(compressed).hexdigest()==section['compressedSha256'],'Compressed curve identity')
    raw=gzip.decompress(compressed)
    require(hashlib.sha256(raw).hexdigest()==section['sha256'],'Decoded curve identity')
    curves={};coverage=[]
    for identity,channels in section['directory'].items():
        curves[identity]={}
        for channel,info in channels.items():
            start=info['offset'];end=start+info['bytes'];position=start;upper=0;bins=[]
            require(0<=start<end<=len(raw) and info['bins']>0,'Curve byte range')
            def integer():
                nonlocal position
                value=0;shift=0
                while position<end and shift<=63:
                    byte=raw[position];position+=1;value|=(byte&127)<<shift
                    if byte<128:return value
                    shift+=7
                raise ValueError('Truncated/oversized curve integer')
            for index in range(info['bins']):
                delta=integer();count=integer()
                require((index==0 or delta>0) and count>0,'Curve order/count')
                upper+=delta;bins.append((upper,count))
            require(position==end and sum(n for _,n in bins)==info['count'],'Curve byte/count conservation')
            curves[identity][channel]=bins;coverage.append((start,end))
    coverage.sort()
    require(coverage and coverage[0][0]==0 and coverage[-1][1]==len(raw) and
            all(a[1]==b[0] for a,b in zip(coverage,coverage[1:])),'Curve coverage/overlap')
    return curves


def quantile(bins,percentile):
    total=sum(n for _,n in bins)
    target=max(1,math.ceil(math.nextafter(float(percentile),-math.inf)*total/100))
    count=0
    for value,n in bins:
        count+=n
        if count>=target:return value
    raise ValueError('Missing rank')


def pair_key(pair):
    return tuple(pair[k] for k in ('cohort','stage','payload','liveMiB','seed','block','referenceBackend'))


def verify(data,final=True):
    require(data['schema']=='tailcache-service-followup-v1','Schema')
    require(data['forks'] and data['pairs'] and data['points'],'Empty research package')
    if final:
        require(set(data['cohortInputs'])==EXPECTED and data['planCompletion']['allDeclaredCohortsPresent'],
                'Missing declared cohort')
    curves=decode(data);forks={r['id']:r for r in data['forks']};counts=collections.Counter()
    require(len(forks)==len(data['forks']),'Duplicate fork identity')
    require(sum(v['workloadJvms'] for v in data['cohortInputs'].values())==len(forks),'Cohort fork accounting')
    expected_curves=set()
    for identity,row in forks.items():
        inputs=data['cohortInputs'][row['cohort']];audit=inputs['audit']
        require(audit['passed'] and audit['studySha256']==inputs['studySha256'] and
                audit['protocolSha256']==inputs['protocolSha256'],'Retained raw-audit input binding')
        if not row['latencyVerified'] or row['status']!='OK':
            require(identity not in curves,'Failure represented as latency');counts['failureOutcomes']+=1;continue
        expected_curves.add(identity)
        expected={c for c,v in row['latency'].items() if v['count']>0}
        require(set(curves[identity])==expected,'Missing/nonexistent curve channel')
        measured=[w for w in row['windows'] if w['phase']=='MEASUREMENT']
        n=sum(int(w['operations']) for w in measured);writes=sum(int(w['writes']) for w in measured)
        require(n==row['measurement']['operations'] and writes==row['measurement']['writes'],'Window/operation accounting')
        if row['cohort']=='observer':
            require(len(measured)==8 and inputs['measurementPlan']['measurementIterations']==8,'Actual JMH iteration plan')
            require(0<row['latency']['service']['count']<=n,'JMH samples are not all operations')
            require(row['latency']['service']['count']==row['measurement']['samples'],'JMH sample accounting')
        else:
            require(len(measured)==1,'Contiguous measurement window')
            require(row['latency']['service']['count']==row['latency']['gap']['count']==n,'All-operation channel counts')
            require(row['latency']['read-service']['count']==n-writes and
                    row['latency']['update-service']['count']==writes,'Conditional operation counts')
            union=collections.Counter(dict(curves[identity]['read-service']))
            union.update(dict(curves[identity].get('update-service',[])))
            require(dict(union)==dict(curves[identity]['service']),'Per-bin read/update conservation')
            counts['perBinUnions']+=1
            for w in row['windows']:
                require(not int(w['scheduled']) or int(w['scheduled'])==int(w['operations']),'All-phase scheduled accounting')
            if row.get('qps',0):require(row['latency']['response']['count']==n,'Complete response distribution')
        for channel,bins in curves[identity].items():
            require(sum(v for _,v in bins)==row['latency'][channel]['count'],'Portable channel support')
            for p in Q:
                same(quantile(bins,p),row['latency'][channel]['percentilesNs'][p],'Portable raw rank')
                counts['quantileEndpoints']+=1
            counts['distributions']+=1
        m=row.get('mechanism')
        if m:
            require(m['largeGcServiceOverlapNs']+m['largeGcBetweenCallOverlapNs']+m['largeGcUnmappedNs']==m['largeGcOverlapNs'],
                    'GC event partition')
            require(m['largeGcUnmappedNs']==0 and 0<=m['largeGcAffectedServiceCalls']<=n,'Complete GC event reconciliation')
            same(m['largeGcAffectedCallFraction'],m['largeGcAffectedServiceCalls']/n,'GC operation denominator')
            for rate in m['serviceExceedance']:
                threshold=rate['thresholdNs'];bins=curves[identity]['service']
                lower=sum(v for u,v in bins if u-(1<<max(0,u.bit_length()-11))+1>threshold)
                upper=sum(v for u,v in bins if u>threshold)
                require((lower,upper,n)==(rate['countLower'],rate['countUpper'],rate['operations']),'HDR threshold bounds')
                same(lower/n,rate['probabilityLower'],'Lower tail probability');same(upper/n,rate['probabilityUpper'],'Upper tail probability')
                counts['thresholdChecks']+=1
            mixed=m['mixtureAboveP999'];boundary=mixed['boundaryUpperEquivalentNs']
            for channel in ('service','read-service','update-service'):
                require(sum(v for u,v in curves[identity].get(channel,[]) if u>boundary)==mixed['counts'][channel],'Tail mixture component')
            counts['mixtureChecks']+=1
        counts['forks']+=1
    require(set(curves)==expected_curves,'Unexpected/missing fork curves')
    pairs={pair_key(p):p for p in data['pairs']};require(len(pairs)==len(data['pairs']),'Duplicate paired contrast')
    for pair in pairs.values():
        c,h=[forks[pair[k]] for k in ('c','h')]
        require(c['cohort']==h['cohort']==pair['cohort'] and c['backend']==pair['referenceBackend'] and
                h['backend']=='CHRONICLE_IN_MEMORY','Pair contract identity')
        for name in ('stage','payload','liveMiB','seed','block'):
            require(c[name]==h[name]==pair[name],'Paired workload differs')
        require(pair['warningFree']==(not(c['warnings'] or h['warnings'])),'Warning coverage')
        if pair['valid']:
            require(c['status']==h['status']=='OK' and c['latencyVerified'] and h['latencyVerified'],'Invalid valid pair')
            require(c['trace']['traceSha256']==h['trace']['traceSha256'],'Paired logical trace differs')
            expected=set(curves[c['id']])&set(curves[h['id']])
            require(set(pair['ratios'])==expected,'Missing ratio channel')
            for channel,values in pair['ratios'].items():
                require(set(values)==set(Q),'Missing ratio endpoint')
                for p,value in values.items():
                    same(value,h['latency'][channel]['percentilesNs'][p]/c['latency'][channel]['percentilesNs'][p],'Paired ratio')
                    counts['pairedRatios']+=1
    covered=set()
    require(len({p['id'] for p in data['points']})==len(data['points']),'Duplicate point identity')
    for point in data['points']:
        ps=point['pairs'];require(ps,'Empty point comparison')
        for pair in ps:
            require(all(point[k]==pair[k] for k in ('cohort','stage','payload','liveMiB','seed','referenceBackend')),
                    'Point label differs from paired evidence')
            key=pair_key(pair);require(key in pairs and pair==pairs[key] and key not in covered,'Point pair coverage')
            covered.add(key)
        require(point['completePairs']==sum(p['valid'] for p in ps) and
                point['warningFreePairs']==sum(p['valid'] and p['warningFree'] for p in ps),'Point quality coverage')
        expected=set.intersection(*(set(p['ratios']) for p in ps))
        require(set(point['conclusions'])==expected,'Missing point channel')
        for channel,values in point['conclusions'].items():
            require(set(values)==set(Q),'Missing point endpoint')
            for p,con in values.items():
                ratios=[pair['ratios'][channel][p] for pair in ps]
                outcome='Chronicle lower' if all(v<1 for v in ratios) else 'Caffeine lower' if all(v>1 for v in ratios) else 'Equal' if all(v==1 for v in ratios) else 'Mixed'
                require(con['ratios']==ratios and con['range']==[min(ratios),max(ratios)] and con['direction']==outcome,
                        'Point conclusion changed')
                counts['pointConclusions']+=1
    require(covered==set(pairs),'Missing point/pair comparisons')
    return dict(passed=True,counts=dict(counts),cohorts=len(data['cohortInputs']),pairContrasts=len(pairs),pointGroups=len(data['points']),
                limits='Independent portable arithmetic/representation reconciliation; raw audits remain separate, not human peer review or proof of design validity.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('package',type=pathlib.Path);parser.add_argument('--out',type=pathlib.Path)
    args=parser.parse_args();result=verify(json.loads(args.package.read_text()))
    result['packageSha256']=hashlib.sha256(args.package.read_bytes()).hexdigest()
    if args.out:args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
