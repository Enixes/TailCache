#!/usr/bin/env python3
"""Static scientific figures from the audited midpoint cohort; no collection."""
import json,pathlib,shutil
import tailcache12_focus_report as plot

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence-archives/midpoint-results-20261110-001'


def main():
    study=json.loads((OUT/'study.json').read_text());rows=[r for r in study['observations'] if r['cohort']=='primary']
    plot.OUT=OUT;(OUT/'figures').mkdir(exist_ok=True)
    def points(backend,metric):
        return [(live,[metric(r) for r in rows if r['liveMiB']==live and r['backend']==backend],
                 [bool(r['warnings']) for r in rows if r['liveMiB']==live and r['backend']==backend]) for live in (0,104,208)]
    f=plot.Figure('Fresh response p99.9 replication: the 104 MiB point remains mixed',
        '4 KiB ordinary get | 50,000 arrivals/s | 30 s offered windows | three fresh pairs/point | hollow points carry JIT warnings')
    x,y=f.panel(100,125,580,350,'Scheduled response p99.9',0,220,10,3000,[0,104,208],[10,100,1000],
        'Common application ballast (MiB)','Latency (microseconds)',True)
    for i,b in enumerate(plot.COLORS.keys()):
        if b not in ('CAFFEINE','CHRONICLE_IN_MEMORY'):continue
        f.series(x,y,points(b,lambda r:r['latency']['response']['percentilesNs']['99.9']/1000),plot.COLORS[b],
            'Caffeine' if b=='CAFFEINE' else 'Chronicle ordinary get',100+250*i,560)
    x,y=f.panel(850,125,560,350,'Paired Chronicle / Caffeine ratio',0,220,.1,30,[0,104,208],[.1,1,10],
        'Common application ballast (MiB)','Below 1 favours Chronicle',True)
    f.line(x(0),y(1),x(220),y(1),'#64748b',1,'5 4')
    for r in study['conclusions']:
        if r['cohort']!='primary' or r['channel']!='response' or r['percentile']!='99.9':continue
        for ratio in r['pairedRatios']:
            f.parts.append(f'<circle cx="{x(r["ballastMiB"])}" cy="{y(ratio)}" r="5" fill="#334155"/>')
    f.text(100,615,'Ranges are min–max, not confidence intervals. Connected medians are guides, not an interpolated threshold.',14)
    f.write('midpoint_response_and_ratio')
    f=plot.Figure('Reduced GC heap occupancy does not establish reduced total process residency',
        'Same 512 MiB JVM heap and application demand | primary cohort only | coarse 1 Hz RSS, not PSS or exact native allocation')
    for at,(title,metric,low,high,ticks,label) in enumerate([
        ('Post-GC heap occupancy',lambda r:r['gc']['postGcUsedHeapMedianFraction']*100,0,85,[0,20,40,60,80],'Used heap (%)'),
        ('Measured-window sampled RSS maximum',lambda r:r['processMemory']['measuredMaxRssKiB']/1024,500,850,[500,600,700,800],'Resident memory (MiB)')]):
        x,y=f.panel(100+750*at,125,560,350,title,0,220,low,high,[0,104,208],ticks,'Common application ballast (MiB)',label)
        for i,b in enumerate(('CAFFEINE','CHRONICLE_IN_MEMORY')):
            f.series(x,y,points(b,metric),plot.COLORS[b],('Caffeine' if b=='CAFFEINE' else 'Chronicle') if at==0 else '',100+250*i,560)
    f.text(100,615,'At 208 MiB, Chronicle uses less post-GC heap but has higher sampled RSS. This is not an equal-total-memory experiment.',14)
    f.write('midpoint_heap_and_residency')
    target=ROOT/'docs/figures';target.mkdir(exist_ok=True)
    for p in (OUT/'figures').glob('midpoint_*'):shutil.copyfile(p,target/p.name)
    print(json.dumps({'figures':[str(p.relative_to(ROOT)) for p in sorted(target.glob('midpoint_*'))]},indent=2))


if __name__=='__main__':main()
