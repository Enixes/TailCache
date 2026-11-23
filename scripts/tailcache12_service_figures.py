#!/usr/bin/env python3
"""Render separate, per-fork scientific follow-up figures from the portable package."""
import hashlib,json,pathlib,subprocess,sys,os
os.environ.setdefault("MPLCONFIGDIR","/tmp/tailcache-mpl-config")
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import tailcache12_service_verify as verify

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/service-followup'
DATA=BASE/'followup-data-20261117.json'
C,H='#245f88','#bc5d27'
WARN='#a82935'


def main():
    data=json.loads(DATA.read_text());checks=verify.verify(data);curves=verify.decode(data)
    forks={r['id']:r for r in data['forks']};pairs=data['pairs'];out=BASE/'figures';out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
        'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18,'svg.hashsalt':'tailcache-service-20261117'})
    index=[]
    def save(fig,name,title,caption):
        fig.suptitle(title,fontsize=13,fontweight='bold');fig.tight_layout(rect=(0,0,1,.94))
        for ext in ('svg','png'):
            fig.savefig(out/(name+'.'+ext),dpi=180,metadata={'Date':None} if ext=='svg' else None)
        plt.close(fig);index.append(dict(id=name,title=title,caption=caption))
    def dot(ax,x,y,color,pair,marker='o'):
        ax.scatter(x,y,s=48,marker=marker,c=color,edgecolors=WARN if not pair['warningFree'] else 'white',
                   linewidths=1.6,zorder=3)
    def ratio_axis(ax):
        ax.axhline(1,color='#374151',ls='--',lw=1);ax.set_yscale('log',base=2)
        ax.set_ylabel('Chronicle / Caffeine p99.9');ax.set_yticks([.5,1,2,4],['0.5','1','2','4'])
    fig,axes=plt.subplots(1,2,figsize=(10.5,4.3),sharey=True)
    for ax,live in zip(axes,(0,208)):
        for cohort,color,marker in [('replication',C,'o'),('observer',H,'s')]:
            chosen=[p for p in pairs if p['cohort']==cohort and p['liveMiB']==live and
                    (cohort=='observer' or p['stage']=='payload-confirmation')]
            for p in chosen:
                offset=(p['block']-2)*.025 if cohort=='replication' else (p['block']-1.5)*.035
                dot(ax,p['payload']*2**offset,p['ratios']['service']['99.9'],color,p,marker)
        ax.set_xscale('log',base=2);ax.set_xticks([512,1024,2048,4096],['512 B','1 KiB','2 KiB','4 KiB'])
        ratio_axis(ax);ax.set_title(f'{live} MiB common ballast');ax.set_xlabel('Value payload')
    axes[0].legend(handles=[Line2D([],[],ls='',marker='o',color=C,label='Every-operation recorder (3 pairs)'),
        Line2D([],[],ls='',marker='s',color=H,label='JMH sample regime (2 pairs)')],fontsize=8)
    save(fig,'a1-harness-payload','Service ranking depends on the harness regime',
         'Every dot is one paired JVM comparison; horizontal jitter separates repeats. Red outlines retain recorded warnings. No percentiles are pooled. JMH changes caller/sampling/iteration/reset/consumption and uses eight one-second measurement iterations, versus a contiguous 30 seconds for the custom recorder; this is not an isolated timer intervention.')
    fig,axes=plt.subplots(1,2,figsize=(10.5,4.2),sharey=True)
    modes=['CAFFEINE','CAFFEINE_BOUNDED_DIRECT','CAFFEINE_UNBOUNDED']
    for ax,payload in zip(axes,(512,4096)):
        for p in pairs:
            if p['cohort']=='policy' and p['payload']==payload:
                dot(ax,modes.index(p['referenceBackend'])+(p['block']-1.5)*.07,p['ratio'] if 'ratio' in p else p['ratios']['service']['99.9'],C,p)
        ratio_axis(ax);ax.set_xticks(range(3),['Bounded\ndefault executor','Bounded\ndirect executor','Unbounded'])
        ax.set_title(f'{payload} B, zero ballast')
    save(fig,'a2-cache-policy','The small-value service advantage changes with cache policy',
         'Two paired repetitions per configuration. The three contrasts within a block share the same Chronicle anchor and are dependent. Unbounded Caffeine changes capacity policy, metadata and layout; it does not replace the bounded main comparison or isolate heap placement. Red outlines show retained warnings.')
    fig,axes=plt.subplots(1,2,figsize=(10.8,4.7),sharey=True)
    settings=[('trace',['trace-40001','trace-1000003'],['40,001 slots','1,000,003 slots'],'Trace-length comparison'),
              ('geometry',['geometry-repeated-short','geometry-uniform-long'],['Repeated-short\nin long arrays','Uniform-long'],'Equal-array control')]
    for ax,(cohort,stages,labels,title) in zip(axes,settings):
        for p in pairs:
            if p['cohort']!=cohort:continue
            x=stages.index(p['stage'])
            for key,color,offset in [('c',C,-.12),('h',H,.12)]:
                dot(ax,x+offset+(p['block']-1.5)*.045,forks[p[key]]['latency']['response']['percentilesNs']['99.9']/1000,color,p)
        ax.set_yscale('log');ax.set_ylim(10,16000);ax.set_xticks(range(2),labels);ax.set_title(title)
        ax.set_ylabel('Scheduled-response p99.9 (µs)')
    axes[0].legend(handles=[Line2D([],[],ls='',marker='o',color=C,label='Caffeine'),
        Line2D([],[],ls='',marker='o',color=H,label='Chronicle')])
    save(fig,'a3-trace-response','The baseline response reversal persists with equal trace-array geometry',
         'Each treatment has two fresh paired forks, 4 KiB values, zero ballast, 50,000 intended arrivals/s and 60/4/30-second phases. In the right panel both patterns retain identical long/boolean array lengths, with 10 Caffeine/9 Chronicle max humongous regions. Updated keys are 1,939 versus 25,532. The logical pattern still changes active read keys, ordering and lifetime together. Red outlines show any warning in the pair; both uniform-control pairs and one repeated-control pair are warning-free.')
    fig,axes=plt.subplots(1,2,figsize=(10.5,4.5))
    for r in data['forks']:
        if r['cohort']!='replication' or r['payload']!=4096 or r['stage']=='payload-holdout':continue
        x=r['liveMiB']+(r['block']-2)*1.6 if r['stage']=='payload-confirmation' else r['liveMiB']
        color=C if r['backend']=='CAFFEINE' else H
        axes[0].scatter(x,100*r['gc']['pauseExposureFraction'],c=color,s=32)
        value=100*r['mechanism']['largeGcAffectedCallFraction']
        if value:axes[1].scatter(x,value,c=color,s=32)
    axes[0].set_ylabel('GC-pause share of measured wall time (%)')
    axes[1].set_yscale('log');axes[1].set_ylabel('Calls intersecting ≥1 ms GC intervals (%)')
    for threshold,label in [(.1,'p99.9 tail = 0.1%'),(.01,'p99.99 tail = 0.01%'),(.001,'p99.999 tail = 0.001%')]:
        axes[1].axhline(threshold,color='#6b7280',ls=':',lw=.8);axes[1].text(2,threshold*1.12,label,fontsize=8)
    axes[1].set_ylim(.0003,.2)
    for ax in axes:ax.set_xlabel('Common application ballast (MiB)')
    axes[0].legend(handles=[Line2D([],[],ls='',marker='o',color=C,label='Caffeine'),Line2D([],[],ls='',marker='o',color=H,label='Chronicle')])
    save(fig,'a4-gc-denominators','GC wall time and operation-tail probability use different denominators',
         'All displayed forks remain separate: three anchor pairs and single high-pressure discovery pairs. GC intersects few timed calls even when it consumes substantial wall time. The right panel counts service intervals intersecting GC intervals of at least 1 ms; it is not a count of independent stalls or proof that each whole call exceeds every shown latency threshold. At 336 MiB, all large-pause overlap in one Caffeine fork lies in 312 of 28,508,698 calls (0.0010944%), while GC occupies 39.36% wall time.')
    fig,axes=plt.subplots(1,2,figsize=(10.5,4.4))
    for ax,channel in zip(axes,('service','response')):
        for p in pairs:
            if p['cohort']=='paced':
                color=C if p['payload']==256 else H
                dot(ax,p['liveMiB']+(p['block']-1.5)*5,p['ratios'][channel]['99.9'],color,p)
        ax.set_yscale('log');ax.axhline(1,color='#374151',ls='--',lw=1)
        ax.set_xticks([0,208,336]);ax.set_xlabel('Common ballast (MiB)');ax.set_title('Paced '+channel)
        ax.set_ylabel('Chronicle / Caffeine p99.9')
    axes[0].legend(handles=[Line2D([],[],ls='',marker='o',color=C,label='256 B'),Line2D([],[],ls='',marker='o',color=H,label='4 KiB')],loc='lower center',bbox_to_anchor=(.5,1.12),ncol=2)
    save(fig,'a5-paced-payload','Matched-arrival service and response answer different questions',
         'Two paired forks per payload/pressure, same long trace and 50,000 intended arrivals/s. Every phase completes its intended operations, with matched paired write counts. These are paced service durations, not saturated-service replacements. Response favors Chronicle already at baseline in this workload. All JIT, host and dropped-demand warnings remain visible as red outlines.')
    fig,ax=plt.subplots(figsize=(7.3,4.3))
    for p in pairs:
        if p['cohort']=='largePilot':
            for key,color,offset in [('c',C,-7),('h',H,7)]:
                dot(ax,p['liveMiB']+offset,forks[p[key]]['latency']['service']['percentilesNs']['99.9']/1000,color,p)
    ax.set_xticks([0,208]);ax.set_xlabel('Common ballast (MiB)');ax.set_ylabel('Service p99.9 (µs)')
    ax.legend(handles=[Line2D([],[],ls='',marker='o',color=C,label='Caffeine'),Line2D([],[],ls='',marker='o',color=H,label='Chronicle')])
    save(fig,'a6-larger-payload','The 8 KiB pilot did not justify a larger campaign',
         'One discovery pair per point with a ten-second measurement, 12/2-second preparation and 32,768 residents. Chronicle/Caffeine service p99.9 ratios are 1.1047 and 1.1711; pressure does not improve the ratio. The predeclared worth rule stops after four workload JVMs, with no confirmation or post hoc switch to a rarer primary endpoint. Red outlines retain endogenous dropped-churn warnings.')
    fig,ax=plt.subplots(figsize=(8.5,4.8))
    selected=[r for r in data['forks'] if r['cohort']=='replication' and r['stage']=='pressure-discovery' and
              r['payload']==4096 and r['liveMiB']==336]
    for r in selected:
        bins=curves[r['id']]['service'];total=sum(n for _,n in bins);remaining=total;xs=[];ys=[]
        for value,count in bins:
            remaining-=count
            if remaining:xs.append(value/1000);ys.append(remaining/total)
        color=C if r['backend']=='CAFFEINE' else H
        ax.step(xs,ys,where='post',color=color,label=('Caffeine' if color==C else 'Chronicle')+f' · N={total:,}')
    for y,label in [(1e-3,'p99.9'),(1e-4,'p99.99'),(1e-5,'p99.999')]:
        ax.axhline(y,color='#6b7280',ls=':',lw=.8);ax.text(.13,y*1.15,label,fontsize=8)
    ax.set_xscale('log');ax.set_yscale('log');ax.set_xlabel('Service time (µs)');ax.set_ylabel('Empirical P(service > HDR upper-bin boundary)')
    ax.legend(fontsize=8)
    save(fig,'a7-full-service-tail','A full service tail reveals what a single percentile omits',
         'One 4 KiB/336 MiB discovery pair, not a confirmed crossover threshold. Full retained positive-survival bins are plotted without smoothing or pooling; the terminal zero cannot be drawn on the log axis. Caffeine p99.9/p99.99 are 8.367/19.887 µs, while p99.999 reaches 35.783 ms; Chronicle p99.999 is 1.465 ms. Finite sample resolution and correlated stall episodes constrain inference; zero observations do not establish zero risk.')
    (BASE/'figure-index-20261117.json').write_text(json.dumps(index,indent=2)+'\n')
    captions=['# Follow-up scientific figures','', 'Per-fork observations and descriptive contrasts; no pooled percentiles or confidence-interval claims. A red outline indicates a recorded warning in either arm of that pair, not necessarily the marked backend.','']
    for i,f in enumerate(index,1):captions += [f"## Figure A{i}. {f['title']}",'',f"![{f['title']}](figures/{f['id']}.png)",'',f['caption'],'']
    (BASE/'FIGURES_20261117.md').write_text('\n'.join(captions))
    freeze=subprocess.run([sys.executable,'-m','pip','freeze'],capture_output=True,text=True,check=True)
    (BASE/'render-requirements-20261117.txt').write_text(freeze.stdout)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    manifest=dict(passed=True,packageSha256=sha(DATA),sourceSha256=sha(pathlib.Path(__file__)),portableChecks=checks,
        matplotlib=matplotlib.__version__,outputs={str(p.relative_to(BASE)):sha(p) for p in sorted(out.glob('*')) if p.is_file()})
    (BASE/'render-manifest-20261117.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(passed=True,figures=len(index),outputs=len(manifest['outputs']))))


if __name__=='__main__':main()
