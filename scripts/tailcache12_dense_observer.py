"""Diagnostic common-observer controls and complete recorder conservation checks."""
import csv
from collections import Counter
import math

from tailcache12_analysis import histogram,quantile,validate_windows

VERSION='dense-observer-work-v1'


def validate_controls(args,inputs,selection,directory,diagnostic=False):
    flags=[a for a in args if a.startswith(('-Dtailcache12.denseObserver=',
                                          '-Dtailcache12.observerDiagnosticOnly='))]
    declared=bool(flags or inputs.get('DenseObserver') or inputs.get('ObserverDiagnosticOnly')
                  or selection and selection.get('denseObserverWork') or (directory/'dense-observer').exists())
    if not diagnostic:
        if declared:raise ValueError('Common-observer diagnostics cannot supply ordinary endpoints')
        return
    if (set(flags)!={'-Dtailcache12.denseObserver=true','-Dtailcache12.observerDiagnosticOnly=true'}
            or len(flags)!=2 or inputs.get('DenseObserver')!='true'
            or inputs.get('ObserverDiagnosticOnly')!='true' or not selection
            or not selection.get('denseObserverWork')):
        raise ValueError('Missing/mismatched common-observer diagnostic controls')


def replay(directory,inputs,sidecars,sample_counts):
    path=directory/'dense-observer'
    config=dict(line.split('=',1) for line in (path/'configuration.txt').read_text().splitlines())
    conditioning=inputs.get('Conditioning',0);warmups=inputs['Warmups'];measurements=inputs['Measurements']
    if config!=dict(version=VERSION,warmups=str(warmups),physicalMeasurements=str(conditioning+measurements),
                    conditioning=str(conditioning),histogramSignificantDigits='3',histogramMaxNs='60000000000'):
        raise ValueError('Dense observation configuration changed')
    with (path/'iterations.csv').open() as stream:rows=list(csv.DictReader(stream))
    expected=[(phase,i+1) for phase,n in (('WARMUP',warmups),('CONDITIONING',conditioning),('MEASUREMENT',measurements)) for i in range(n)]
    if [(r['phase'],int(r['iteration'])) for r in rows]!=expected or len(sidecars)!=len(rows):
        raise ValueError('Dense phase/count coverage differs from JMH')
    windows=[(int(r['startNs']),int(r['endNs'])) for r in rows];validate_windows(windows)
    allowed={'configuration.txt','iterations.csv'};merged=Counter();gaps=Counter();operations=0;elapsed=0
    for row,parent,(start,end) in zip(rows,sidecars,windows):
        count=int(row['operations'])
        if (count<=0 or parent['phase']!=row['phase'] or count>int(parent['operations'])
                or start<int(parent['envelopeStartNs']) or end>int(parent['envelopeEndNs'])):
            raise ValueError('Dense window/count escapes actual JMH envelope')
        if row['phase']=='WARMUP':continue
        if int(row['overflowCount'])!=0:raise ValueError('Dense recorder overflow')
        prefix=('conditioning/' if row['phase']=='CONDITIONING' else '')+'iteration-'+row['iteration']
        for channel in ('service','completion-gap'):
            bins=histogram(path/(prefix+'-'+channel+'-bins.csv'),count)
            exact_max=int(row['serviceMaxNs' if channel=='service' else 'completionGapMaxNs'])
            upper=bins[-1][0];width=1<<max(0,int(upper).bit_length()-11)
            if not upper-width+1<=exact_max<=upper:raise ValueError('Dense exact maximum differs from histogram')
            for threshold,suffix in ((1000000,'1ms'),(10000000,'10ms')):
                observed=int(row[('serviceAbove' if channel=='service' else 'gapAbove')+suffix])
                low=sum(n for v,n in bins if v-(1<<max(0,int(v).bit_length()-11))+1>=threshold)
                high=sum(n for v,n in bins if v>=threshold)
                if not low<=observed<=high:raise ValueError('Dense threshold count differs from histogram')
            for suffix in ('-bins.csv','.hdr'):allowed.add(prefix+'-'+channel+suffix)
            compressed=path/(prefix+'-'+channel+'.hdr')
            if not compressed.is_file() or not compressed.stat().st_size:raise ValueError('Missing dense compressed histogram')
            if row['phase']=='MEASUREMENT':
                target=merged if channel=='service' else gaps
                for value,n in bins:target[value]+=n
        allowed.add(prefix+'-stall-events.csv')
        with (path/(prefix+'-stall-events.csv')).open() as stream:events=list(csv.DictReader(stream))
        if len(events)>4096:raise ValueError('Dense stall-event capacity exceeded')
        if len(events)!=int(row['eventCount']):raise ValueError('Dense stall-event count mismatch')
        for e in events:
            a,b,previous,service,gap=(int(e[k]) for k in ('serviceStartNs','endNs','previousCompletionNs','serviceNs','completionGapNs'))
            if not start<=a<=b<=end or b-a!=service or b-previous!=gap or gap<service or max(service,gap)<1000000:
                raise ValueError('Invalid dense stall event')
        for field,column,threshold in (('serviceAbove1ms','serviceNs',1000000),('gapAbove1ms','completionGapNs',1000000),
                                       ('serviceAbove10ms','serviceNs',10000000),('gapAbove10ms','completionGapNs',10000000)):
            if sum(int(e[column])>=threshold for e in events)!=int(row[field]):
                raise ValueError('Incomplete dense stall-event threshold evidence')
        if row['phase']=='MEASUREMENT':operations+=count;elapsed+=end-start
    actual={p.relative_to(path).as_posix() for p in path.rglob('*') if p.is_file()}
    if actual!=allowed:raise ValueError('Missing/unexpected dense capture artifact')
    retained=sum(sample_counts)
    if len(sample_counts)!=measurements or retained>operations or abs(retained-operations/16)>operations/16*.01:
        raise ValueError('Dense fixed-sampling inclusion differs by more than1%')
    lower=sum((v-(1<<max(0,int(v).bit_length()-11))+1)*n for v,n in merged.items())
    if lower>elapsed:raise ValueError('Dense service intervals cannot fit the recorded window')
    if elapsed<=0 or not math.isfinite(operations/elapsed):raise ValueError('Invalid dense exposure')
    return dict(version=VERSION,operations=operations,measurementSeconds=elapsed/1e9,
        operationsPerSecond=operations/(elapsed/1e9),sampleCount=retained,sampleFraction=retained/operations,
        servicePercentilesNs={str(p):quantile(sorted(merged.items()),p) for p in (50,95,99,99.9)},
        gapPercentilesNs={str(p):quantile(sorted(gaps.items()),p) for p in (50,95,99,99.9)},
        primaryEndpointUseAllowed=False,windows=[w for r,w in zip(rows,windows) if r['phase']=='MEASUREMENT'])
