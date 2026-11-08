#!/usr/bin/env python3
"""Build an offline HTML explorer from retained, verified measurements only."""
import argparse,collections,hashlib,json,pathlib,re

ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT/'evidence-archives/focused-rq-p9999-20261108-001/study.json'
TEMPLATE=ROOT/'scripts/tailcache12_explorer.html'
OUTPUT=ROOT/'docs/TAILCACHE_RESULTS_EXPLORER.html'
PERCENTILES=('99','99.9','99.99')


def embedded_download(name):
    """The committed standalone page preserves inputs for a fresh checkout."""
    match=re.search(r'<script id="study-data" type="application/json">(.*?)</script>',OUTPUT.read_text(),re.S)
    if match is None:raise ValueError('Retained source and embedded source are unavailable')
    file=json.loads(match.group(1))['downloads'][name]
    assert hashlib.sha256(file['text'].encode()).hexdigest()==file['sha256']
    return file['text']


def load_study(source=SOURCE):
    return source.read_text() if source.exists() else embedded_download('study')


def classify(caffeine,chronicle):
    assert len(caffeine)==len(chronicle)==3
    ratios=[h/c for c,h in zip(caffeine,chronicle)]
    wins=dict(caffeine=sum(v>1 for v in ratios),chronicle=sum(v<1 for v in ratios),tie=sum(v==1 for v in ratios))
    winner='chronicle' if wins['chronicle']==3 else 'caffeine' if wins['caffeine']==3 else 'tie' if wins['tie']==3 else 'mixed'
    return dict(winner=winner,wins=wins,ratios=ratios,caffeine=[min(caffeine),max(caffeine)],chronicle=[min(chronicle),max(chronicle)])


def build_data(source):
    source_text=load_study(source)
    original=json.loads(source_text);observations=original['observations'];forks=[];by=collections.defaultdict(list)
    for index,r in enumerate(observations):
        forks.append({k:r[k] for k in ('label','batch','backend','payload','liveMiB','block','regime','measureMs','runtimeGroup','warnings','measurement','gc','latency')})
        by[(r['batch'],r['liveMiB'],r['regime'])].append(index)
    runtime_ids=sorted({r['runtimeGroup'] for r in observations})
    # Names describe the measured runtime, not the order of lexicographic hashes.
    earlier=next(r['runtimeGroup'] for r in observations if r['batch']=='focused-rq2-256-20261108-001')
    runtime_names={k:'Earlier build' if k==earlier else 'Later build' for k in runtime_ids}
    groups=[]
    for (batch,live,regime),indices in sorted(by.items()):
        first=observations[indices[0]]
        assert len(indices)==6 and len({observations[i]['runtimeGroup'] for i in indices})==1
        pairs=[]
        for block in (1,2,3):
            by_backend={observations[i]['backend']:i for i in indices if observations[i]['block']==block}
            assert set(by_backend)=={'CAFFEINE','CHRONICLE_IN_MEMORY'}
            pairs.append(dict(block=block,c=by_backend['CAFFEINE'],h=by_backend['CHRONICLE_IN_MEMORY']))
        for channel in ('service','gap','response'):
            if channel=='response' and regime!='arrival':continue
            conclusions={}
            for p in PERCENTILES:
                c=[forks[pair['c']]['latency'][channel]['percentilesNs'][p] for pair in pairs]
                h=[forks[pair['h']]['latency'][channel]['percentilesNs'][p] for pair in pairs]
                assert all(v is not None and v>0 for v in c+h)
                conclusions[p]=classify(c,h)
            groups.append(dict(id='point-'+str(len(groups)),batch=batch,ballast=live,payload=first['payload'],regime=regime,
                duration=first['measureMs']//1000,runtime=first['runtimeGroup'],runtimeName=runtime_names[first['runtimeGroup']],
                contract='reuse' if batch.startswith('focused-reuse') else 'ordinary',channel=channel,pairs=pairs,conclusions=conclusions,
                primary=(regime=='closed' and channel=='service') or (regime=='arrival' and channel=='response'),
                warningPairs=sum(bool(forks[p['c']]['warnings'] or forks[p['h']]['warnings']) for p in pairs)))
    assert len(forks)==132 and len(groups)==56 and sum(g['primary'] for g in groups)==22
    return dict(forks=forks,groups=groups,percentiles=PERCENTILES,source=str(source.relative_to(ROOT)),
        sourceSha256=hashlib.sha256(source_text.encode()).hexdigest(),runtimeNames=runtime_names,
        studyDate='8 November 2026',heapMiB=512,offeredQps=50000,residentEntries=32768,backgroundMiBPerSecond=32)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=pathlib.Path,default=OUTPUT);args=parser.parse_args()
    data=build_data(SOURCE)
    data['downloads']={
        'study':dict(name='tailcache-p9999-study.json',mime='application/json',text=load_study()),
        'audit':dict(name='tailcache-p9999-audit.json',mime='application/json',text=(SOURCE.parent/'audit.json').read_text() if (SOURCE.parent/'audit.json').exists() else embedded_download('audit')),
        'review':dict(name='tailcache-research-review.md',mime='text/markdown',text=(ROOT/'docs/TAILCACHE_FOCUSED_RESULTS.md').read_text()),
    }
    for file in data['downloads'].values():
        file['sha256']=hashlib.sha256(file['text'].encode()).hexdigest()
    embedded=json.dumps(data,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=TEMPLATE.read_text();assert template.count('__TAILCACHE_DATA__')==1
    args.out.write_text(template.replace('__TAILCACHE_DATA__',embedded))
    print(json.dumps(dict(html=str(args.out.relative_to(ROOT)),bytes=args.out.stat().st_size,forks=len(data['forks']),primaryComparisons=22,allChannelComparisons=56,percentileConclusions=168,sourceSha256=data['sourceSha256']),indent=2))


if __name__=='__main__':main()
