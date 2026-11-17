#!/usr/bin/env python3
"""Frozen, resumable continuous-stream predictor qualification/validation."""
import argparse,collections,hashlib,json,os,pathlib,random,shutil,subprocess,time
import tailcache12_service_campaign as core
import tailcache12_focused as focus
import tailcache12_pause_model as model

ROOT=core.ROOT;MAIN='io.github.enixes.tailcache.workload.PredictorCrossoverRunner'
STATUS=ROOT/'docs/TAILCACHE_PREDICTOR_STATUS.json'
OLD_SOURCE_FILES=core.source_files
def sources():return sorted(set(OLD_SOURCE_FILES()+[ROOT/'docs/TAILCACHE_PREDICTOR_PLAN.md',ROOT/'docs/predictor/model-v1.json',ROOT/'docs/predictor/development-inputs-v1.json']))
core.source_files=sources

def extend(path,r):
    if r['status']!='OK' or not r.get('latencyVerified'):return r
    r=json.loads(json.dumps(r));w=next(w for w in r['windows'] if w['phase']=='MEASUREMENT');n=int(w['operations']);writes=int(w['writes'])
    for channel,count in [('read-service',n-writes),('update-service',writes)]:
        bins=path/'worker'/(channel+'-bins.csv');values=core.bins(bins);core.check(sum(values.values())==count,'Conditional count')
        summary=focus.rows(bins.with_name(channel+'-summary.csv'))[0]
        r['latency'][channel]=dict(count=count,maxNs=int(summary['maxNs']),percentilesNs={q:focus.rank(bins,float(q)) for q in core.PERCENTILES})
    combined=core.bins(path/'worker/service-bins.csv');union=collections.Counter(core.bins(path/'worker/read-service-bins.csv'));union.update(core.bins(path/'worker/update-service-bins.csv'))
    core.check(dict(union)==combined,'Exact service union')
    config=focus.properties(path/'worker/configuration.txt')
    core.check(config['streamVersion']=='indexed-splitmix-v1' and config['streamPhaseReset']==config['streamWrap']=='false','Stream contract')
    core.check(config['traceOperations']==config['traceArrayPayloadBytes']=='0','No retained trace arrays')
    r['trace']={k:v for k,v in config.items() if k.startswith(('trace','stream'))}
    previous=0
    for window in r['windows']:
        p=focus.properties(path/'worker'/('stream-'+window['phase']+'.txt'))
        core.check(int(p['start'])==previous and int(p['writeBps'])==r['writeBps'],'Continuous phase cursor')
        previous=int(p['end']);core.check(r.get('floor') or previous-int(p['start'])==int(window['operations']),'Stream count')
        expected=(r['warmupMs'] if window['phase']=='WARMUP' else r['conditioningMs'] if window['phase']=='CONDITIONING' else r['measureMs'])*50
        core.check(int(window['scheduled'])==int(window['operations'])==expected,'All-phase conservation')
    r['measurement']['writes']=writes;seconds=(int(w['endNs'])-int(w['startNs']))/1e9
    r['measurement']['operationsPerSecond']=n/seconds;r['measurement']['achievedChurnPayloadBytesPerSecond']=int(w['churnPayloadBytes'])/seconds
    return r

def usable(r):return r.get('status')=='OK' and r.get('latencyVerified') and r.get('latency',{}).get('response',{}).get('count',0)>0
core.usable=usable

def schedule(stage,warm,blocks=1):
    writes=(0,50,500) if stage=='qualification' else (0,50,100,200,500)
    cells=[(w,b) for w in writes for b in range(1,blocks+1)];random.Random(34801+warm).shuffle(cells)
    result=[]
    for i,(w,b) in enumerate(cells):
        seed=34810+b if stage=='validation' else 34801
        pair=core.pair_specs(stage+'-w'+str(w)+'-warm'+str(warm),4096,0,block=b,seed=seed,reverse=bool((i+b)%2))
        for row in pair:row.update(writeBps=w,regime='arrival',qps=50000,warmupMs=warm,conditioningMs=4000,measureMs=30000)
        result+=pair
    return result

def qualification():
    base=ROOT/'build/predictor-20261118';c=focus.load(base/'compilation.json');q=focus.load(base/'functional-validation.json')
    core.check(c['passed'] and q['passed'] and q['mode']=='predictor' and q['compilationSha256']==focus.sha(base/'compilation.json'),'Qualification binding')
    for f,h in c['sourceSha256'].items():core.check(focus.sha(ROOT/f)==h,'Compiled source changed '+f)
    for f,h in c['compiledRuntime'].items():core.check(focus.sha(base/f)==h,'Compiled class changed '+f)

class Campaign(core.Campaign):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for name in ('compilation.json','runner-smoke-receipt.json','timed-loop-review.json'):
            core.immutable(self.out/'setup'/name,focus.load(ROOT/'build/predictor-20261118'/name))

    def execute(self,specs,control=False):
        results=[];root=self.out/('controls' if control else 'slots');root.mkdir(exist_ok=True)
        for spec in specs:
            path=root/spec['label'];saved=path/'service-result.json'
            if saved.exists():r=focus.load(saved);focus.verify_retained(path,r);results.append(r);continue
            self.check_frozen();ready=focus.evidence.host_snapshot()
            core.check(shutil.disk_usage(self.out).free>=512*1024**2,'Disk readiness; preserve slots')
            core.check(ready['memAvailableKiB']>=1024**2 and '=0' not in ready.get('externalPower',''),'RAM/power readiness')
            core.check(ready['swapInPages']==self.ready['swapInPages'] and ready['swapOutPages']==self.ready['swapOutPages'],'Paging changed')
            if not control and spec not in self.state['scheduled']:
                core.check(len(self.state['scheduled'])<self.protocol['maxWorkloadJvms'],'Budget');self.state['scheduled'].append(spec);self.checkpoint()
            if path.exists():
                core.check((path/'result.json').exists(),'Unresolved interrupted slot; retain/adjudicate '+str(path));r=focus.load(path/'result.json');focus.verify_retained(path,r)
            else:
                time.sleep(3)
                saved_flags=focus.FLAGS
                try:
                    focus.FLAGS=[*saved_flags,f'-Xlog:gc+age=trace:file={path}/age.log:uptimemillis,timenanos,level,tags:filecount=0']
                    r=focus.launch(root,spec,self.cp,warmup=spec['warmupMs'],conditioning=spec['conditioningMs'],measure=spec['measureMs'],
                        floor=spec.get('floor',False),inject=spec.get('inject',0),runner=MAIN,
                        extra_args=('--write-bps',str(spec['writeBps']),'--supply-floor',str(spec.get('supply',False)).lower()),
                        timeout_seconds=(spec['warmupMs']+spec['conditioningMs']+spec['measureMs'])/1000+60)
                finally:focus.FLAGS=saved_flags
            r=extend(path,r);core.immutable(saved,r);results.append(r)
            if control:
                core.check(usable(r),'Control failed')
                if spec.get('inject'):core.check(r['latency']['service']['maxNs']>=15000000 and r['latency']['response']['percentilesNs']['99.9']>=1000000,'Injected-pause observability')
            self.state.update(lastLabel=spec['label'],collectedWorkloadJvms=len(self.observations()),updatedUtc=focus.now());self.checkpoint()
            print('PREDICTOR_PROGRESS',len(self.observations()),spec['label'],r['status'],'warnings='+str(len(r['warnings'])),flush=True)
            core.check(usable(r),'Failed/censored fork retained; stop for adjudication')
        return results

    def controls(self):
        for label,floor,supply,inject,bps in [('timer',True,False,0,500),('injected',True,False,20,500),('supply50',False,True,0,50),('supply500',False,True,0,500)]:
            row=core.pair_specs('predictor-control-'+label,4096,0,block=0)[0]
            row.update(writeBps=bps,regime='arrival',qps=50000,residents=64,churnMiB=0,floor=floor,supply=supply,inject=inject,
                       warmupMs=12000,conditioningMs=4000,measureMs=4000)
            self.execute([row],control=True)

    def stability(self,warm):
        diagnostics=[];extend=False
        from tailcache12_analysis import parse_gc,gc_summary
        for r in self.observations():
            if r['warmupMs']!=warm:continue
            w=r['measurement'];a,b=w['startNs'],w['endNs'];mid=(a+b)//2
            gc=parse_gc(self.out/'slots'/r['label']/'gc-through-measurement.log')
            halves=[gc_summary(gc,[(x,y)],1)['postGcUsedHeapMedianFraction'] for x,y in ((a,mid),(mid,b))]
            shift=abs(halves[1]-halves[0]) if all(v is not None for v in halves) else None
            evolving=(shift is not None and shift>.05) or w['compilerMs']>80
            extend|=evolving;diagnostics.append(dict(label=r['label'],postGcHalfMedians=halves,shift=shift,compilerMs=w['compilerMs'],evolving=evolving,warnings=r['warnings']))
        return dict(warmupMs=warm,needsLonger=extend,diagnostics=diagnostics,limits='Half-window occupancy/compiler diagnostic, not proof of steady state.')

    def run(self,stage):
        if stage=='qualification':
            self.controls()
            self.execute(self.protocol['design']['warm12']);self.execute(self.protocol['design']['warm60'])
            d=self.stability(60000);self.decision('stability60',d)
            if d['needsLonger']:
                self.execute(self.protocol['design']['warm120']);last=self.stability(120000);self.decision('stability120',last)
                choice=dict(warmupMs=120000,transient=last['needsLonger'])
            else:choice=dict(warmupMs=60000,transient=False)
            choice.update(proceed=True,reason='Functional/accounting checks pass; positive or contrary forecasts both informative.',modelSha256=focus.sha(ROOT/'docs/predictor/model-v1.json'))
            self.decision('validation-choice',choice)
        else:self.execute(self.protocol['design']['schedule'])
        rows=self.observations();ps=core.pairs(rows)
        by={r['label']:r for r in rows}
        for p in ps:
            c,h=[by[p['labels'][b]] for b in core.BACKENDS]
            core.check([(w['phase'],w['writes']) for w in c['windows']]==[(w['phase'],w['writes']) for w in h['windows']],'Paired logical writes')
            p['ratios']['response']={q:h['latency']['response']['percentilesNs'][q]/c['latency']['response']['percentilesNs'][q] for q in core.PERCENTILES}
            p['writeBps']=c['writeBps'];p['warmupMs']=c['warmupMs']
        self.check_frozen();core.immutable(self.out/'study.json',dict(kind='predictor-'+stage,collectionComplete=True,observations=rows,pairs=ps,
            workloadJvms=len(rows),primary='scheduled-response p99.9',limits='Separate qualification/validation; model conditioned on GC is not an ex ante forecast.'))
        self.state.update(complete=True,collectionComplete=True,researchComplete=False,completedUtc=focus.now());self.checkpoint()
        print('PREDICTOR_COLLECTION_COMPLETE',stage,len(rows),flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['qualification','validation']);parser.add_argument('attempt');parser.add_argument('--qualification-attempt');args=parser.parse_args()
    core.check(focus.evidence.re.fullmatch('[A-Za-z0-9._-]+',args.attempt),'Attempt');qualification()
    base=ROOT/'build/predictor-20261118';inputs={str(p.relative_to(ROOT)):focus.sha(p) for p in [base/'compilation.json',base/'functional-validation.json',base/'runner-smoke-receipt.json',base/'timed-loop-review.json',ROOT/'docs/predictor/model-v1.json',ROOT/'docs/predictor/development-inputs-v1.json']}
    design=dict(kind='predictor-'+args.stage,maxWorkloadJvms=18 if args.stage=='qualification' else 30,
        controls=4 if args.stage=='qualification' else 0,functionalValidationJvms=3 if args.stage=='qualification' else 0,functionalReceiptReused=args.stage=='validation',functionalValidationReceipt=str((base/'functional-validation.json').relative_to(ROOT)),
        warmupMs=60000,conditioningMs=4000,measureMs=30000,perSlotTiming=True,primaryEndpoint='scheduled response p99.9',
        protocol='docs/TAILCACHE_PREDICTOR_PLAN.md',discoveryInputs=inputs)
    if args.stage=='qualification':design.update(warm12=schedule(args.stage,12000),warm60=schedule(args.stage,60000),warm120=schedule(args.stage,120000))
    else:
        core.check(args.qualification_attempt is not None,'Qualification study required');q=ROOT/'evidence-archives'/args.qualification_attempt
        choice=focus.load(q/'validation-choice.json');core.check(focus.load(q/'independent-audit-001/audit.json')['passed'],'Qualification raw audit')
        inputs.update({str(p.relative_to(ROOT)):focus.sha(p) for p in [q/'study.json',q/'validation-choice.json',q/'independent-audit-001/audit.json']})
        core.check(choice['proceed'],'Worth gate');design.update(warmupMs=choice['warmupMs'],schedule=schedule('validation',choice['warmupMs'],3),transient=choice['transient'])
    s=focus.load(STATUS);s.update(phase=args.stage.upper()+'_RUNNING',running=dict(attempt=args.attempt),updatedUtc=focus.now());focus.save(STATUS,s)
    Campaign(ROOT/'evidence-archives'/args.attempt,design=design,classpath_file=base/'classpath.txt').run(args.stage)

if __name__=='__main__':main()
