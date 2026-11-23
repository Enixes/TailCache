#!/usr/bin/env python3
"""Scientific figures from the independently verified portable predictor package."""
import hashlib,json,os,pathlib
os.environ.setdefault('MPLCONFIGDIR','/tmp/tailcache-predictor-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import tailcache12_predictor_verify as verify
ROOT=pathlib.Path(__file__).resolve().parents[1];BASE=ROOT/'docs/predictor';DATA=BASE/'predictor-data-20261118.json'
C,H,W='#245f88','#bc5d27','#a82935'
def main():
 d=json.loads(DATA.read_text());verify.verify(d);fs={r['id']:r for r in d['forks']};out=BASE/'figures';out.mkdir(exist_ok=True);idx=[]
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18,'svg.hashsalt':'tailcache-predictor-20261118'})
 def save(fig,name,title,caption):
  fig.suptitle(title,fontsize=13,fontweight='bold');fig.tight_layout(rect=(0,0,1,.94))
  for ext in ('svg','png'):fig.savefig(out/(name+'.'+ext),dpi=180,metadata={'Date':None} if ext=='svg' else None)
  plt.close(fig);idx.append(dict(id=name,title=title,caption=caption))
 levels=[0,50,100,200,500]
 def x(w):return levels.index(w)
 def points(ax,cohort,q):
  ps=[p for p in d['pairs'] if p['cohort']==cohort]
  for p in ps:ax.scatter(x(p['writeBps'])+(p['block']-2)*.06,p['ratios']['response'][q],s=48,c=C,edgecolor=W if not p['warningFree'] else 'white',linewidth=1.6,zorder=3)
  ax.axhline(1,color='#374151',ls='--',lw=1);ax.set_yscale('log');ax.set_xticks(range(5),['0','0.5','1','2','5']);ax.set_xlabel('Writes (%), categorical spacing');ax.set_ylabel(f'Chronicle / Caffeine response p{q}')
 fig,axes=plt.subplots(1,2,figsize=(10.8,4.4),sharey=True)
 for ax,cohort,title in zip(axes,('validation','confirmation'),('Original holdout: 3 pairs / point','Fresh secondary: 2 pairs / point')):
  points(ax,cohort,'99.9');ax.set_title(title);ax.axvspan(0,1,color='#e5eff6',zorder=0);ax.text(.5,.96,'Untested interval',ha='center',va='top',transform=ax.get_xaxis_transform(),fontsize=8)
 save(fig,'b1-write-rate-reversal','Response endpoints repeat; the 0.5% boundary does not',
  'Every dot is one complete paired comparison, with red outlines for any recorded warning; no percentiles are pooled. Shading marks the primary observed0–0.5% bracket. Fresh0.5% pairs disagree; only0%/5% endpoint directions repeat. Shading is not a confidence bound or exact threshold. The original before-run0.5–2% bracket forecast failed. Fresh secondary repetitions are plotted separately. All observations retain transient qualification; categorical spacing avoids implying a fitted response curve.')
 fig,axes=plt.subplots(2,3,figsize=(12.2,7.5))
 for row,cohort in zip(axes,('validation','confirmation')):
  for ax,method in zip(row,('M1','M2','constant')):
   rs=[r for r in fs.values() if r['cohort']==cohort]
   values=[v/1000 for r in rs for v in (r['latency']['response']['percentilesNs']['99.9'],r['predictionNs'][method]['99.9'])];lo=min(values)/1.4;hi=max(values)*1.4
   ax.plot([lo,hi],[lo,hi],ls='--',c='#486078',lw=1)
   for r in rs:ax.scatter(r['latency']['response']['percentilesNs']['99.9']/1000,r['predictionNs'][method]['99.9']/1000,s=30,c=C if r['backend']=='CAFFEINE' else H,edgecolors=W if r['warnings'] else 'white',linewidth=1.2)
   ax.set_xscale('log');ax.set_yscale('log');ax.set_xlim(lo,hi);ax.set_ylim(lo,hi);ax.set_title(cohort+' · '+method);ax.set_xlabel('Measured response p99.9 (µs)');ax.set_ylabel('Predicted (µs)')
 axes[0,0].legend(handles=[Line2D([],[],ls='',marker='o',color=C,label='Caffeine'),Line2D([],[],ls='',marker='o',color=H,label='Chronicle')],fontsize=8,loc='upper left')
 save(fig,'b2-conditional-prediction','Conditional numerical accuracy remains limited near the tail boundary',
  'M1 and M2 use this run\'s observed GC intervals, not an ex ante GC forecast. M2 and the additional constant-quantile baseline use pilot calibration; the constant comparator was specified after primary outcomes, before fresh confirmation. Diagonal indicates exact agreement. Every fork, including warnings, is shown; blue Caffeine/orange Chronicle. No below-threshold outcome is excluded.')
 fig,axes=plt.subplots(1,2,figsize=(10.8,4.4))
 for ax,cohort in zip(axes,('validation','confirmation')):
  for r in fs.values():
   if r['cohort']!=cohort:continue
   offset=(-.13 if r['backend']=='CAFFEINE' else .13)+(r['block']-2)*.035
   ax.scatter(x(r['writeBps'])+offset,r['totalGcPauseOverlapNs']/1e6,c=C if r['backend']=='CAFFEINE' else H,s=40,edgecolor=W if r['warnings'] else 'white',linewidth=1.4)
  ax.axhline(30,ls='--',c='#486078',lw=1,label='Pause-only p99.9 budget (30 ms)');ax.set_xticks(range(5),['0','0.5','1','2','5']);ax.set_xlabel('Writes (%), categorical spacing');ax.set_ylabel('GC-pause overlap in offered window (ms)');ax.set_title(cohort)
 axes[0].legend(handles=[Line2D([],[],ls='',marker='o',color=C,label='Caffeine'),Line2D([],[],ls='',marker='o',color=H,label='Chronicle'),Line2D([],[],ls='--',color='#486078',label='Pause-only p99.9 budget (30 ms)')],fontsize=8)
 save(fig,'b3-pause-budget','Write rate changes GC pause exposure under fixed arrival demand',
  'Pause-only budget is0.1% of the30-second window. It determines whether ideal residual pause delay can exceed zero, not a complete latency value or universal transition. Chronicle response can exceed a baseline even with pause sum below this line because queue drain, baseline work and non-GC stalls remain. Paired library configurations differ in more than value placement. All forks and warnings remain included.')
 fig,axes=plt.subplots(1,2,figsize=(10.8,4.4),sharey=True)
 for ax,q in zip(axes,('99.99','99.999')):points(ax,'validation',q);ax.set_title('Primary holdout · p'+q)
 save(fig,'b4-extreme-tails','Extreme response tails favor Chronicle already at zero writes',
  'All15 primary pairs are shown separately at each percentile. This is an already-present extreme-tail advantage, not a newly pressure-induced crossing. p99.999 has about15 nominal observations in the upper tail per1.5-million-response fork; several can share a stall. The same forks contribute both panels, so these are dependent endpoints. Secondary holdout results remain available in the data/table and explorer.')
 (BASE/'figure-index-20261118.json').write_text(json.dumps(idx,indent=2)+'\n')
 files=[p for p in out.iterdir() if p.suffix in ('.svg','.png')]
 manifest={'inputSha256':hashlib.sha256(DATA.read_bytes()).hexdigest(),'rendererSha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'matplotlibVersion':matplotlib.__version__,'outputs':{str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}}
 (BASE/'render-manifest-20261118.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (BASE/'FIGURES.md').write_text('# Continuous-stream prediction study figures\n\n'+ '\n\n'.join(f"**Figure B{i}. {r['title']}.** {r['caption']}\n\n![{r['title']}](figures/{r['id']}.png)" for i,r in enumerate(idx,1))+'\n')
 print(json.dumps({'figures':len(idx),'outputs':len(files),'inputSha256':manifest['inputSha256']}))
if __name__=='__main__':main()
