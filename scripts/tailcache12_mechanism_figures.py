#!/usr/bin/env python3
"""Scientific mechanism figures: separate paired outcomes, no pooled quantiles."""
import argparse,hashlib,json,math,os,pathlib
import tailcache12_mechanism_report as checks
os.environ.setdefault('MPLCONFIGDIR','/tmp/tailcache-mechanism-mpl')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
ROOT=pathlib.Path(__file__).resolve().parents[1];BASE=ROOT/'docs/mechanism';OUT=BASE/'figures';C,H,W='#246387','#b85a29','#ad3044'
def main():
 global OUT
 parser=argparse.ArgumentParser();parser.add_argument('--out',type=pathlib.Path);args=parser.parse_args()
 if args.out:OUT=args.out/'figures';OUT.parent.mkdir(parents=True,exist_ok=True)
 d=json.loads((BASE/'mechanism-data-20261118.json').read_text());checks.verify(d);fs={r['id']:r for r in d['forks']};cohorts=[c for c in ('logging','priming','hotset-screen','hotset-repeat','transition','headroom-screen','headroom-confirm','payload') if any(p['cohort']==c for p in d['pairs'])];OUT.mkdir(exist_ok=True);idx=[]
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18,'svg.hashsalt':'tailcache-mechanism-20261118'})
 def save(fig,id,title,caption):
  fig.suptitle(title,fontsize=14,fontweight='bold');fig.tight_layout(rect=(0,0,1,.94))
  for ext in ('png','svg'):fig.savefig(OUT/(id+'.'+ext),dpi=180,metadata={'Date':None} if ext=='svg' else None)
  plt.close(fig);idx.append(dict(id=id,title=title,caption=caption))
 def short(r,c):
  if c=='logging':return r['logging']
  if c=='priming':return 'prime '+str(r['primeCalls'])
  if c.startswith('hotset'):return str(r['hotset'])+' keys'
  if c.startswith('headroom'):return str(r['heapMiB'])+'MiB / '+str(r['writeBps']/100)+'%'
  if c=='payload':return str(r['payload'])+'B / '+str(r['writeBps']/100)+'%'
  return '90 s window'
 for q,id in [('99.9','c1-mechanism-response'),('99.999','c2-mechanism-extreme')]:
  fig,axes=plt.subplots(math.ceil(len(cohorts)/2),2,figsize=(12,3.2*math.ceil(len(cohorts)/2)),squeeze=False)
  for ax,c in zip(axes.flat,cohorts):
   ps=[p for p in d['pairs'] if p['cohort']==c]
   for i,p in enumerate(ps):
    a,b=fs[p['c']],fs[p['h']];ax.scatter(i,p['ratios']['response'][q],s=45,c=C,edgecolor=W if a['warnings'] or b['warnings'] else 'white',linewidth=1.5,zorder=3)
   ax.axhline(1,ls='--',lw=1,c='#566a78');ax.set_yscale('log');ax.set_xticks(range(len(ps)),[short(fs[p['c']],c)+'\n'+str(fs[p['c']]['seed'])+' / r'+str(fs[p['c']]['repeat']) for p in ps],rotation=16,fontsize=7);ax.set_title(c+' · '+d['cohorts'][c]['role']);ax.set_ylabel('Ch/C response p'+q)
  for ax in list(axes.flat)[len(cohorts):]:ax.axis('off')
  save(fig,id,'Matched interventions and separate paired outcomes · p'+q,'Each dot is one retained paired fork; below1 favors Chronicle, above1 Caffeine. Red outlines retain warnings. Each panel uses different interventions; no quantile pooling, fitted crossing or confidence interval. Development logging/priming are separate from transport tests. Repeated hotset seeds are not fresh confirmation. Extreme-tail observations can share stalls;90-second transition measurements remain separate from30-second cohorts.')
 hold=[r for r in d['forks'] if r['cohort'] not in ('logging','priming') and not r['predictionOutsideCalibration']]
 fig,axes=plt.subplots(1,3,figsize=(12,4.5))
 for ax,method in zip(axes,('M2','M3total','constant')):
  vals=[v/1000 for r in hold for v in (r['latency']['response']['percentilesNs']['99.9'],r['predictionNs'][method]['99.9'])];lo=min(vals)/1.4;hi=max(vals)*1.4;ax.plot([lo,hi],[lo,hi],ls='--',c='#566a78')
  for r in hold:ax.scatter(r['latency']['response']['percentilesNs']['99.9']/1000,r['predictionNs'][method]['99.9']/1000,s=25,c=C if r['backend']=='CAFFEINE' else H,edgecolor=W if r['warnings'] else 'white',linewidth=1)
  ax.set(xscale='log',yscale='log',xlim=(lo,hi),ylim=(lo,hi),xlabel='Measured response p99.9 (µs)',ylabel='Predicted (µs)',title=method)
 axes[0].legend(handles=[Line2D([],[],ls='',marker='o',color=C,label='Caffeine'),Line2D([],[],ls='',marker='o',color=H,label='Chronicle')],fontsize=8)
 save(fig,'c3-conditional-transport','Frozen conditional models still have numerical transport error','All calibrated4KiB forks after logging/priming development are shown, including warnings and collector failures. The fixed GC-only and broader-safepoint FIFO reconstructions use observed pauses; the constant pilot baseline does not. No parameters are fitted here. Contrasts across multiple interventions are descriptive; per-cohort/per-backend numerical summaries remain authoritative. M3core is also retained/scored in the portable package; showing M3total is not an after-data model selection.')
 target=OUT.parent
 (target/'figure-index-20261118.json').write_text(json.dumps(idx,indent=2)+'\n');manifest=dict(inputSha256=hashlib.sha256((BASE/'mechanism-data-20261118.json').read_bytes()).hexdigest(),rendererSha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),matplotlibVersion=matplotlib.__version__,outputs={str(p.relative_to(target)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.suffix in ('.png','.svg')});(target/'render-manifest-20261118.json').write_text(json.dumps(manifest,indent=2)+'\n');(target/'FIGURES.md').write_text('# Mechanism figures\n\n'+'\n\n'.join(f"**Figure C{i}. {r['title']}.** {r['caption']}\n\n![{r['title']}](figures/{r['id']}.png)" for i,r in enumerate(idx,1))+'\n');print('MECHANISM_FIGURES_COMPLETE',len(idx))
if __name__=='__main__':main()
