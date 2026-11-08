#!/usr/bin/env python3
"""Offline p99.99 extension of the retained focused study; never launches workloads."""
import argparse,collections,copy,csv,datetime,hashlib,json,math,pathlib,shutil,subprocess
import tailcache12_focus_report as report
import tailcache12_focused as focused

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/'evidence-archives/focused-rq-results-20261108-001'
DEFAULT_OUT=ROOT/'evidence-archives/focused-rq-p9999-20261108-001'
PERCENTILES=(50,99,99.9,99.99)


def extract(bins,expected):
    """Rank actual HDR bins; expose finite sample/tie support without inventing a CI."""
    values=[(int(r['upperEquivalentNs']),int(r['count'])) for r in bins]
    assert all(n>0 for v,n in values)
    assert all(a[0]<b[0] for a,b in zip(values,values[1:]))
    total=sum(n for v,n in values)
    assert total==expected
    ranks={str(p):max(1,math.ceil(math.nextafter(p,-math.inf)*total/100)) for p in PERCENTILES}
    quantiles={str(p):None for p in PERCENTILES};support=None;acc=0
    for value,count in values:
        acc+=count
        for p,rank in ranks.items():
            if quantiles[p] is None and acc>=rank:quantiles[p]=value
        if support is None and acc>=ranks['99.99']:
            support=dict(rank=ranks['99.99'],selectedBinCount=count,strictlyAboveSelectedBin=total-acc)
    return quantiles,dict(count=total,nominalUpperTailObservations=total/10000,
        p9999=support,approxAtLeastOneMs=sum(n for v,n in values if v>=1_000_000),
        thresholdNote='Millisecond count uses HDR upper-equivalent bin bounds; not event-level attribution to GC.')


def paired(rows):
    result=[];groups=collections.defaultdict(list)
    for r in rows:groups[(r['batch'],r['liveMiB'],r['regime'])].append(r)
    for (batch,live,regime),chosen in sorted(groups.items()):
        channel='response' if regime=='arrival' else 'service'
        pairs=[]
        for block in (1,2,3):
            by={r['backend']:r for r in chosen if r['block']==block}
            assert set(by)=={'CAFFEINE','CHRONICLE_IN_MEMORY'}
            pairs.append(dict(block=block,warningBearing=any(r['warnings'] for r in by.values()),
                ratios={p:by['CHRONICLE_IN_MEMORY']['latency'][channel]['percentilesNs'][p]/by['CAFFEINE']['latency'][channel]['percentilesNs'][p] for p in ('99','99.9','99.99')}))
        result.append(dict(batch=batch,ballastMiB=live,regime=regime,channel=channel,pairs=pairs,
            warningFreeBlocks=[p['block'] for p in pairs if not p['warningBearing']]))
    return result


def figures(rows,out):
    # Reuse only the plotting primitive; write into this derivative, never BASE.
    report.OUT=out;(out/'figures').mkdir()
    def points(selected,backend,channel,p):
        answer=[]
        for live in sorted({r['liveMiB'] for r in selected}):
            rs=[r for r in selected if r['liveMiB']==live and r['backend']==backend]
            answer.append((live,[r['latency'][channel]['percentilesNs'][p]/1000 for r in rs],[bool(r['warnings']) for r in rs]))
        return answer
    f=report.Figure('Service tails: p99.9 versus requested p99.99',
        'Same retained forks | ordinary get | 512 MiB G1 | three pairs/point | no new benchmark runs',height=930)
    for row,payload in enumerate((4096,256)):
        selected=[r for r in rows if r['payload']==payload and r['regime']=='closed' and not r['batch'].startswith('focused-reuse')]
        for col,p in enumerate(('99.9','99.99')):
            ymin=0;ymax=(16 if col==0 else 50) if payload==4096 else (4 if col==0 else 32)
            yticks=([0,4,8,12,16] if col==0 else [0,10,20,30,40,50]) if payload==4096 else ([0,1,2,3,4] if col==0 else [0,8,16,24,32])
            ticks=[328,352,360,368] if payload==4096 else [448,464,472,480]
            xmin,xmax=(324,372) if payload==4096 else (444,484)
            label='4 KiB' if payload==4096 else '256 B'
            xf,yf=f.panel(85+col*740,135+row*375,590,235,f'{label} service p{p}',xmin,xmax,ymin,ymax,ticks,yticks,'Common application ballast (MiB)','microseconds')
            for index,b in enumerate(('CAFFEINE','CHRONICLE_IN_MEMORY')):
                f.series(xf,yf,points(selected,b,'service',p),report.COLORS[b],b.replace('_IN_MEMORY',' get') if row==0 and col==0 else '',100+250*index,845)
    f.text(35,885,'p99.99: Caffeine service is lower at every tested primary point for both payloads. The 256 B p99.9 reverse crossover does not carry over.',13)
    f.text(35,912,'Dots: individual forks; large dot: median; bars: min–max, not CI. Hollow dots retain warnings. 256 B midpoints use the later runtime.',12)
    f.write('service_p999_vs_p9999')
    selected=[r for r in rows if r['batch'] in ('focused-rq1-response-long-20261108-001','focused-rq1-response-bracket-20261108-001')]
    f=report.Figure('Scheduled response: percentile choice changes the crossover statement',
        '4 KiB ordinary get | 50,000 arrivals/s | matched 30 s windows | same three pairs/point | intended-arrival timestamps')
    for col,p in enumerate(('99.9','99.99')):
        xf,yf=f.panel(85+col*740,130,590,345,'Response p'+p,0,300,10,10000,[0,104,208,248,288],[10,100,1000,10000],
            'Common application ballast (MiB)','microseconds (log)',True)
        for index,b in enumerate(('CAFFEINE','CHRONICLE_IN_MEMORY')):
            f.series(xf,yf,points(selected,b,'response',p),report.COLORS[b],b.replace('_IN_MEMORY',' get') if col==0 else '',100+250*index,560)
    f.text(35,605,'p99.9 crosses between 0–208 MiB. At p99.99 Chronicle is already lower at baseline and stays lower: no new forward bracket is established.',13)
    f.text(35,630,'Each 30 s fork has 1,500,000 actual response observations; nominal upper 0.01% contains 150 observations. No samples pooled.',12)
    f.write('response_p999_vs_p9999')


def markdown(rows,comparisons):
    lines=['# All retained focused comparisons at p99.99','',
        'Ranges are across three forks, not confidence intervals. Ratios are Chronicle/Caffeine in block order; below1 favors Chronicle. All warnings and source groups remain attached in study.json.','',
        '| Batch | Ballast MiB | Channel | Caffeine p99.99 µs | Chronicle p99.99 µs | Paired ratios | Clean blocks |',
        '| --- | --- | --- | --- | --- | --- | --- |']
    for c in comparisons:
        selected=[r for r in rows if r['batch']==c['batch'] and r['liveMiB']==c['ballastMiB'] and r['regime']==c['regime']]
        ranges=[]
        for backend in ('CAFFEINE','CHRONICLE_IN_MEMORY'):
            v=[r['latency'][c['channel']]['percentilesNs']['99.99']/1000 for r in selected if r['backend']==backend]
            ranges.append(f'{min(v):.3f}–{max(v):.3f}')
        ratios=', '.join(f"{p['ratios']['99.99']:.3f}" for p in c['pairs'])
        lines.append(f"| {c['batch']} | {c['ballastMiB']} | {c['channel']} | {ranges[0]} | {ranges[1]} | {ratios} | {c['warningFreeBlocks']} |")
    return '\n'.join(lines)+'\n'


def run(out):
    if out.exists():raise ValueError('Derivative already exists; preserve evidence')
    out.mkdir(parents=True);setup=out/'setup';setup.mkdir();decoded=out/'decoded';decoded.mkdir()
    original=report.load(BASE/'study.json');archive=ROOT/'evidence-archives/focused-rq-delivery-20261108-001.tar.gz'
    original_hashes={str(p.relative_to(ROOT)):report.sha(p) for p in (BASE/'study.json',BASE/'audit.json',BASE/'delivery-members.json',archive)}
    jar=BASE/'runtime-libraries/HdrHistogram-2.2.2.jar'
    wanted=next(v['sha256'] for k,v in report.load(BASE/'runtime-libraries.json')['files'].items() if k.endswith('/HdrHistogram-2.2.2.jar'))
    assert report.sha(jar)==wanted
    java=pathlib.Path('/usr/lib/jvm/java-21-openjdk/bin');helper=ROOT/'scripts/java/TailCacheFocusedHdrVerify.java'
    subprocess.run([str(java/'javac'),'-cp',str(jar),'-d',str(setup),str(helper)],check=True)
    hdr={};inventories=0;decoded_count=0
    for batch in original['batches']:
        base=ROOT/'evidence-archives'/batch['batch']
        for entry in report.load(base/'inventory.json'):
            path=base/entry['path'];assert path.stat().st_size==entry['bytes'] and report.sha(path)==entry['sha256'];inventories+=1
        endpoint_file=decoded/(base.name+'.csv')
        done=subprocess.run([str(java/'java'),'-Xmx64m','-cp',str(setup)+':'+str(jar),'TailCacheFocusedHdrVerify',str(base),str(endpoint_file)],check=True,capture_output=True,text=True)
        proof=json.loads(done.stdout);records=report.csvrows(endpoint_file)
        assert len(records)==proof['verifiedHistograms'];decoded_count+=len(records)
        for r in records:
            assert r['path'] not in hdr;hdr[r['path']]=r
    rows=copy.deepcopy(original['observations']);checks=0
    endpoint_keys={'50':'p50Ns','99':'p99Ns','99.9':'p999Ns','99.99':'p9999Ns'}
    for r in rows:
        worker=ROOT/'evidence-archives'/r['batch']/r['label']/'worker'
        for channel in ('service','gap','response'):
            count=r['latency'][channel]['count']
            values,support=extract(report.csvrows(worker/(channel+'-bins.csv')),count)
            direct=hdr[str(worker/(channel+'.hdr'))]
            assert int(direct['count'])==count
            for p,key in endpoint_keys.items():
                assert (values[p] if count else 0)==int(direct[key]),(r['label'],channel,p)
                if count:checks+=1
                if p!='99.99':assert values[p]==r['latency'][channel]['percentilesNs'][p]
            r['latency'][channel]['percentilesNs']=values
            r['latency'][channel]['tailSupport']=support
    comparisons=paired(rows)
    report.save(out/'study.json',dict(kind='user-requested-post-hoc-p9999-extension',complete=True,baseStudy=str(BASE.relative_to(ROOT)/'study.json'),
        newBenchmarkRuns=0,percentiles=list(PERCENTILES),observations=rows,comparisons=comparisons,
        limits=['Post hoc extension; original endpoints and evidence unchanged.','No pooling across forks, windows, read contracts or runtime groups.',
                'Extreme percentile uncertainty and autocorrelation are not removed by a large operation count.','No precise crossover threshold or invented confidence interval.']))
    with (out/'forks.csv').open('x',newline='') as f:
        writer=csv.writer(f);writer.writerow(['batch','label','payloadBytes','ballastMiB','backend','accessMode','regime','block','measureMs','channel','count','p99Us','p999Us','p9999Us','nominalUpperTailObservations','p9999Rank','strictlyAboveSelectedBin','approxAtLeastOneMs','warnings'])
        for r in rows:
            for channel in ('service','gap','response'):
                l=r['latency'][channel];v=l['percentilesNs'];t=l['tailSupport'];s=t['p9999']
                writer.writerow([r['batch'],r['label'],r['payload'],r['liveMiB'],r['backend'],r.get('accessMode','get'),r['regime'],r['block'],r['measureMs'],channel,t['count'],
                    *[v[p]/1000 if v[p] is not None else '' for p in ('99','99.9','99.99')],t['nominalUpperTailObservations'],s['rank'] if s else '',s['strictlyAboveSelectedBin'] if s else '',t['approxAtLeastOneMs'],json.dumps(r['warnings'])])
    (out/'comparisons.md').open('x').write(markdown(rows,comparisons))
    figures(rows,out)
    for name in original_hashes:assert report.sha(ROOT/name)==original_hashes[name],name
    report.save(out/'audit.json',dict(passed=True,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),newBenchmarkRuns=0,workloadForks=len(rows),
        workloadHistograms=len(rows)*3,decodedWorkloadAndControlHistograms=decoded_count,independentPercentileChecks=checks,inventoryFilesVerified=inventories,
        baseArtifactsUnchanged=original_hashes,implementationSha256={str(p.relative_to(ROOT)):report.sha(p) for p in (pathlib.Path(__file__),helper,ROOT/'scripts/tailcache12_focused.py',ROOT/'scripts/tailcache12_focus_report.py')},hdrJarSha256=wanted))
    shutil.copyfile(pathlib.Path(__file__),out/'analysis-source.py');shutil.copyfile(helper,out/'TailCacheFocusedHdrVerify.java')
    print(json.dumps(report.load(out/'audit.json'),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=pathlib.Path,default=DEFAULT_OUT)
    run(parser.parse_args().out.resolve())
