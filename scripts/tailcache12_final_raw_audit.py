#!/usr/bin/env python3
"""Independent rank/GC/allocation/bootstrap/archive reconciliation; no collector parsers."""
import collections,csv,hashlib,json,math,pathlib,random,re,statistics,tarfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
REPORTS=ROOT/'build/reports/tailcache12'
DATA=ROOT/'evidence-archives/native-final-conditional-completion-dataset-20261108-001'
PARENT='native-final-conditional-20261107-005'
SUPPLEMENT=PARENT+'-completion-20261108-001'

def load(p):return json.loads(p.read_text())
def csvrows(p):
    with p.open() as f:return list(csv.DictReader(f))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while b:=f.read(1024*1024):h.update(b)
    return h.hexdigest()
def close(a,b):
    assert (a is None and b is None) or (a is not None and b is not None and math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9)),(a,b)
def rank(bins,p):
    target=math.ceil(sum(bins.values())*p/100);n=0
    for value,count in sorted(bins.items()):
        n+=count
        if n>=target:return value
    raise ValueError('Empty rank distribution')
def size(n,u):return float(n)*1024**'BKMGT'.index(u)
def overlap(a,b,windows):return sum(max(0,min(b,y)-max(a,x)) for x,y in windows)


def gc_audit(path,windows):
    pending={};regions={};pauses=[];occupancy=[];old=[];hum=[];safepoint=0;concurrent=0
    for line in path.open():
        stamp=re.search(r'\[([0-9]+)ns\]',line);assert stamp,line
        t=int(stamp[1]);match=re.search(r'\[(?:info|debug|trace|warning|error)\]\[([^]]+)\]\s+(.*)',line);assert match,line
        tag,msg=match[1].strip(),match[2].strip()
        reg=re.match(r'GC\((\d+)\) (Eden|Survivor|Old|Humongous) regions: \d+->(\d+)',msg)
        if reg:regions.setdefault(reg[1],{})[reg[2]]=int(reg[3])
        start=re.fullmatch(r'GC\((\d+)\) (Pause .+)',msg)
        if tag=='gc,start' and start:
            key=(start[1],start[2]);assert key not in pending;pending[key]=t
        end=re.fullmatch(r'GC\((\d+)\) (Pause .+?)\s+([0-9.]+)ms',msg)
        if tag=='gc' and end:
            heap=re.search(r'([0-9.]+)([BKMG])->([0-9.]+)([BKMG])\(([0-9.]+)([BKMG])\)',end[2])
            label=end[2][:heap.start()].rstrip() if heap else end[2]
            key=(end[1],label)
            if key not in pending and label.endswith(' (Evacuation Failure)'):key=(end[1],label[:-len(' (Evacuation Failure)')])
            duration=round(float(end[3])*1e6);begin=pending.pop(key,t-duration)
            exposure=overlap(begin,t,windows)
            if exposure:pauses.append((exposure,duration))
            if heap and any(a<=t<b for a,b in windows):
                after=size(heap[3],heap[4]);capacity=size(heap[5],heap[6]);occupancy.append(after/capacity)
                r=regions.get(end[1],{})
                if 'Old' in r:old.append(r['Old']*1024**2/capacity)
                if 'Humongous' in r:hum.append(r['Humongous'])
        if tag=='safepoint':
            total=re.search(r'Total: (\d+) ns',msg)
            if total:safepoint+=overlap(t-int(total[1]),t,windows)
        if tag=='gc' and re.fullmatch(r'GC\(\d+\) Concurrent .+ Cycle [0-9.]+ms',msg) and any(a<=t<b for a,b in windows):concurrent+=1
    assert not pending,pending
    return dict(pauseCount=len(pauses),pauseOverlapMs=sum(x for x,y in pauses)/1e6,pauseTotalWholeMs=sum(y for x,y in pauses)/1e6,
        pauseMaxWholeMs=max((y for x,y in pauses),default=0)/1e6,safepointOverlapMs=safepoint/1e6,completedConcurrentCycles=concurrent,
        postGcUsedHeapMedianFraction=statistics.median(occupancy) if occupancy else None,
        oldRegionsMedianHeapFraction=statistics.median(old) if old else None,maxHumongousRegionsAfter=max(hum,default=None),occupancyCount=len(occupancy))


def independent_bootstrap(blocks,confidence,resamples):
    rng=random.Random(24301);draws=[]
    def ratio(block):return statistics.median(b for a,b in block)/statistics.median(a for a,b in block)
    point=math.sqrt(ratio(blocks[0])*ratio(blocks[1]))
    for _ in range(resamples):
        selected=[int(rng.random()*2),int(rng.random()*2)];ratios=[]
        for index in selected:
            picks=[blocks[index][int(rng.random()*3)] for j in range(3)];ratios.append(ratio(picks))
        draws.append(math.sqrt(ratios[0]*ratios[1]))
    draws.sort();tail=(1-confidence)/2
    return point,draws[math.ceil(tail*resamples)-1],draws[math.ceil((1-tail)*resamples)-1]


def main():
    out=DATA/'independent-review-002';out.mkdir(exist_ok=False);dataset=load(DATA/'dataset.json')
    observations={k:v['observations'] for k,v in dataset['stages'].items() if k!='campaign'}
    observations.update(campaign=dataset['campaignObservations'],robustness=dataset['robustnessObservations'])
    controls={};invocations={}
    for stage in observations:
        dirs=[REPORTS/(PARENT+'-'+stage)]
        if stage=='campaign':dirs.append(REPORTS/(SUPPLEMENT+'-campaign'))
        if stage=='robustness':dirs=[REPORTS/(SUPPLEMENT+'-robustness')]
        invocations[stage]={}
        for directory in dirs:
            manifest=load(directory/'manifest.json')
            assert sha(directory/'source.tar.gz')==manifest['sourceArchiveSha256']
            for inv in manifest['invocations']:
                assert inv['label'] not in invocations[stage];invocations[stage][inv['label']]=inv;controls[(stage,inv['label'])]=directory/inv['label']
                assert inv['sourceUnchanged'] and inv['exitCode']==0
                for name,wanted in inv['controlSha256'].items():assert sha(directory/inv['label']/name)==wanted
                for name,wanted in inv['rawSha256'].items():assert sha(pathlib.Path(inv['rawDirectory'])/name)==wanted
        assert len(invocations[stage])==len(observations[stage])
    counts=collections.Counter();fork_rows=[];all_hist=[];raw_compiler=[];raw_drops=0;occupancy_count=0
    for stage,rows in observations.items():
        if stage in ('functional','pause'):continue
        for row in rows:
            p=row['inputs'];channel=p['Channel'];inv=invocations[stage][row['label']];raw=pathlib.Path(inv['rawDirectory'])
            eo=channel in ('every-operation','timer');directory=raw/('every-operation' if eo else channel)
            side=directory/'worker/iterations.csv' if eo else next(directory.glob('iterations-*.csv'))
            all_rows=csvrows(side);measured=[r for r in all_rows if r['phase']=='MEASUREMENT'];assert len(measured)==8
            windows=[(int(r['startNs' if eo else 'envelopeStartNs']),int(r['endNs' if eo else 'envelopeEndNs'])) for r in measured]
            operations=sum(int(r['operations']) for r in measured);close(operations,row['operations'])
            compiler=[int(r['compilerMs' if eo else 'workerEnvelopeCompilerMs']) for r in measured];assert compiler==row['compilerPerIterationMs'];raw_compiler.extend(compiler)
            counts['physicalMeasuredWindows']+=8
            bins=collections.Counter()
            if eo:
                for r in measured:
                    entries=csvrows(directory/'worker'/f"iteration-{r['iteration']}-service-bins.csv")
                    assert sum(int(x['count']) for x in entries)==int(r['operations'])
                    bins.update({int(x['upperEquivalentNs']):int(x['count']) for x in entries})
                hdr=row['offlineHdrVerification'];assert hdr['distributionMatch'];counts['offlineDecodedHdrHistograms']+=hdr['verifiedHistograms']
            else:
                result=load(directory/'results.json')[0];h=result['primaryMetric']['rawDataHistogram'][0][p.get('Conditioning',0):]
                assert len(h)==8
                for entries,window in zip(h,measured):
                    total=sum(n for value,n in entries);assert 0<total<=int(window['operations'])
                    bins.update({int(value):int(n) for value,n in entries})
                close(sum(bins.values()),row['sampleCount']);counts['jmhRetainedSamples']+=sum(bins.values())
            for percentile in (50,95,99,99.9):close(rank(bins,percentile),row['servicePercentilesNs'][str(percentile)])
            counts['recomputedPercentileEndpoints']+=4;counts['histogramForks']+=1
            for r in all_rows:
                if r['phase'] not in ('CONDITIONING','MEASUREMENT'):continue
                dropped=int(r['churnDroppedBytes']);payload=int(r['churnPayloadBytes']);raw_drops+=dropped
                assert dropped>=0 and payload>=0 and dropped<=32768 and dropped*999<=payload
                assert int(r['churnJvmAllocatedBytes'])>=payload
                assert abs(float(r['churnPayloadBytesPerSecond'])-p['ChurnBytesPerSecond'])<=max(1,p['ChurnBytesPerSecond']*.1)
            elapsed=sum(b-a for a,b in windows)/1e9
            alloc=row['allocation'];close(sum(int(r['workerJvmAllocatedBytes']) for r in measured),alloc['workerAllocatedBytes'])
            close(sum(int(r['churnJvmAllocatedBytes']) for r in measured),alloc['churnAllocatedBytes']);close(elapsed,alloc['measurementSeconds'])
            if channel not in ('timer','floor'):
                summary=gc_audit(next(directory.glob('gc-*.log')),windows);expected=row.get('gc',row)
                for key,value in summary.items():
                    if key!='occupancyCount':close(value,expected[key])
                occupancy_count+=summary['occupancyCount'];counts['independentGcForks']+=1
                counts['measuredGcPauses']+=summary['pauseCount']
            fork_rows.append(dict(stage=stage,label=row['label'],backend=p['Backend'],payloadBytes=p['Payload'],liveMiB=p['LiveBytes']//1024**2,channel=channel,
                accepted=row['finalPolicyUsable'],operations=operations,measurementSeconds=elapsed,
                p99Ns=row['servicePercentilesNs']['99'],p999Ns=row['servicePercentilesNs']['99.9'],sampleCount=sum(bins.values()),
                heapFraction=row.get('gc',row).get('postGcUsedHeapMedianFraction'),workerBytesPerOperation=alloc['workerBytesPerOperation']))
    campaign=dataset['campaignObservations'];valid=[r for r in campaign if r['finalPolicyUsable']]
    assert set(dataset['campaign']['statisticsInputLabels'])=={r['label'] for r in valid}
    assert not set(dataset['campaign']['statisticsInputLabels'])&set(dataset['campaign']['excludedLabels'])
    comparison_rows=[]
    for cell in dataset['campaign']['comparisons']:
        channel='sample-calibration' if cell['channel']=='sample' else cell['channel']
        chosen=[r for r in valid if (r['inputs']['Channel'],r['inputs']['Payload'],r['inputs']['LiveBytes'])==(channel,cell['payloadBytes'],cell['applicationLiveBytes'])]
        assert cell['complete']==(len(chosen)==12)
        if len(chosen)!=12:assert not cell['ratios'] and not cell['resolvedConditionalClaimAllowed']
        for endpoint,interval in cell['ratios'].items():
            blocks=[]
            for block in (1,2):
                pairs=[]
                for fork in (1,2,3):
                    pair={r['inputs']['Backend']:r['servicePercentilesNs'][endpoint] for r in chosen if r['inputs']['Block']==block and r['inputs']['ForkOrdinal']==fork}
                    pairs.append((pair['CAFFEINE'],pair['CHRONICLE_IN_MEMORY']))
                blocks.append(pairs)
            point,lower,upper=independent_bootstrap(blocks,1-.05/32,50000)
            close(point,interval['ratio']);close(lower,interval['lower']);close(upper,interval['upper'])
            _,low95,high95=independent_bootstrap(blocks,.95,5000)
            close(low95,interval['descriptiveLower95']);close(high95,interval['descriptiveUpper95']);counts['independentBootstrapEndpoints']+=1
        comparison_rows.append(dict(channel=cell['channel'],payloadBytes=cell['payloadBytes'],liveMiB=cell['applicationLiveBytes']//1024**2,
            complete=cell['complete'],resolvedConditionalClaimAllowed=cell['resolvedConditionalClaimAllowed'],
            p99Ratio=cell['ratios'].get('99',{}).get('ratio'),p999Ratio=cell['ratios'].get('99.9',{}).get('ratio'),
            p99Direction=cell['ratios'].get('99',{}).get('direction'),p999Direction=cell['ratios'].get('99.9',{}).get('direction'),claimLimitations=json.dumps(cell['claimLimitations'])))
    inventory={r['path']:r for r in load(DATA/'archive-inventory.json')};seen=set()
    with tarfile.open(DATA/'raw-sources.tar.gz','r:gz') as archive:
        for member in archive:
            assert member.isfile() and member.name in inventory and member.name not in seen
            expected=inventory[member.name];h=hashlib.sha256()
            with archive.extractfile(member) as stream:
                while block:=stream.read(1024*1024):h.update(block)
            assert member.size==expected['bytes'] and h.hexdigest()==expected['sha256'];seen.add(member.name)
    assert seen==set(inventory);assert sha(DATA/'raw-sources.tar.gz')==load(DATA/'archive.json')['sha256']
    for name,rows in (('independent-forks.csv',fork_rows),('comparison-summary.csv',comparison_rows)):
        with (out/name).open('x',newline='') as f:
            writer=csv.DictWriter(f,list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary=dict(passed=True,method='Independent stdlib CSV/rank, unified-log, paired bootstrap and tar-member reconciliation; collector parsers not imported.',
        datasetSha256=sha(DATA/'dataset.json'),counts=dict(counts),occupancySamples=occupancy_count,totalConditioningAndMeasuredDroppedBytes=raw_drops,
        maximumMeasuredCompilerIntervalMs=max(raw_compiler),totalInvocations=sum(len(r) for r in observations.values()),
        campaignAccepted=len(valid),campaignRejected=len(campaign)-len(valid),completeCampaignComparisons=sum(c['complete'] for c in dataset['campaign']['comparisons']),
        resolvedConditionalComparisons=sum(c['resolvedConditionalClaimAllowed'] for c in dataset['campaign']['comparisons']),
        archiveVerifiedMembers=len(seen),archiveSha256=sha(DATA/'raw-sources.tar.gz'),originalStoppingRulePassed=False,unconditionalProtocolQualified=False)
    (out/'audit.json').write_text(json.dumps(summary,indent=2)+'\n');(out/'audit-source.py').write_bytes(pathlib.Path(__file__).read_bytes())
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
