#!/usr/bin/env python3
"""Offline empirical tails and resolution-aware stall rates; no workload runs."""
import argparse,base64,copy,csv,datetime,gzip,hashlib,json,pathlib,shutil,subprocess
import tailcache12_focus_report as report

ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT/'evidence-archives/focused-rq-p99999-20261108-001/study.json'
OUT=ROOT/'evidence-archives/focused-rq-tails-20261108-001'
THRESHOLDS=(100_000,1_000_000,10_000_000)


def lower_equivalent(upper):
    """Pinned HDR: unit magnitude 0, 3 significant digits, subbucket count 2048."""
    return upper-(1<<max(0,upper.bit_length()-11))+1


def summarize(bins,expected):
    values=[(int(r['upperEquivalentNs']),int(r['count'])) for r in bins]
    assert all(n>0 and u>=0 for u,n in values)
    assert all(a[0]<b[0] for a,b in zip(values,values[1:]))
    assert sum(n for u,n in values)==expected
    rates={};digest=hashlib.sha256()
    for u,n in values:digest.update(f'{lower_equivalent(u)},{u},{n}\n'.encode())
    for threshold in THRESHOLDS:
        low=sum(n for u,n in values if lower_equivalent(u)>threshold)
        high=sum(n for u,n in values if u>threshold)
        rates[str(threshold)]=dict(lowerCount=low,upperCount=high,
            lowerProbability=low/expected if expected else None,upperProbability=high/expected if expected else None)
    flat=[n for u,count in values for n in (u,count)]
    raw=json.dumps(flat,separators=(',',':')).encode()
    return dict(count=expected,bins=len(values),binBoundsSha256=digest.hexdigest(),rates=rates,
        encoding='gzip-base64-flat-upper-ns-count',curve=base64.b64encode(gzip.compress(raw,mtime=0)).decode(),
        curveSha256=hashlib.sha256(raw).hexdigest(),minimumBinLowerNs=lower_equivalent(values[0][0]) if values else None,
        maximumBinUpperNs=values[-1][0] if values else None,empiricalResolution=1/expected if expected else None)


def classify_rates(pairs):
    """Count fractions are compared as integers; overlapping bounds stay unresolved."""
    outcomes=[]
    for c,h in pairs:
        if h['upperCount']*c['count']<c['lowerCount']*h['count']:outcomes.append('chronicle')
        elif c['upperCount']*h['count']<h['lowerCount']*c['count']:outcomes.append('caffeine')
        elif c['lowerCount']==c['upperCount'] and h['lowerCount']==h['upperCount'] and c['lowerCount']*h['count']==h['lowerCount']*c['count']:outcomes.append('tie')
        else:outcomes.append('unresolved')
    winner=outcomes[0] if len(set(outcomes))==1 else 'mixed'
    return dict(winner=winner,outcomes=outcomes)


def run(out):
    out.mkdir(parents=True,exist_ok=False);setup=out/'setup';setup.mkdir()
    original=report.load(SOURCE);preserved={str(SOURCE.relative_to(ROOT)):report.sha(SOURCE)}
    for path in (ROOT/'evidence-archives').glob('focused-rq*-delivery-20261108-001.tar.gz'):
        preserved[str(path.relative_to(ROOT))]=report.sha(path)
    paths=[]
    for r in original['observations']:
        worker=ROOT/'evidence-archives'/r['batch']/r['label']/'worker'
        for channel in r['latency']:paths.append(worker/(channel+'.hdr'))
    (setup/'paths.txt').write_text(''.join(str(p)+'\n' for p in paths))
    java=pathlib.Path('/usr/lib/jvm/java-21-openjdk/bin');helper=ROOT/'scripts/java/TailCacheTailVerify.java'
    jar=ROOT/'evidence-archives/focused-rq-results-20261108-001/runtime-libraries/HdrHistogram-2.2.2.jar'
    assert report.sha(jar)=='22d1d4316c4ec13a68b559e98c8256d69071593731da96136640f864fa14fad8'
    subprocess.run([str(java/'javac'),'-cp',str(jar),'-d',str(setup),str(helper)],check=True)
    done=subprocess.run([str(java/'java'),'-Xmx96m','-cp',str(setup)+':'+str(jar),'TailCacheTailVerify',str(setup/'paths.txt'),str(out/'hdr-check.csv')],check=True,capture_output=True,text=True)
    assert json.loads(done.stdout)['verifiedHistograms']==396
    direct={r['path']:r for r in report.csvrows(out/'hdr-check.csv')};forks=[];checks=0;raw_files=0
    for row in original['observations']:
        worker=ROOT/'evidence-archives'/row['batch']/row['label']/'worker';channels={}
        for channel,latency in row['latency'].items():
            for suffix in ('.hdr','-bins.csv'):
                p=worker/(channel+suffix);relative='worker/'+p.name
                assert report.sha(p)==row['rawSha256'][relative],p
                raw_files+=1
            tail=summarize(report.csvrows(worker/(channel+'-bins.csv')),latency['count'])
            check=direct[str(worker/(channel+'.hdr'))]
            assert tail['count']==int(check['count']) and tail['bins']==int(check['bins'])
            assert tail['binBoundsSha256']==check['binBoundsSha256']
            for threshold,label in zip(THRESHOLDS,('gt100us','gt1ms','gt10ms')):
                rate=tail['rates'][str(threshold)]
                assert rate['lowerCount']==int(check[label+'Lower']) and rate['upperCount']==int(check[label+'Upper'])
                checks+=1
            channels[channel]=tail
        forks.append(dict(batch=row['batch'],label=row['label'],channels=channels))
    result=dict(kind='offline-full-tail-extension',complete=True,newBenchmarkRuns=0,sourceStudy=str(SOURCE.relative_to(ROOT)),sourceSha256=preserved[str(SOURCE.relative_to(ROOT))],
        thresholdsNs=THRESHOLDS,forks=forks,curveSemantics='Empirical P(T > upper-equivalent HDR bin boundary); full recorded bins, no pooling or smoothing.',
        thresholdSemantics='Strict > threshold; definite and possible counts bound any observations in a straddling HDR bin.',
        zeroSemantics='Zero observed events is not zero underlying risk; show N and 1/N resolution without inventing a confidence interval.')
    report.save(out/'tails.json',result)
    with (out/'stall-rates.csv').open('x',newline='') as stream:
        w=csv.writer(stream);w.writerow(['batch','label','payloadBytes','ballastMiB','backend','regime','block','measureMs','channel','count','thresholdNs','definiteCount','possibleCount','lowerProbability','upperProbability','warnings'])
        for row,tail in zip(original['observations'],forks):
            for channel,distribution in tail['channels'].items():
                for threshold,rate in distribution['rates'].items():
                    w.writerow([row['batch'],row['label'],row['payload'],row['liveMiB'],row['backend'],row['regime'],row['block'],row['measureMs'],channel,distribution['count'],threshold,rate['lowerCount'],rate['upperCount'],rate['lowerProbability'],rate['upperProbability'],json.dumps(row['warnings'])])
    for path,digest in preserved.items():assert report.sha(ROOT/path)==digest
    report.save(out/'audit.json',dict(passed=True,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),newBenchmarkRuns=0,workloadForks=132,decodedWorkloadHistograms=396,nonemptyChannels=336,independentThresholdChecks=checks,rawFilesVerified=raw_files,binCount=sum(t['bins'] for r in forks for t in r['channels'].values()),baseArtifactsUnchanged=preserved,
        tailsSha256=report.sha(out/'tails.json'),implementationSha256={str(p.relative_to(ROOT)):report.sha(p) for p in (pathlib.Path(__file__),helper)}))
    shutil.copyfile(pathlib.Path(__file__),out/'analysis-source.py');shutil.copyfile(helper,out/helper.name)
    print(json.dumps(report.load(out/'audit.json'),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=pathlib.Path,default=OUT)
    run(parser.parse_args().out.resolve())
