#!/usr/bin/env python3
"""Compact audited RQ synthesis and standalone SVG/PNG figures; no new benchmarks."""
import collections,csv,datetime,hashlib,html,json,math,pathlib,re,shutil,statistics,subprocess,tarfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence-archives/focused-rq-results-20261108-001'
COLORS={'CAFFEINE':'#b91c1c','CHRONICLE_IN_MEMORY':'#0369a1','reuse':'#047857'}

def load(p):return json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while b:=f.read(1024*1024):h.update(b)
    return h.hexdigest()
def csvrows(p):
    with p.open() as f:return list(csv.DictReader(f))
def save(p,v):p.open('x').write(json.dumps(v,indent=2)+'\n')
def median(v):return statistics.median(v)


def warning_sensitivity(observations):
    """Describe all paired ratios and warning-free sensitivity, without deleting data."""
    groups=collections.defaultdict(list)
    for r in observations:groups[(r['batch'],r['liveMiB'],r['regime'])].append(r)
    result=[]
    for (batch,live,regime),rows in sorted(groups.items()):
        channel='response' if regime=='arrival' else 'service'
        pairs=[]
        for block in (1,2,3):
            pair={r['backend']:r for r in rows if r['block']==block}
            assert set(pair)=={'CAFFEINE','CHRONICLE_IN_MEMORY'}
            pairs.append(dict(block=block,warningBearing=any(r['warnings'] for r in pair.values()),
                ratios={p:pair['CHRONICLE_IN_MEMORY']['latency'][channel]['percentilesNs'][p]/pair['CAFFEINE']['latency'][channel]['percentilesNs'][p] for p in ('99','99.9')}))
        result.append(dict(batch=batch,ballastMiB=live,regime=regime,channel=channel,pairs=pairs,
            warningFreeBlocks=[p['block'] for p in pairs if not p['warningBearing']],
            note='All pairs remain in the dataset; warning-free subset is descriptive sensitivity, not replacement evidence.'))
    return result


def audit_gc(path,start,end):
    starts={};events=[];occupancy=[]
    size=lambda n,u:float(n)*1024**'BKMG'.index(u)
    for line in path.open():
        m=re.search(r'\[(\d+)ns\]\[(?:info|debug|warning|error|trace)\]\[([^]]+)\]\s+(.*)',line)
        if not m:continue
        t,tag,text=int(m[1]),m[2].strip(),m[3].strip()
        s=re.fullmatch(r'GC\((\d+)\) (Pause .+)',text)
        if tag=='gc,start' and s:starts[(s[1],s[2])]=t
        f=re.fullmatch(r'GC\((\d+)\) (Pause .+?)\s+([0-9.]+)ms',text)
        if tag=='gc' and f:
            heap=re.search(r'([0-9.]+)([BKMG])->([0-9.]+)([BKMG])\(([0-9.]+)([BKMG])\)',f[2])
            label=f[2][:heap.start()].rstrip() if heap else f[2]
            key=(f[1],label)
            if key not in starts and label.endswith(' (Evacuation Failure)'):key=(f[1],label.removesuffix(' (Evacuation Failure)'))
            a=starts.pop(key,t-round(float(f[3])*1e6));overlap=max(0,min(end,t)-max(start,a))
            if overlap:events.append((overlap,'Pause Full' in label))
            if heap and start<=t<end:occupancy.append(size(heap[3],heap[4])/size(heap[5],heap[6]))
    return dict(pauseCount=len(events),fullGcCount=sum(full for n,full in events),pauseOverlapMs=sum(n for n,full in events)/1e6,
        postGcUsedHeapMedianFraction=median(occupancy) if occupancy else None)


def audit():
    batches=sorted((ROOT/'evidence-archives').glob('focused-*/summary.json'))
    all_rows=[];batch_rows=[];files_verified=0;gc_checks=0;hist_checks=0;decoded=0;runtime_groups=collections.defaultdict(list)
    for file in batches:
        base=file.parent;s=load(file);p=load(base/'protocol.json')
        assert s['completeCollection'] and s['sourceUnchanged'] and s['collected']==s['planned']
        assert [r['label'] for r in s['results']]==[r['label'] for r in p['schedule']]
        for entry in load(base/'inventory.json'):
            q=base/entry['path'];assert q.stat().st_size==entry['bytes'] and sha(q)==entry['sha256'],q;files_verified+=1
        decoded+=load(base/'hdr-verification.json')['verifiedHistograms']
        classes={k.removeprefix(str(ROOT/'build/classes/java/main')+'/'):v for k,v in p['runtimeSha256'].items() if k.startswith(str(ROOT/'build/classes/java/main')+'/')}
        for name,digest in classes.items():
            options=[OUT/'runtime-before-reuse'/name,OUT/'runtime-after-reuse'/name]
            assert any(q.exists() and sha(q)==digest for q in options),('runtime',name)
        group=hashlib.sha256(json.dumps(classes,sort_keys=True).encode()).hexdigest();runtime_groups[group].append(base.name)
        for r in s['results']:
            raw=base/r['label'];assert r['status']=='OK' and r['latencyVerified'],r['label']
            window=next(w for w in csvrows(raw/'worker/windows.csv') if w['phase']=='MEASUREMENT')
            start,end=int(window['startNs']),int(window['endNs']);n=int(window['operations'])
            if r['regime']=='arrival':
                assert n==int(window['scheduled'])==p['measureMs']*r['qps']//1000
                assert r['latency']['response']['count']==n and r['completion']['unserved']=='0'
            for channel in ('service','gap','response'):
                bins=csvrows(raw/'worker'/(channel+'-bins.csv'));total=sum(int(b['count']) for b in bins)
                assert total==r['latency'][channel]['count']
                if total:
                    for percentile in (50,99,99.9):
                        target=max(1,math.ceil(math.nextafter(percentile,-math.inf)*total/100));acc=0
                        for b in bins:
                            acc+=int(b['count'])
                            if acc>=target:
                                assert int(b['upperEquivalentNs'])==r['latency'][channel]['percentilesNs'][str(percentile)];break
                        hist_checks+=1
            independent=audit_gc(raw/'gc.log',start,end)
            for key,value in independent.items():
                assert value==r['gc'][key] or math.isclose(value,r['gc'][key],rel_tol=1e-12,abs_tol=1e-6),(r['label'],key,value,r['gc'][key])
            gc_checks+=1
            observation=dict(r,batch=base.name,measureMs=p['measureMs'],runtimeGroup=group)
            all_rows.append(observation)
        commands=[load(base/r['label']/'command.json')['startedUtc'] for r in s['results']]
        finish=load(base/'progress.json')['utc']
        elapsed=(datetime.datetime.fromisoformat(finish)-datetime.datetime.fromisoformat(min(commands))).total_seconds()
        batch_rows.append(dict(batch=base.name,collected=s['collected'],seconds=elapsed,sourceSha256=p['sourceSha256'],
            summarySha256=sha(file),inventorySha256=sha(base/'inventory.json'),runtimeGroup=group))
    return all_rows,batch_rows,dict(passed=True,forks=len(all_rows),batchCount=len(batches),inventoryFilesVerified=files_verified,
        independentMeasuredGcChecks=gc_checks,independentHistogramPercentileChecks=hist_checks,decodedCompressedHistograms=decoded,
        runtimeGroups=dict(runtime_groups),replacementForks=0,ooms=0,censoredRequests=0,
        warnings=dict(collections.Counter(w for r in all_rows for w in r['warnings'])),
        collectionSeconds=sum(b['seconds'] for b in batch_rows))


class Figure:
    def __init__(self,title,subtitle,width=1500,height=650):
        self.w,self.h=width,height
        self.parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="white"/>','<style>text{font-family:DejaVu Sans,sans-serif;fill:#172033}</style>']
        self.text(35,36,title,24,weight='bold');self.text(35,65,subtitle,14)
    def text(self,x,y,text,size=13,anchor='start',weight='normal'):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}">{html.escape(str(text))}</text>')
    def line(self,x1,y1,x2,y2,color='#d7dee8',width=1,dash=''):
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}"/>')
    def panel(self,x,y,w,h,title,xmin,xmax,ymin,ymax,xticks,yticks,xlabel,ylabel,log=False):
        self.text(x,y-20,title,17,weight='bold')
        xf=lambda value:x+(value-xmin)/(xmax-xmin)*w
        yf=lambda value:y+h-((math.log10(value)-math.log10(ymin))/(math.log10(ymax)-math.log10(ymin)) if log else (value-ymin)/(ymax-ymin))*h
        for value in yticks:
            yy=yf(value);self.line(x,yy,x+w,yy);self.text(x-10,yy+4,f'{value:g}',12,'end')
        for value in xticks:
            xx=xf(value);self.line(xx,y+h,xx,y+h+5,'#64748b');self.text(xx,y+h+22,f'{value:g}',12,'middle')
        self.line(x,y,x,y+h,'#64748b');self.line(x,y+h,x+w,y+h,'#64748b')
        self.text(x+w/2,y+h+47,xlabel,13,'middle');self.text(x,y-3,ylabel,12)
        return xf,yf
    def series(self,xf,yf,points,color,label,legend_x,legend_y):
        last=None
        for x,values,warnings in points:
            xx,yy=xf(x),yf(median(values))
            if last:self.line(*last,xx,yy,color,2)
            self.line(xx,yf(min(values)),xx,yf(max(values)),color,2)
            for value,warning in zip(values,warnings):
                self.parts.append(f'<circle cx="{xx}" cy="{yf(value)}" r="4" fill="{("white" if warning else color)}" stroke="{color}" stroke-width="1.5"/>')
            self.parts.append(f'<circle cx="{xx}" cy="{yy}" r="6" fill="{color}"/>');last=(xx,yy)
        if label:
            self.line(legend_x,legend_y,legend_x+20,legend_y,color,3);self.text(legend_x+27,legend_y+4,label,12)
    def write(self,name):
        path=OUT/'figures'/name;path.with_suffix('.svg').write_text(''.join(self.parts)+'</svg>')
        subprocess.run(['rsvg-convert','--width',str(self.w*2),'--output',str(path.with_suffix('.png')),str(path.with_suffix('.svg'))],check=True)


def make_figures(observations):
    bybatch=collections.defaultdict(list)
    for r in observations:bybatch[r['batch']].append(r)
    def points(selected,backend,metric):
        result=[]
        for live in sorted({r['liveMiB'] for r in selected}):
            chosen=[r for r in selected if r['liveMiB']==live and r['backend']==backend]
            if chosen:result.append((live,[metric(r) for r in chosen],[bool(r['warnings']) for r in chosen]))
        return result
    (OUT/'figures').mkdir(exist_ok=True)
    selected=bybatch['focused-rq1-response-long-20261108-001']+bybatch['focused-rq1-response-bracket-20261108-001']
    f=Figure('RQ1: actual scheduled-response crossover, 4 KiB','512 MiB G1 | 50,000 arrivals/s | matched 30 s offered windows | three paired runs per point | no synthetic correction')
    xf,yf=f.panel(90,125,600,350,'Response p99.9',0,300,10,10000,[0,104,208,248,288],[10,100,1000,10000],'Common application ballast (MiB)','Latency (microseconds)',True)
    for i,b in enumerate(('CAFFEINE','CHRONICLE_IN_MEMORY')):
        f.series(xf,yf,points(selected,b,lambda r:r['latency']['response']['percentilesNs']['99.9']/1000),COLORS[b],b.replace('_IN_MEMORY',' get'),100+250*i,560)
    xf,yf=f.panel(860,125,560,350,'Paired Chronicle / Caffeine p99.9 ratio',0,300,.1,100,[0,104,208,248,288],[.1,1,10,100],'Common application ballast (MiB)','Ratio; below 1 favors Chronicle',True)
    f.line(xf(0),yf(1),xf(300),yf(1),'#334155',2,'6 4')
    for live in (0,208,248,288):
        v=[];flags=[]
        for block in (1,2,3):
            pair={r['backend']:r for r in selected if r['liveMiB']==live and r['block']==block}
            v.append(pair['CHRONICLE_IN_MEMORY']['latency']['response']['percentilesNs']['99.9']/pair['CAFFEINE']['latency']['response']['percentilesNs']['99.9']);flags.append(any(r['warnings'] for r in pair.values()))
        f.series(xf,yf,[(live,v,flags)],'#6d28d9','',1450,600)
    f.text(35,605,'First observed forward bracket: 0–208 MiB ballast (~31–33% to ~72% Caffeine post-GC heap). No interpolated threshold.',14)
    f.text(35,630,'Small circles: individual forks/pairs; large: median; bars: min–max, not confidence intervals. Hollow circles retain warning-bearing data.',12)
    f.write('rq1_scheduled_response')
    selected=[r for r in observations if r['payload']==4096 and r['regime']=='closed' and not r.get('reuse')]
    f=Figure('RQ1: service percentiles can stay small while GC destroys throughput','Ordinary get | 8 s saturated windows | three pairs/point | all pressure outcomes retained')
    panels=[('Service p99.9',lambda r:r['latency']['service']['percentilesNs']['99.9']/1000,0,16,[0,4,8,12,16],'microseconds'),
        ('GC pause exposure',lambda r:r['gc']['pauseExposureFraction']*100,0,80,[0,20,40,60,80],'% of measured wall time'),
        ('Completed throughput',lambda r:r['measurement']['operations']*1000/(r['measurement']['endNs']-r['measurement']['startNs']),0,2,[0,.5,1,1.5,2],'million operations/s')]
    for index,(title,metric,ymin,ymax,ticks,label) in enumerate(panels):
        xf,yf=f.panel(75+index*495,130,400,350,title,324,372,ymin,ymax,[328,352,360,368],ticks,'Application ballast (MiB)',label)
        for i,b in enumerate(('CAFFEINE','CHRONICLE_IN_MEMORY')):f.series(xf,yf,points(selected,b,metric),COLORS[b],b.replace('_IN_MEMORY',' get'),80+index*495,555+i*25)
    f.text(35,620,'No ordinary-get service p99/p99.9 forward crossover at the tested 4 KiB points, including ~99.3% heap occupancy. Survival boundary not located.',13)
    f.write('rq1_service_gc_throughput')
    selected=[r for r in observations if r['payload']==256 and r['regime']=='closed' and not r.get('reuse')]
    # Reused-arm Caffeine controls stay separate: select only ordinary-arm batches here.
    selected=[r for r in selected if not r['batch'].startswith('focused-reuse')]
    f=Figure('RQ2: payload and read contract change the crossover','Same 512 MiB heap, 32,768 entries and 32 MiB/s offered background allocation | exploratory pairs, no pooled histograms')
    xf,yf=f.panel(75,130,410,350,'256 B service p99.9: reverse crossover',444,484,0,4,[448,464,472,480],[0,1,2,3,4],'Application ballast (MiB)','microseconds')
    for i,b in enumerate(('CAFFEINE','CHRONICLE_IN_MEMORY')):f.series(xf,yf,points(selected,b,lambda r:r['latency']['service']['percentilesNs']['99.9']/1000),COLORS[b],b.replace('_IN_MEMORY',' get'),80,555+i*25)
    reuse=[r for r in observations if r['batch']=='focused-reuse-256-20261108-001' and r['regime']=='closed' and r.get('reuse')]
    f.series(xf,yf,[(480,[r['latency']['service']['percentilesNs']['99.9']/1000 for r in reuse],[bool(r['warnings']) for r in reuse])],COLORS['reuse'],'getUsing sensitivity',80,605)
    xf,yf=f.panel(590,130,360,350,'Observed worker allocation',0,7,1,10000,[],[1,10,100,1000,10000],'256 B (left) / 4 KiB (right)','bytes/operation (log)',True)
    for offset,payload in ((0,256),(4,4096)):
        groups=[('Caff',lambda r:r['backend']=='CAFFEINE' and not r['batch'].startswith('focused-reuse'),'#b91c1c'),
                ('get',lambda r:r['backend']=='CHRONICLE_IN_MEMORY' and not r.get('reuse'),'#0369a1'),
                ('reuse',lambda r:bool(r.get('reuse')),'#047857')]
        for j,(name,predicate,color) in enumerate(groups,1):
            values=[r['measurement']['workerBytesPerOperation'] for r in observations if r['payload']==payload and predicate(r)]
            x=offset+j;y=median(values);f.line(xf(x),yf(1),xf(x),yf(y),color,18);f.text(xf(x),yf(y)-10,f'{y:.1f}',12,'middle');f.text(xf(x),505,name,11,'middle')
    xf,yf=f.panel(1055,130,365,350,'4 KiB / 352 MiB response p99.9',0,5,10,100000,[],[10,100,1000,10000,100000],'Separate paired batches A / B','microseconds (log)',True)
    groups=[('Caff A','focused-rq1-4k-20261108-001','CAFFEINE',False),('get','focused-rq1-4k-20261108-001','CHRONICLE_IN_MEMORY',False),
        ('Caff B','focused-reuse-4k-20261108-001','CAFFEINE',False),('reuse','focused-reuse-4k-20261108-001','CHRONICLE_IN_MEMORY',True)]
    for index,(label,batch,backend,reused) in enumerate(groups,1):
        values=[r['latency']['response']['percentilesNs']['99.9']/1000 for r in bybatch[batch] if r['backend']==backend and r['regime']=='arrival' and r['liveMiB']==352]
        color=COLORS['reuse'] if reused else COLORS[backend];f.line(xf(index),yf(10),xf(index),yf(median(values)),color,22);f.line(xf(index),yf(min(values)),xf(index),yf(max(values)),'#172033',2)
        f.text(xf(index),yf(median(values))-12,f'{median(values):.0f}',12,'middle');f.text(xf(index),505,label,11,'middle')
    f.text(535,555,'getUsing reuses the caller buffer; fresh writes remain identical.',13)
    f.text(535,580,'Secondary borrowed-read contract; ordinary-get RQ1 remains separate.',12)
    f.text(535,605,'Response tails approach the pacing floor; no floor subtraction.',12)
    f.write('rq2_payload_and_reuse')


def main():
    if (OUT/'study.json').exists():raise ValueError('Retained report exists; no overwrite')
    observations,batches,audited=audit()
    save(OUT/'audit.json',audited)
    save(OUT/'warning-sensitivity.json',warning_sensitivity(observations))
    save(OUT/'study.json',dict(kind='focused-exploratory-rq-followup',complete=True,batches=batches,observations=observations,
        primaryContract='ordinary-get',secondaryContract='borrowed-getUsing-buffer',heapMiB=512,offeredArrivalQps=50000,replacements=0,
        answerRq1='No observed forward saturated-service crossover at4KiB through368MiB (~99.3% Caffeine heap). Actual scheduled-response p99.9 switches from Caffeine at0MiB to Chronicle at208MiB.',
        answerRq2='256B ordinary service p99.9 reverses from Chronicle lower at448MiB to Caffeine lower at480MiB; midpoints support a transition near the upper end. Reusing read buffers restores the Chronicle advantage at480MiB.',
        limits=['Three exploratory pairs per point; no confirmatory pooled p-value or invented CI.','Batches/access contracts/source-runtime groups remain identified.',
            'External/JIT warnings retained and sensitivity reported; no endpoint-based rejection.','No OOM occurred; the actual capacity limit is not established.']))
    flat=[]
    for r in observations:
        m=r['measurement'];g=r['gc'];flat.append(dict(batch=r['batch'],label=r['label'],payload=r['payload'],ballastMiB=r['liveMiB'],backend=r['backend'],
            accessMode=r.get('accessMode','get'),regime=r['regime'],block=r['block'],measureMs=r['measureMs'],operations=m['operations'],
            serviceP99Us=r['latency']['service']['percentilesNs']['99']/1000,serviceP999Us=r['latency']['service']['percentilesNs']['99.9']/1000,
            responseP99Us=(r['latency']['response']['percentilesNs']['99'] or 0)/1000,responseP999Us=(r['latency']['response']['percentilesNs']['99.9'] or 0)/1000,
            heapPct=g['postGcUsedHeapMedianFraction']*100,fullGcCount=g['fullGcCount'],gcPausePct=g['pauseExposureFraction']*100,
            workerBop=m['workerBytesPerOperation'],warnings=json.dumps(r['warnings'])))
    with (OUT/'forks.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,list(flat[0]));w.writeheader();w.writerows(flat)
    make_figures(observations)
    save(OUT/'report-source.json',dict(path=str(pathlib.Path(__file__).relative_to(ROOT)),sha256=sha(pathlib.Path(__file__))))
    print(json.dumps(audited,indent=2))

if __name__=='__main__':main()
