#!/usr/bin/env python3
"""Bounded mechanism sequence with constrained order, frozen cohorts and no replacements."""
import argparse,collections,csv,datetime,hashlib,json,os,pathlib,random,shutil,statistics,subprocess,sys,time
import tailcache12_service_campaign as core
import tailcache12_focused as f
ROOT=core.ROOT;BUILD=ROOT/'build/mechanism-20261118';STATUS=ROOT/'docs/TAILCACHE_MECHANISM_STATUS.json'
MAIN='io.github.enixes.tailcache.workload.MechanismCrossoverRunner';OLD_SOURCES=core.source_files

def sources():return sorted(set(OLD_SOURCES()+[ROOT/'docs/TAILCACHE_MECHANISM_PLAN.md',ROOT/'docs/TAILCACHE_MECHANISM_FINISH_PLAN.md',ROOT/'docs/mechanism/model-v1.json',ROOT/'docs/predictor/model-v1.json',ROOT/'docs/predictor/drain-candidate-v1.json',ROOT/'docs/predictor/drain_candidate.py.txt',ROOT/'docs/predictor/numeric-baseline-v1.json']))
core.source_files=sources

def usable(r):return r.get('status')=='OK' and r.get('latencyVerified') and r.get('latency',{}).get('response',{}).get('count',0)>0
core.usable=usable

def pair(stage,seed,repeat,first,**settings):
 rows=core.pair_specs(stage,settings.pop('payload',4096),0,block=repeat,seed=seed,reverse=first=='CHRONICLE_IN_MEMORY')
 defaults=dict(regime='arrival',qps=50000,writeBps=500,hotset=32768,primeCalls=0,logging='sync',heapMiB=512,warmupMs=120000,conditioningMs=4000,measureMs=30000,repeat=repeat);defaults.update(settings)
 for r in rows:r.update(defaults)
 return rows

def schedule(kind,logging='sync',prime=0,confirmation=False):
 seeds={'logging':[54801,54802],'priming':[54811,54812],'hotset':[54821,54822],'transition':[54831,54832],'headroom':[54842] if confirmation else [54841],'payload':[54851]}[kind]
 variants={'logging':[dict(logging=x,writeBps=50) for x in ('sync','async')],
  'priming':[dict(primeCalls=x,writeBps=50,jit=True) for x in (0,4)],'hotset':[dict(hotset=x) for x in (2048,32768)],
  'transition':[dict(writeBps=50,measureMs=90000)],'headroom':[dict(heapMiB=h,writeBps=w) for h in (512,1024) for w in (50,500)],
  'payload':[dict(payload=p,writeBps=w) for p in (256,4096) for w in (0,500)]}[kind]
 repeats=[2] if kind=='hotset' and confirmation else [1,2] if kind=='transition' else [1]
 cells=[(i,seed,rep,v) for rep in repeats for i,seed in enumerate(seeds) for v in variants]
 random.Random(54800+sum(map(ord,kind))+(100 if confirmation else 0)).shuffle(cells);rows=[]
 for i,seed,rep,v in cells:
  # Same order within seed across treatments; repeated forks reverse it.
  first='CAFFEINE' if (i+rep+(1 if confirmation and kind=='headroom' else 0))%2 else 'CHRONICLE_IN_MEMORY'
  tag=kind+('-confirm' if confirmation else '')+'-'+ '-'.join(str(k)+str(val) for k,val in sorted(v.items()))
  settings=dict(logging=logging,primeCalls=prime);settings.update(v)
  rows+=pair(tag,seed,rep,first,**settings)
 validate_schedule(rows);return rows

def validate_schedule(rows):
 core.check(len({r['label'] for r in rows})==len(rows),'Unique slots')
 for a,b in zip(rows[::2],rows[1::2]):
  core.check({a['backend'],b['backend']}==set(core.BACKENDS),'Paired backends')
  core.check(all(a[k]==b[k] for k in a if k not in ('backend','label')),'Matched settings')
 grouped=collections.defaultdict(list)
 for i in range(0,len(rows),2):
  r=rows[i];key=tuple((k,r[k]) for k in ('stage','payload','writeBps','hotset','primeCalls','logging','heapMiB','measureMs'));grouped[key].append(r['backend'])
 for arms in grouped.values():
  if len(arms)%2==0:core.check(arms.count('CAFFEINE')==arms.count('CHRONICLE_IN_MEMORY'),'Per-treatment backend order balance')
 return True

def jdk_identity():
 base=pathlib.Path(f.JAVA).resolve().parents[1]
 return {str(p):f.sha(p) for p in (base/'release',base/'bin/java',base/'lib/server/libjvm.so',base/'lib/modules')}

def build():
 BUILD.mkdir(parents=True,exist_ok=True);receipt=BUILD/'compilation.json'
 if receipt.exists():qualify();return
 classes=BUILD/'classes';classes.mkdir(exist_ok=False)
 deps=[p for p in (ROOT/'build/predictor-20261118/classpath.txt').read_text().strip().split(':') if pathlib.Path(p).is_file() and p.endswith('.jar')]
 files=sorted((ROOT/'src/main/java').rglob('*.java'))+[ROOT/'scripts/java/MechanismSelfTest.java',ROOT/'scripts/java/MechanismStreamAudit.java',ROOT/'scripts/java/TailCacheFocusedHdrVerify.java']
 cmd=['/usr/lib/jvm/java-21-openjdk/bin/javac','-cp',':'.join(deps),'-d',str(classes),*map(str,files)]
 r=subprocess.run(cmd,capture_output=True,text=True);core.check(r.returncode==0,r.stderr)
 cp=str(classes)+':'+':'.join(deps);(BUILD/'classpath.txt').write_text(cp+'\n')
 old=f.load(ROOT/'build/predictor-20261118/compilation.json');legacy={name:f.sha(BUILD/name)==h for name,h in old['compiledRuntime'].items() if any(x in name for x in ('/workload/PredictorCrossoverRunner','/workload/PredictorWorkload','/workload/PredictorStream'))}
 core.check(all(legacy.values()),'Legacy measured classes changed')
 value=dict(passed=True,command=cmd,sourceSha256={str(p.relative_to(ROOT)):f.sha(p) for p in files},compiledRuntime={str(p.relative_to(BUILD)):f.sha(p) for p in sorted(classes.rglob('*.class'))},jdkSha256=jdk_identity(),legacyMeasuredClassesUnchanged=legacy)
 core.immutable(receipt,value)
 ran=subprocess.run([f.JAVA,*f.FLAGS,'-Xmx256m','-cp',cp,'io.github.enixes.tailcache.workload.MechanismSelfTest'],capture_output=True,text=True)
 core.check(ran.returncode==0,ran.stderr);q=json.loads(ran.stdout.strip().splitlines()[-1]);q.update(mode='mechanism',compilationSha256=f.sha(receipt),functionalJvms=1);core.immutable(BUILD/'functional-validation.json',q)
 print('MECHANISM_BUILD_FUNCTIONAL_COMPLETE',flush=True)

def qualify():
 c=f.load(BUILD/'compilation.json');q=f.load(BUILD/'functional-validation.json');core.check(c['passed'] and q['passed'] and q['compilationSha256']==f.sha(BUILD/'compilation.json'),'Functional binding')
 for file,h in c['sourceSha256'].items():core.check(f.sha(ROOT/file)==h,'Compiled source changed '+file)
 for file,h in c['compiledRuntime'].items():core.check(f.sha(BUILD/file)==h,'Compiled classes changed')
 core.check(jdk_identity()==c['jdkSha256'],'JDK changed')

# Dedicated launcher changes only explicit JVM settings; old launchers remain frozen.

evidence=f.evidence;JAVA=f.JAVA;FLAGS=f.FLAGS;save=f.save;process_memory=f.process_memory;read_fork=f.read_fork;now=f.now;MEMORY_FIELDS=f.MEMORY_FIELDS
import threading
def launch(root,spec,classpath,warmup=8000,conditioning=2000,measure=8000,floor=False,inject=0,
           runner=None,extra_args=(),timeout_seconds=75):
    path=root/spec['label'];path.mkdir(exist_ok=False)
    heap=spec.get('heapMiB',512)
    extra_flags=[f'-Xlog:gc+age=trace:file={path}/age.log:uptimemillis,timenanos,level,tags:filecount=0','-XX:AsyncLogBufferSize=2097152']
    if spec.get('logging')=='async':extra_flags.append('-Xlog:async')
    if spec.get('jit'):extra_flags.append(f'-Xlog:jit+compilation=debug:file={path}/jit.log:uptimemillis,timenanos,level,tags:filecount=0')
    cmd=[JAVA,*FLAGS,'-XX:+UseG1GC',f'-Xms{heap}m',f'-Xmx{heap}m',f'-Xlog:gc*,safepoint:file={path}/gc.log:uptimemillis,timenanos,level,tags:filecount=0',*extra_flags,
        '-cp',classpath,runner or MAIN,'--out',str(path/'worker'),'--backend',spec['backend'],'--payload',str(spec['payload']),
        '--live-mib',str(spec['liveMiB']),'--residents',str(spec.get('residents',32768)),
        '--churn-mib-sec',str(spec.get('churnMiB',32)),'--qps',str(spec['qps']),
        '--seed',str(spec.get('seed',24301)),
        '--warmup-ms',str(warmup),'--conditioning-ms',str(conditioning),'--measure-ms',str(measure),
        '--floor',str(floor).lower(),'--inject-stall-ms',str(inject),'--reuse',str(spec.get('reuse',False)).lower(),*extra_args]
    save(path/'command.json',dict(command=cmd,startedUtc=now()))
    host=[evidence.host_snapshot()];finished=threading.Event();errors=[];memory=[];process=None
    def monitor():
        try:
            while not finished.wait(1):
                host.append(evidence.host_snapshot())
                sample=process_memory(process.pid,path/'worker/phase.txt')
                if sample is not None:memory.append(sample)
        except Exception as error:errors.append(str(error))
    observer=None;timedout=False
    try:
        with (path/'stdout.txt').open('x') as stdout,(path/'stderr.txt').open('x') as stderr:
            process=subprocess.Popen(cmd,stdout=stdout,stderr=stderr)
            group=pathlib.Path(f'/proc/{process.pid}/cgroup').read_text()
            save(path/'worker-process.json',dict(pid=process.pid,cgroup=group,observedNs=time.monotonic_ns()))
            if host[0].get('nativeScopeQualified')==1 and evidence.native_host.process_cgroup(group)!=host[0]['nativeCgroup']:
                process.kill();process.wait();raise ValueError('Worker escaped declared native scope')
            observer=threading.Thread(target=monitor,daemon=True);observer.start()
            try:code=process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timedout=True;process.kill();process.wait();code=None
    finally:
        if process is not None and process.poll() is None:
            process.kill();process.wait()
        finished.set()
        if observer is not None:observer.join()
        host.append(evidence.host_snapshot())
        with (path/'host.csv').open('x',newline='') as f:
            w=csv.DictWriter(f,list(host[0]));w.writeheader();w.writerows(host)
        with (path/'process-memory.csv').open('x',newline='') as f:
            w=csv.DictWriter(f,MEMORY_FIELDS);w.writeheader();w.writerows(memory)
    result=read_fork(path,spec,code,timedout);result['warnings']+=errors;save(path/'result.json',result)
    return result



def extend(path,r):
 if not usable(r):return r
 r=json.loads(json.dumps(r));windows=r['windows'];m=next(w for w in windows if w['phase']=='MEASUREMENT');n=int(m['operations']);writes=int(m['writes'])
 for channel,count in [('read-service',n-writes),('update-service',writes)]:
  bins=path/'worker'/(channel+'-bins.csv');values=core.bins(bins);core.check(sum(values.values())==count,'Conditional counts');summary=f.rows(path/'worker'/(channel+'-summary.csv'))[0]
  r['latency'][channel]=dict(count=count,maxNs=int(summary['maxNs']),percentilesNs={q:f.rank(bins,float(q)) for q in core.PERCENTILES})
 union=collections.Counter(core.bins(path/'worker/read-service-bins.csv'));union.update(core.bins(path/'worker/update-service-bins.csv'));core.check(dict(union)==core.bins(path/'worker/service-bins.csv'),'Per-bin union')
 config=f.properties(path/'worker/configuration.txt');core.check(int(config['maxHeapBytes'])==r.get('heapMiB',512)*1024**2,'Actual heap capacity');core.check(int(config['updateHotset'])==r.get('hotset',32768),'Actual update set')
 core.check(int(config['primeCalls'])==r.get('primeCalls',0),'Actual priming');core.check(config['streamPhaseReset']==config['streamWrap']=='false','Continuous stream')
 r['trace']={k:v for k,v in config.items() if k.startswith(('trace','stream','updateHotset'))}
 prev=0
 for w in windows:
  phase=w['phase'];duration=1000 if phase.startswith('PRIME') else r['warmupMs']-1000*r.get('primeCalls',0) if phase=='WARMUP' else r['conditioningMs'] if phase=='CONDITIONING' else r['measureMs']
  core.check(int(w['scheduled'])==int(w['operations'])==duration*r['qps']//1000,'Actual all-phase timing')
  pos=f.properties(path/'worker'/('stream-'+phase+'.txt'));core.check(int(pos['start'])==prev,'Phase cursor')
  core.check(r.get('floor') or int(pos['end'])-prev==int(w['operations']),'Phase work count');prev=int(pos['end'])
 expected=['PRIME'+str(i) for i in range(r.get('primeCalls',0))]+['WARMUP','CONDITIONING','MEASUREMENT'];core.check([w['phase'] for w in windows]==expected,'Declared phase coverage')
 texts=[p.read_text(errors='replace') for p in path.iterdir() if p.suffix in ('.txt','.log')]
 drops=[line for text in texts for line in text.splitlines() if any(x in line.lower() for x in ('discarded','dropped')) and any(x in line.lower() for x in ('log','messages'))]
 r['logComplete']=not drops;r['droppedLogMessages']=drops
 if drops:r['warnings'].append('Dropped logging messages; no GC-conditioned reconstruction')
 r['measurement']['writes']=writes;seconds=(int(m['endNs'])-int(m['startNs']))/1e9;r['measurement'].update(operationsPerSecond=n/seconds,achievedChurnPayloadBytesPerSecond=int(m['churnPayloadBytes'])/seconds)
 return r

class Campaign(core.Campaign):
 def __init__(self,*args,**kw):
  super().__init__(*args,**kw)
  for name in ('compilation.json','runner-smoke-receipt.json'):core.immutable(self.out/'setup'/name,f.load(BUILD/name))
 def execute(self,specs,control=False):
  results=[];root=self.out/('controls' if control else 'slots');root.mkdir(exist_ok=True)
  for spec in specs:
   path=root/spec['label'];saved=path/'service-result.json'
   if saved.exists():r=f.load(saved);f.verify_retained(path,r);results.append(r);continue
   self.check_frozen();qualify();ready=f.evidence.host_snapshot()
   core.check(shutil.disk_usage(self.out).free>=512*1024**2,'Disk reserve; completed slots preserved');core.check(ready['memAvailableKiB']>=1024**2 and '=0' not in ready.get('externalPower',''),'RAM/power readiness')
   core.check(ready['swapInPages']==self.ready['swapInPages'] and ready['swapOutPages']==self.ready['swapOutPages'],'Paging changed; resume completed slots')
   if not control and spec not in self.state['scheduled']:core.check(len(self.state['scheduled'])<self.protocol['maxWorkloadJvms'],'JVM ceiling');self.state['scheduled'].append(spec);self.checkpoint()
   if path.exists():
    core.check((path/'result.json').exists(),'Unresolved interrupted slot retained: '+str(path));r=f.load(path/'result.json');f.verify_retained(path,r)
   else:
    time.sleep(3);r=launch(root,spec,self.cp,warmup=spec['warmupMs'],conditioning=spec['conditioningMs'],measure=spec['measureMs'],floor=spec.get('floor',False),inject=spec.get('inject',0),runner=MAIN,
     extra_args=('--write-bps',str(spec['writeBps']),'--update-hotset',str(spec.get('hotset',32768)),'--prime-calls',str(spec.get('primeCalls',0)),'--supply-floor',str(spec.get('supply',False)).lower()),timeout_seconds=(spec['warmupMs']+spec['conditioningMs']+spec['measureMs'])/1000+75)
   r=extend(path,r);core.immutable(saved,r);results.append(r);self.state.update(lastLabel=spec['label'],collectedWorkloadJvms=len(self.observations()),updatedUtc=f.now());self.checkpoint()
   print('MECHANISM_PROGRESS',self.out.name,len(self.observations()),spec['label'],r['status'],'warnings='+str(len(r['warnings'])),flush=True)
   core.check(usable(r),'Failed/censored fork retained; explicit adjudication required')
   if control and spec.get('inject'):core.check(r['latency']['service']['maxNs']>=15000000 and r['latency']['response']['percentilesNs']['99.9']>=1000000,'Injected pause visible')
  return results

def smoke():
 if (BUILD/'runner-smoke-receipt.json').exists():return
 cp=(BUILD/'classpath.txt').read_text().strip();out=BUILD/'runner-smokes';out.mkdir(exist_ok=True);results=[]
 for i,backend in enumerate(core.BACKENDS):
  spec=pair('smoke'+str(i),54800,1,backend,hotset=8 if i else 64,primeCalls=i,writeBps=500,warmupMs=1500,conditioningMs=100,measureMs=200,residents=64,churnMiB=0,logging='async' if i else 'sync')[0]
  path=out/spec['label']
  if (path/'service-result.json').exists():r=f.load(path/'service-result.json');f.verify_retained(path,r)
  else:r=extend(path,launch(out,spec,cp,warmup=1500,conditioning=100,measure=200,extra_args=('--write-bps','500','--update-hotset',str(spec['hotset']),'--prime-calls',str(i),'--supply-floor','false'),timeout_seconds=30));core.immutable(path/'service-result.json',r)
  core.check(usable(r) and r['logComplete'],'Runner smoke');results.append(r)
 core.immutable(BUILD/'runner-smoke-receipt.json',dict(passed=True,functionalJvms=2,researchObservations=0,observations=results))

def design(kind,rows,controls=0):
 inputs={str(p.relative_to(ROOT)):f.sha(p) for p in (BUILD/'compilation.json',BUILD/'functional-validation.json',BUILD/'runner-smoke-receipt.json',ROOT/'docs/mechanism/model-v1.json')}
 return dict(kind='mechanism-'+kind,maxWorkloadJvms=len(rows),controls=controls,functionalValidationJvms=0,sharedFunctionalValidationJvms=3,functionalReceiptReused=True,functionalValidationReceipt='build/mechanism-20261118/functional-validation.json',warmupMs=120000,conditioningMs=4000,measureMs=30000,perSlotTiming=True,primaryEndpoint='scheduled response p99.9; per-stage mechanism diagnostics',protocol='docs/TAILCACHE_MECHANISM_PLAN.md',discoveryInputs=inputs,schedule=rows)

def collect(kind,attempt,logging='sync',prime=0,confirmation=False):
 rows=schedule(kind,logging,prime,confirmation);out=ROOT/'evidence-archives'/attempt;camp=Campaign(out,design=design(kind,rows,4 if kind=='logging' else 0),classpath_file=BUILD/'classpath.txt')
 if kind=='logging':
  cs=[]
  for label,floor,supply,inject,bps in [('timer',True,False,0,500),('injected',True,False,20,500),('supply50',False,True,0,50),('supply500',False,True,0,500)]:
   r=pair('control-'+label,54800,0,'CAFFEINE',writeBps=bps,hotset=64,residents=64,churnMiB=0,floor=floor,supply=supply,inject=inject,warmupMs=12000,conditioningMs=4000,measureMs=4000)[0];cs.append(r)
  camp.execute(cs,True)
 camp.execute(rows);observations=camp.observations();ps=core.pairs(observations);by={r['label']:r for r in observations}
 for p in ps:
  c,h=[by[p['labels'][b]] for b in core.BACKENDS];core.check([(w['phase'],w['writes']) for w in c['windows']]==[(w['phase'],w['writes']) for w in h['windows']],'Paired phase writes')
  p['ratios']['response']={q:h['latency']['response']['percentilesNs'][q]/c['latency']['response']['percentilesNs'][q] for q in core.PERCENTILES}
  for k in ('writeBps','hotset','logging','primeCalls','heapMiB','measureMs','repeat'):p[k]=c[k]
 camp.check_frozen();qualify();core.immutable(out/'study.json',dict(kind='mechanism-'+kind,observations=observations,pairs=ps,collectionComplete=True,workloadJvms=len(observations),limits='Finite-window, balanced block design; warnings/failures retained; no pooled quantiles'))
 camp.state.update(complete=True,collectionComplete=True,completedUtc=f.now());camp.checkpoint()


def step(out,name,cmd,artifact):
 receipt=out/(name+'.json')
 if receipt.exists():
  r=f.load(receipt);core.check(artifact.exists() and f.sha(artifact)==r['artifactSha256'],'Retained postprocess changed');return
 index=1
 while (out/(name+'-'+str(index)+'.log')).exists():index+=1
 log=out/(name+'-'+str(index)+'.log')
 with log.open('x') as stream:r=subprocess.run([sys.executable,str(ROOT/'scripts'/cmd[0]),*cmd[1:]],stdout=stream,stderr=subprocess.STDOUT)
 core.check(r.returncode==0,'Postprocess failure retained: '+str(log));core.check(artifact.exists(),'Postprocess artifact absent');core.immutable(receipt,dict(command=cmd,exitCode=0,artifactSha256=f.sha(artifact)))

def postprocess(attempt):
 base=ROOT/'evidence-archives'/attempt;out=base/'postprocess';out.mkdir(exist_ok=True)
 for name,cmd,artifact in [('raw',['tailcache12_mechanism_audit.py','raw',attempt],base/'raw-audit.json'),('predict',['tailcache12_mechanism_audit.py','predict',attempt],base/'predictions-v1.json'),('score',['tailcache12_mechanism_audit.py','score',attempt],base/'score-v1.json')]:
  print('MECHANISM_AUDIT',attempt,name,flush=True);step(out,name,cmd,artifact)

def choose_logging(base):
 rows=f.load(base/'study.json')['observations'];audit=f.load(base/'raw-audit.json');events={r['label']:r for r in audit['eventDiagnostics']};metrics={}
 for b in core.BACKENDS:
  metrics[b]={}
  for m in ('sync','async'):
   values=[events[r['label']]['medianGcLinkedExcessNs'] for r in rows if r['backend']==b and r['logging']==m]
   metrics[b][m]=statistics.median(values) if values and all(v is not None for v in values) else None
 complete=all(r['logComplete'] for r in rows if r['logging']=='async');ratios=[v['async']/max(1,v['sync']) for v in metrics.values() if v['async'] is not None and v['sync'] is not None];chosen='async' if complete and len(ratios)==len(core.BACKENDS) and min(ratios)<=.9 and max(ratios)<=1.1 else 'sync'
 return dict(logging=chosen,asyncLogsComplete=complete,metrics=metrics,rule='At least10% median excess reduction for one backend, no>10% increase for other; no log drops')

def choose_priming(base):
 rows=f.load(base/'study.json')['observations'];counts={str(p):sum(r['measurement']['compilerMs']>80 for r in rows if r['primeCalls']==p) for p in (0,4)}
 return dict(primeCalls=4 if counts['0']-counts['4']>=2 else 0,compilerWarningCounts=counts,rule='At least two fewer>80ms warnings out of four backend/seed observations')

def hotset_worth(base):
 rows=f.load(base/'study.json')['observations'];tests=[]
 for seed in sorted({r['seed'] for r in rows}):
  by={(r['hotset'],r['backend']):r for r in rows if r['seed']==seed};a,b=[by[h,'CAFFEINE'] for h in (2048,32768)];ratios=[by[h,'CHRONICLE_IN_MEMORY']['latency']['response']['percentilesNs']['99.9']/by[h,'CAFFEINE']['latency']['response']['percentilesNs']['99.9'] for h in (2048,32768)]
  tests.append(dict(seed=seed,gcRatio=a['gc']['pauseExposureFraction']/max(1e-20,b['gc']['pauseExposureFraction']),winnerReversal=(ratios[0]<1)!=(ratios[1]<1)))
 return dict(expand=all(t['gcRatio']<=.8 for t in tests) or any(t['winnerReversal'] for t in tests),tests=tests,rule='Both seeds Caffeine GC overlap reduce>=20% or any seed ranking reversal')

def heap_worth(base):
 rows=f.load(base/'study.json')['observations'];tests=[]
 for w in (50,500):
  by={(r['heapMiB'],r['backend']):r for r in rows if r['writeBps']==w};ratios=[by[h,'CHRONICLE_IN_MEMORY']['latency']['response']['percentilesNs']['99.9']/by[h,'CAFFEINE']['latency']['response']['percentilesNs']['99.9'] for h in (512,1024)]
  tests.append(dict(writeBps=w,gcRatio=by[1024,'CAFFEINE']['gc']['pauseExposureFraction']/max(1e-20,by[512,'CAFFEINE']['gc']['pauseExposureFraction']),winnerReversal=(ratios[0]<1)!=(ratios[1]<1)))
 return dict(expand=all(t['gcRatio']<=.8 for t in tests) or any(t['winnerReversal'] for t in tests),tests=tests,rule='Any ranking reversal or both Caffeine cells GC exposure reduce>=20%')

def sequence():
 build();qualify();smoke();root=ROOT/'evidence-archives/mechanism-sequence-20261118-001';root.mkdir(exist_ok=True)
 def run(kind,logging='sync',prime=0,confirm=False):
  attempt='mechanism-'+({'hotset':'hotset-repeat' if confirm else 'hotset-screen','headroom':'headroom-confirm' if confirm else 'headroom-screen'}.get(kind,kind))+'-20261118-001'
  s=f.load(STATUS)
  deadline=datetime.datetime.fromisoformat(s['collectionDeadlineUtc'])
  existing=ROOT/'evidence-archives'/attempt
  if not (existing/'study.json').exists():
   estimate=sum((r['warmupMs']+r['conditioningMs']+r['measureMs'])/1000+15 for r in schedule(kind,logging,prime,confirm))+180
   core.check(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=estimate)<deadline,'Collection reserve reached; preserve completed cohorts and report remaining scope')
  s.update(phase=kind.upper()+'_RUNNING',running=dict(attempt=attempt),updatedUtc=f.now());f.save(STATUS,s)
  collect(kind,attempt,logging,prime,confirm);postprocess(attempt);return ROOT/'evidence-archives'/attempt
 def decision(name,compute):
  path=root/(name+'.json')
  if not path.exists():core.immutable(path,compute())
  return f.load(path)
 a=run('logging');log=decision('logging-choice',lambda:choose_logging(a))['logging']
 b=run('priming',log);prime=decision('priming-choice',lambda:choose_priming(b))['primeCalls']
 c=run('hotset',log,prime)
 if decision('hotset-worth',lambda:hotset_worth(c))['expand']:run('hotset',log,prime,True)
 run('transition',log,prime);h=run('headroom',log,prime)
 if decision('headroom-worth',lambda:heap_worth(h))['expand']:run('headroom',log,prime,True)
 run('payload',log,prime)
 s=f.load(STATUS);s.update(phase='COLLECTION_AUDITS_COMPLETE_REPORT_PENDING',running=None,selectedLogging=log,selectedPrimeCalls=prime,updatedUtc=f.now(),collectionComplete=True);f.save(STATUS,s);print('MECHANISM_SEQUENCE_COMPLETE',flush=True)

def fixture():
 qualify();smoke();attempt='mechanism-qualification-20261118-001';out=ROOT/'evidence-archives'/attempt
 camp=Campaign(out,design=design('qualification',[],2),classpath_file=BUILD/'classpath.txt')
 rows=[]
 for i,b in enumerate(core.BACKENDS):
  rows.append(pair('qualification'+str(i),54800,0,b,residents=64,hotset=8,heapMiB=512 if i==0 else 1024,primeCalls=i,logging='sync' if i==0 else 'async',writeBps=0 if i==0 else 500,churnMiB=0,warmupMs=2000,conditioningMs=1000,measureMs=2000)[0])
 camp.execute(rows,True);core.immutable(out/'study.json',dict(observations=[],pairs=[],collectionComplete=True,workloadJvms=0,qualificationControls=2));camp.state.update(complete=True,collectionComplete=True);camp.checkpoint()
 step(out,'qualification-raw',['tailcache12_mechanism_audit.py','raw',attempt],out/'raw-audit.json')
 print('MECHANISM_QUALIFICATION_COMPLETE',flush=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['build','smoke','fixture','sequence']);a=p.parse_args()
 if a.command=='build':build()
 elif a.command=='smoke':qualify();smoke()
 elif a.command=='fixture':fixture()
 else:sequence()
if __name__=='__main__':main()
