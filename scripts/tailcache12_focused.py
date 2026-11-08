#!/usr/bin/env python3
"""Task12 focused resumable crossover batches; pressure outcomes are retained."""
import argparse,collections,csv,datetime,hashlib,json,math,os,pathlib,random,shutil,statistics,subprocess,tarfile,threading,time
import tailcache12 as evidence
from tailcache12_analysis import parse_gc,gc_summary

VERSION='focused-crossover-v1'
JAVA='/usr/lib/jvm/java-21-openjdk/bin/java'
MAIN='io.github.enixes.tailcache.workload.FocusedCrossoverRunner'
FLAGS=['-Dchronicle.analytics.disable=true',
 '--add-exports=java.base/jdk.internal.misc=ALL-UNNAMED','--add-exports=java.base/jdk.internal.ref=ALL-UNNAMED',
 '--add-exports=java.base/jdk.internal.util=ALL-UNNAMED','--add-exports=java.base/sun.nio.ch=ALL-UNNAMED',
 '--add-exports=jdk.compiler/com.sun.tools.javac.file=ALL-UNNAMED','--add-exports=jdk.unsupported/sun.misc=ALL-UNNAMED',
 '--add-opens=java.base/java.io=ALL-UNNAMED','--add-opens=java.base/java.lang=ALL-UNNAMED',
 '--add-opens=java.base/java.lang.reflect=ALL-UNNAMED','--add-opens=java.base/java.util=ALL-UNNAMED',
 '--add-opens=jdk.compiler/com.sun.tools.javac=ALL-UNNAMED']

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def load(p):return json.loads(p.read_text())
def save(p,v):
    tmp=p.with_suffix(p.suffix+'.pending');tmp.write_text(json.dumps(v,indent=2)+'\n');tmp.replace(p)
def rows(p):
    with p.open() as f:return list(csv.DictReader(f))
def properties(p):return dict(line.split('=',1) for line in p.read_text().splitlines() if '=' in line)
def sha(p):return evidence.file_sha(p)


def schedule(payload,levels,passes,regimes,reuse=False):
    result=[]
    for block in range(1,passes+1):
        cells=[(live,regime) for live in levels for regime in regimes]
        random.Random(24301+block).shuffle(cells)
        for index,(live,regime) in enumerate(cells):
            backends=evidence.BACKENDS if (block+index)%2 else tuple(reversed(evidence.BACKENDS))
            for backend in backends:
                using=reuse and backend=='CHRONICLE_IN_MEMORY'
                result.append(dict(label=f'b{block}-{regime}-p{payload}-live{live}-{backend}'+('-getUsing' if using else ''),backend=backend,payload=payload,
                    liveMiB=live,block=block,regime=regime,qps=50000 if regime=='arrival' else 0,reuse=using,accessMode='getUsing' if using else 'get'))
    return result


def rank(path,percentile):
    values=[(int(r['upperEquivalentNs']),int(r['count'])) for r in rows(path)];total=sum(n for v,n in values)
    if not total:return None
    # Pinned HDR2.2.2: nextAfter(percentile,-infinity), then ceiling rank.
    target=max(1,math.ceil(math.nextafter(percentile,-math.inf)*total/100.0));n=0
    for value,count in values:
        n+=count
        if n>=target:return value
    raise ValueError('Histogram rank missing')


def read_fork(path,spec,exit_code,timeout=False):
    result=dict(spec,status='TIMEOUT' if timeout else 'ERROR',exitCode=exit_code,warnings=[],latencyVerified=False)
    worker=path/'worker';window_file=worker/'windows.csv';failure=worker/'failure.txt'
    if failure.exists():result['failure']=properties(failure)
    stderr=(path/'stderr.txt').read_text(errors='replace') if (path/'stderr.txt').exists() else ''
    if 'OutOfMemoryError' in stderr or 'OutOfMemoryError' in str(result.get('failure')):
        result['status']='OOM_'+result.get('failure',{}).get('phase','UNKNOWN')
    if window_file.exists():
        windows=rows(window_file);measured=next((r for r in windows if r['phase']=='MEASUREMENT'),None)
        result['windows']=windows
        if measured:
            start,end=int(measured['startNs']),int(measured['endNs']);operations=int(measured['operations'])
            result['measurement']=dict(startNs=start,endNs=end,offeredEndNs=int(measured['offeredEndNs']),operations=operations,
                scheduled=int(measured['scheduled']),compilerMs=int(measured['compilerMs']),workerBytesPerOperation=int(measured['workerAllocatedBytes'])/operations,
                churnPayloadBytes=int(measured['churnPayloadBytes']),churnDroppedBytes=int(measured['churnDroppedBytes']),
                maxBacklog=int(measured['maxBacklog']),unexportedStallEvents=int(measured['unexportedStallEvents']))
            result['latency']={}
            for channel in ('service','gap','response'):
                bins=worker/(channel+'-bins.csv');summary=rows(worker/(channel+'-summary.csv'))[0]
                count=sum(int(r['count']) for r in rows(bins));expected=operations if channel!='response' or spec['qps'] else 0
                if count!=expected or count!=int(summary['count']):raise ValueError('Histogram operation conservation failed')
                # Full bins retain p99.99 even in legacy runner files whose
                # short summary only printed p50/p99/p99.9.
                values={str(p):rank(bins,p) for p in (50,99,99.9,99.99)}
                for p,key in ((50,'p50Ns'),(99,'p99Ns'),(99.9,'p999Ns')):
                    if count and values[str(p)]!=int(summary[key]):raise ValueError('Raw percentile mismatch')
                result['latency'][channel]=dict(count=count,percentilesNs=values,maxNs=int(summary['maxNs']))
            # Ignore post-measurement verification GC, including an unfinished GC
            # after a killed verification. The complete original log is retained.
            selected=[]
            for line in (path/'gc.log').read_text().splitlines():
                stamp=evidence.re.search(r'\[(-?\d+)ns\]',line)
                if stamp and int(stamp[1])<=end:selected.append(line)
            prefix=path/'gc-through-measurement.log';prefix.write_text('\n'.join(selected)+'\n')
            gc=parse_gc(prefix);full=gc_summary(gc,[(start,end)],operations)
            result['gc']={k:v for k,v in full.items() if k not in ('pauses','occupancySamples')}
            result['gc']['fullGcCount']=sum('Pause Full' in p['kind'] for p in full['pauses'])
            result['gc']['measuredEvacuationFailures']=full['evacuationFailureCount']
            save(path/'measured-gc.json',dict(pauses=full['pauses'],occupancySamples=full['occupancySamples']))
            completion=properties(worker/'completion.txt');result['completion']=completion
            verified=(worker/'integrity.txt').exists()
            if verified:
                integrity=properties(worker/'integrity.txt')
                if int(integrity['residentCount'])!=spec.get('residents',32768):raise ValueError('Resident count changed')
                if spec.get('residents',32768)==32768 and int(integrity['operations'])!=sum(int(r['operations']) for r in windows):
                    raise ValueError('Workload operation totals do not reconcile')
                config=properties(worker/'configuration.txt')
                if spec.get('reuse') and config.get('readContract')!='borrowed-getUsing-buffer':
                    raise ValueError('getUsing access contract missing')
            result['latencyVerified']=verified
            if exit_code==0 and verified:result['status']=completion['status']
            if int(measured['compilerMs'])>80:result['warnings'].append('Measured compiler activity exceeds80ms; retain as short-run evidence')
            if int(measured['churnDroppedBytes']):result['warnings'].append('Allocation demand lost under stall; endogenous pressure outcome retained')
            if int(measured['scheduled']) and operations!=int(measured['scheduled']):result['warnings'].append('Incomplete scheduled arrivals; response tail censored')
    if (path/'host.csv').exists():
        host=[evidence.decode_host_row(r) for r in rows(path/'host.csv')]
        windows=None if 'measurement' not in result else [(result['measurement']['startNs'],result['measurement']['endNs'])]
        reasons,_=evidence.host_gate(host,cpu_windows=windows,native_required=True,native_version=2)
        result['warnings']+=reasons
        intervals=evidence.native_host.cpu_intervals(host)
        relevant=[r for r in intervals if windows is None or any(r['endNs']>=a and r['startNs']<=b for a,b in windows)]
        result['outsideCpuUpperPercent']=max((r['outsideUpperPercent'] for r in relevant),default=None)
        if result['outsideCpuUpperPercent'] is not None and result['outsideCpuUpperPercent']>25:
            result['warnings'].append('Outside CPU upper bound exceeds25%; externally noisy observation')
    result['rawSha256']={str(p.relative_to(path)):sha(p) for p in sorted(path.rglob('*')) if p.is_file() and p.name!='result.json'}
    return result


def launch(root,spec,classpath,warmup=8000,conditioning=2000,measure=8000,floor=False,inject=0):
    path=root/spec['label'];path.mkdir(exist_ok=False)
    cmd=[JAVA,*FLAGS,'-XX:+UseG1GC','-Xms512m','-Xmx512m',f'-Xlog:gc*,safepoint:file={path}/gc.log:uptimemillis,timenanos,level,tags:filecount=0',
        '-cp',classpath,MAIN,'--out',str(path/'worker'),'--backend',spec['backend'],'--payload',str(spec['payload']),
        '--live-mib',str(spec['liveMiB']),'--residents',str(spec.get('residents',32768)),
        '--churn-mib-sec',str(spec.get('churnMiB',32)),'--qps',str(spec['qps']),
        '--warmup-ms',str(warmup),'--conditioning-ms',str(conditioning),'--measure-ms',str(measure),
        '--floor',str(floor).lower(),'--inject-stall-ms',str(inject),'--reuse',str(spec.get('reuse',False)).lower()]
    save(path/'command.json',dict(command=cmd,startedUtc=now()))
    host=[evidence.host_snapshot()];finished=threading.Event();errors=[]
    def monitor():
        try:
            while not finished.wait(1):host.append(evidence.host_snapshot())
        except Exception as error:errors.append(str(error))
    observer=threading.Thread(target=monitor,daemon=True);observer.start();timedout=False
    try:
        with (path/'stdout.txt').open('x') as stdout,(path/'stderr.txt').open('x') as stderr:
            try:code=subprocess.run(cmd,stdout=stdout,stderr=stderr,timeout=75).returncode
            except subprocess.TimeoutExpired:timedout=True;code=None
    finally:
        finished.set();observer.join();host.append(evidence.host_snapshot())
        with (path/'host.csv').open('x',newline='') as f:
            w=csv.DictWriter(f,list(host[0]));w.writeheader();w.writerows(host)
    result=read_fork(path,spec,code,timedout);result['warnings']+=errors;save(path/'result.json',result)
    return result


def summaries(results):
    pairs=[]
    for payload,live,regime in sorted({(r['payload'],r['liveMiB'],r['regime']) for r in results}):
        chosen=[r for r in results if (r['payload'],r['liveMiB'],r['regime'])==(payload,live,regime)]
        row=dict(payload=payload,liveMiB=live,regime=regime,passes=[],ratios={},warnings=[])
        for block in sorted({r['block'] for r in chosen}):
            by={r['backend']:r for r in chosen if r['block']==block}
            if set(by)!=set(evidence.BACKENDS):continue
            good=all(r['status']=='OK' and r['latencyVerified'] for r in by.values())
            pair=dict(block=block,statuses={b:r['status'] for b,r in by.items()},usable=good,
                warnings={b:r['warnings'] for b,r in by.items()},ratios={})
            if good:
                for channel in ('service','response') if regime=='arrival' else ('service',):
                    pair['ratios'][channel]={p:by['CHRONICLE_IN_MEMORY']['latency'][channel]['percentilesNs'][p]/by['CAFFEINE']['latency'][channel]['percentilesNs'][p] for p in ('99','99.9','99.99')}
            row['passes'].append(pair)
        for channel in ('service','response') if regime=='arrival' else ('service',):
            row['ratios'][channel]={}
            for percentile in ('99','99.9','99.99'):
                values=[p['ratios'][channel][percentile] for p in row['passes'] if p['usable']]
                row['ratios'][channel][percentile]=dict(pairedRatios=values,median=statistics.median(values) if values else None,
                    minimum=min(values,default=None),maximum=max(values,default=None),
                    direction='chronicle-lower' if values and max(values)<1 else 'caffeine-lower' if values and min(values)>1 else 'mixed-or-incomplete',confidenceInterval=None)
        pairs.append(row)
    return pairs


def run(args):
    out=evidence.ROOT/'evidence-archives'/args.attempt
    expected=schedule(args.payload,args.live,args.passes,args.regimes,args.reuse)
    classpath=(evidence.ROOT/'build/tmp/tailcache-focused-runtime.txt').read_text().strip()
    source=evidence.source_hash()
    if evidence.host_snapshot().get('nativeScopeQualified')!=1:raise ValueError('Require native exclusive scope')
    if out.exists():
        if not args.resume:raise ValueError('Attempt exists; use resume, never overwrite')
        protocol=load(out/'protocol.json')
        if (protocol['sourceSha256']!=source or protocol['schedule']!=expected or protocol['classpath']!=classpath
                or (protocol['warmupMs'],protocol['conditioningMs'],protocol['measureMs'])!=(args.warmup_ms,args.conditioning_ms,args.measure_ms)):
            raise ValueError('Changed frozen source/schedule/runtime')
    else:
        out.mkdir(parents=True);setup=out/'setup';setup.mkdir()
        runtime_files=[]
        for item in classpath.split(os.pathsep):
            p=pathlib.Path(item)
            runtime_files.extend([p] if p.is_file() else [q for q in p.rglob('*') if q.is_file()])
        protocol=dict(version=VERSION,declaredUtc=now(),sourceSha256=source,schedule=expected,classpath=classpath,
            warmupMs=args.warmup_ms,conditioningMs=args.conditioning_ms,measureMs=args.measure_ms,budgetSeconds=args.budget_seconds,replacements=0,
            estimands=['closed-loop service','scheduled-arrival response including queue debt'],
            runtimeSha256={str(p):sha(p) for p in runtime_files},heapMiB=512,churnMiBPerSecond=32,exploratory=True)
        save(out/'protocol.json',protocol)
        with tarfile.open(out/'source.tar.gz','x:gz') as archive:
            for p in evidence.sources():archive.add(p,arcname=str(p.relative_to(evidence.ROOT)))
        shutil.copyfile(evidence.ROOT/'docs/TAILCACHE_FOCUSED_REDO.md',out/'plan.md')
        note=pathlib.Path('/home/y/.gemini/antigravity-cli/brain/813eaaaa-7714-484f-8709-5826310287c3/tailcache12_review.md')
        if note.exists():shutil.copyfile(note,out/'agy-discovery-review.md')
    for file,wanted in protocol['runtimeSha256'].items():
        if sha(pathlib.Path(file))!=wanted:raise ValueError('Changed compiled runtime')
    controls=out/'controls';controls.mkdir(exist_ok=True)
    control_specs=[dict(label='floor-'+regime,backend='CAFFEINE',payload=256,liveMiB=0,block=0,regime=regime,qps=qps,residents=64,churnMiB=0)
                   for regime,qps in (('closed',0),('arrival',50000))]
    control_specs += [dict(control_specs[1],label='scheduled-stall')]
    for spec in control_specs:
        result_path=controls/spec['label']/'result.json'
        if result_path.exists():r=load(result_path)
        else:r=launch(controls,spec,classpath,warmup=0,conditioning=0,measure=1000,floor=True,inject=20 if spec['label']=='scheduled-stall' else 0)
        if r['status']!='OK' or not r['latencyVerified']:raise ValueError('Harness control failed: '+str(r))
        if spec['label']=='scheduled-stall':
            if r['latency']['response']['count']!=50000 or r['latency']['response']['percentilesNs']['99.9']<1_000_000:
                raise ValueError('Scheduled queue failed to expose injected stall')
    if args.controls_only:
        print('FOCUS_CONTROLS_COMPLETE '+str(out),flush=True);return
    started=time.monotonic();results=[]
    for index,spec in enumerate(expected):
        p=out/spec['label'];result_path=p/'result.json'
        if result_path.exists():
            r=load(result_path)
            for name,wanted in r['rawSha256'].items():
                if sha(p/name)!=wanted:raise ValueError('Retained evidence changed')
            results.append(r);continue
        if time.monotonic()-started>=args.budget_seconds:break
        if evidence.source_hash()!=source:raise ValueError('Source changed; preserve completed slots')
        if shutil.disk_usage(out).free<512*1024**2:break
        if p.exists():
            # No repeated slot: recover an interrupted collection as an explicit outcome.
            r=read_fork(p,spec,None,timeout=True);r['status']='INTERRUPTED';save(result_path,r)
        else:
            time.sleep(3);r=launch(out,spec,classpath,warmup=args.warmup_ms,conditioning=args.conditioning_ms,measure=args.measure_ms)
        results.append(r);save(out/'progress.json',dict(completed=len(results),planned=len(expected),lastLabel=spec['label'],utc=now()))
        print('FOCUS_PROGRESS '+str(len(results))+'/'+str(len(expected))+' '+spec['label']+' '+r['status']+' warnings='+str(len(r['warnings'])),flush=True)
    report=dict(version=VERSION,completeCollection=len(results)==len(expected),collected=len(results),planned=len(expected),
        sourceUnchanged=evidence.source_hash()==source,results=results,comparisons=summaries(results),
        limits=['Exploratory focused batches; no artificial CI from a few pairs.','Warnings and pressure failures are retained, never grounds for discarding the whole batch.',
            'Service and scheduled-response outcomes are different estimands; no pooling with AGY or historical Task12 forks.'])
    if not report['sourceUnchanged']:raise ValueError('Source changed during collection')
    save(out/'summary.json',report)
    helper=out/'setup'
    subprocess.run(['/usr/lib/jvm/java-21-openjdk/bin/javac','-cp',classpath,'-d',str(helper),str(evidence.ROOT/'scripts/java/TailCacheFocusedHdrVerify.java')],check=True,capture_output=True,text=True)
    checked=subprocess.run([JAVA,'-Xmx64m','-cp',str(helper)+os.pathsep+classpath,'TailCacheFocusedHdrVerify',str(out)],check=True,capture_output=True,text=True)
    save(out/'hdr-verification.json',json.loads(checked.stdout))
    save(out/'inventory.json',[dict(path=str(p.relative_to(out)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='inventory.json'])
    print('FOCUS_BATCH_COMPLETE '+str(out)+' '+str(len(results))+'/'+str(len(expected)),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('attempt');p.add_argument('--payload',type=int,default=4096)
    p.add_argument('--live',type=int,nargs='+',default=[328,352]);p.add_argument('--passes',type=int,default=3)
    p.add_argument('--regimes',nargs='+',choices=['closed','arrival'],default=['closed','arrival']);p.add_argument('--budget-seconds',type=int,default=1200)
    p.add_argument('--reuse',action='store_true');p.add_argument('--warmup-ms',type=int,default=8000)
    p.add_argument('--conditioning-ms',type=int,default=2000);p.add_argument('--measure-ms',type=int,default=8000)
    p.add_argument('--resume',action='store_true');p.add_argument('--controls-only',action='store_true');args=p.parse_args()
    if not evidence.re.fullmatch('[A-Za-z0-9._-]+',args.attempt) or args.passes<1 or args.budget_seconds<1:p.error('Invalid batch')
    run(args)
if __name__=='__main__':main()
