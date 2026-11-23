#!/usr/bin/env python3
"""Fixed independent JMH service-harness sensitivity; no pooled observer claims."""
import argparse
import collections
import csv
import json
import math
import os
import pathlib
import random
import shutil
import subprocess
import threading
import time

import tailcache12_service_campaign as core
import tailcache12_focused as focus

ROOT=core.ROOT
BENCH='io.github.enixes.tailcache.observer.ServiceObserverBenchmark.'


def schedule():
    slots=[]
    for block in (1,2):
        cells=[(p,b) for p in (512,1024,4096) for b in (0,208)]
        random.Random(24340+block).shuffle(cells)
        for i,(payload,live) in enumerate(cells):
            for backend in core.BACKENDS[::-1] if (i+block)%2 else core.BACKENDS:
                slots.append(dict(label=f'jmh-p{payload}-live{live}-b{block}-{backend}',
                                  backend=backend,payload=payload,liveMiB=live,block=block,seed=24301,
                                  stage='jmh-observer',regime='JMH-SampleTime',qps=0))
    return slots


def rank(values,percentile):
    total=sum(values.values());target=max(1,math.ceil(math.nextafter(percentile,-math.inf)*total/100))
    cumulative=0
    for value,count in sorted(values.items()):
        cumulative+=count
        if cumulative>=target:return value
    raise ValueError('No sampled observations')


def sample_distribution(histogram, operations):
    counts=collections.Counter()
    for value,count in histogram:
        core.check(math.isfinite(value) and float(value).is_integer() and value>=0
                   and int(count)==count and count>0,'Raw JMH bin')
        counts[int(value)]+=int(count)
    core.check(0<sum(counts.values())<=operations,'JMH sample/operation conservation')
    return counts


def derive(path,spec,code):
    result=dict(spec,status='ERROR',exitCode=code,warnings=[],latencyVerified=False)
    worker=path/'worker'
    if code==0 and (path/'results.json').exists() and (worker/'integrity.txt').exists():
        info=focus.properties(worker/'configuration.txt')
        identity=focus.properties(worker/'worker.properties')
        windows=focus.rows(worker/'windows.csv');measured=[r for r in windows if r['phase']=='MEASUREMENT']
        expected=spec.get('iterations',3 if spec.get('floor') else 8)
        core.check(len(measured)==expected,'JMH measured window count')
        body=focus.load(path/'results.json')
        core.check(len(body)==1 and body[0]['primaryMetric']['scoreUnit']=='ns/op','JMH result identity/units')
        item=body[0]
        core.check(item['benchmark']==BENCH+('timerFloor' if spec.get('floor') else 'cacheAccess') and item['mode']=='sample' and item['threads']==item['forks']==1,'JMH benchmark/fork/mode identity')
        core.check(item['params']==dict(backend=spec['backend'],payload=str(spec['payload']),ballastMiB=str(spec['liveMiB'])),'JMH parameter identity')
        core.check(info['backend']==spec['backend'] and int(info['payload'])==spec['payload'] and int(info['ballastMiB'])==spec['liveMiB'],'Actual workload configuration')
        core.check(info['traceOperations']=='1000003' and info['traceWriteOperations']=='50000' and info['heapMaxBytes']==str(512*1024**2),'Actual trace/heap contract')
        sampled=body[0]['primaryMetric']['rawDataHistogram']
        core.check(len(sampled)==1 and len(sampled[0])==len(measured),'JMH histogram coverage')
        combined=collections.Counter();per_iteration=[]
        for histogram,w in zip(sampled[0],measured):
            counts=sample_distribution(histogram,int(w['operations']))
            n=sum(counts.values())
            combined.update(counts);per_iteration.append(n)
        n=sum(combined.values());operations=sum(int(w['operations']) for w in measured)
        writes=sum(int(w['writes']) for w in measured)
        seconds=sum((int(w['endNs'])-int(w['startNs']))/1e9 for w in measured)
        allocation=sum(int(w['workerAllocatedBytes']) for w in measured)
        compiler=sum(int(w['compilerMs']) for w in measured)
        demand=sum(int(w['churnPayloadBytes']) for w in measured)
        dropped=sum(int(w['churnDroppedBytes']) for w in measured)
        mandatory=0 if spec.get('floor') else (operations if spec['backend']=='CHRONICLE_IN_MEMORY' else writes)*spec['payload']
        if allocation<mandatory:result['warnings'].append('Physical allocation below full materialization/fresh-write payload floor')
        if compiler>80:result['warnings'].append('Measured compiler activity exceeds80ms; retain as harness sensitivity')
        if dropped:result['warnings'].append('Allocation demand lost under stall; endogenous pressure outcome retained')
        windows_ns=[(int(w['startNs']),int(w['endNs'])) for w in measured]
        gc_files=list(path.glob('gc-*.log'));core.check(len(gc_files)==1,'Actual fork GC log coverage')
        gc=focus.gc_summary(focus.parse_gc(gc_files[0]),windows_ns,operations)
        gc={k:v for k,v in gc.items() if k not in ('pauses','occupancySamples')}
        host=[focus.evidence.decode_host_row(r) for r in focus.rows(path/'host.csv')]
        reasons,_=focus.evidence.host_gate(host,cpu_windows=windows_ns,native_required=True,native_version=2)
        result['warnings']+=reasons
        core.check({focus.evidence.native_host.process_cgroup(identity['cgroup'])}=={h['nativeCgroup'] for h in host},
                   'Actual JMH workload escaped native accounting scope')
        memory=focus.rows(path/'process-memory.csv')
        selected=[r for r in memory if r['VmRSSKiB'] and any(int(r['sampleStartNs'])>=a and int(r['sampleEndNs'])<=b for a,b in windows_ns)]
        integrity=focus.properties(worker/'integrity.txt')
        core.check(integrity['passed']=='true' and int(integrity['residentCount'])==(64 if spec.get('floor') else 32768),
                   'Final JMH values/residents')
        core.check(int(integrity['operations'])==sum(int(w['operations']) for w in windows),'All-phase JMH operations')
        result.update(status='OK',latencyVerified=True,windows=windows,
                      measurement=dict(operations=operations,writes=writes,samples=n,seconds=seconds,
                                       workerAllocatedBytes=allocation,workerBytesPerOperation=allocation/operations,
                                       minimumPayloadAllocationBytes=mandatory,materializationFloorPassed=allocation>=mandatory,
                                       operationsPerSecond=operations/seconds,compilerMs=compiler,
                                       churnPayloadBytes=demand,churnDroppedBytes=dropped),
                      latency={'service':dict(count=n,percentilesNs={str(p):rank(combined,p) for p in (50,99,99.9,99.99,99.999)},
                                              maxNs=max(combined),perIterationSampleCounts=per_iteration)},
                      gc=gc,processMemory=dict(measuredMaxRssKiB=max((int(r['VmRSSKiB']) for r in selected),default=None)),
                      trace={k:v for k,v in info.items() if k.startswith('trace')},
                      integrity=integrity,actualWorker=identity,
                      limits='Sparse JMH samples are not all operations. Iteration/caller/sampling regime differs from the custom recorder.')
        with (path/'sample-bins.csv').open('x',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['valueNs','count']);writer.writerows(sorted(combined.items()))
    result['rawSha256']={str(p.relative_to(path)):focus.sha(p) for p in sorted(path.rglob('*'))
                         if p.is_file() and p.name!='service-result.json'}
    return result


class Observer(core.Campaign):
    def launch_jmh(self,spec,control=False):
        root=self.out/('controls' if control else 'slots');root.mkdir(exist_ok=True)
        path=root/spec['label'];result_file=path/'service-result.json'
        if result_file.exists():
            result=focus.load(result_file);focus.verify_retained(path,result);return result
        core.check(not path.exists(),'Interrupted observer slot retained; adjudicate without overwriting')
        self.check_frozen();ready=focus.evidence.host_snapshot()
        core.check(shutil.disk_usage(self.out).free>=512*1024**2,'Less than512MiB free disk')
        core.check(ready['memAvailableKiB']>=1024**2 and '=0' not in ready.get('externalPower',''),'Host readiness')
        core.check(ready['swapInPages']==self.ready['swapInPages'] and ready['swapOutPages']==self.ready['swapOutPages'],
                   'Paging increased; preserve slots')
        if not control:
            core.check(len(self.state['scheduled'])<24,'Observer matrix budget')
            self.state['scheduled'].append(spec);self.checkpoint()
        path.mkdir();time.sleep(3)
        name='timerFloor' if spec.get('floor') else 'cacheAccess'
        warmups=spec.get('warmups',3 if control else 14)
        iterations=spec.get('iterations',3 if control else 8)
        worker_flags=[*focus.FLAGS,'-XX:+UseG1GC','-Xms512m','-Xmx512m',
                      f'-Xlog:gc*,safepoint:file={path}/gc-%p.log:uptimemillis,timenanos,level,tags:filecount=0',
                      f'-Dservice.observationDir={path}/worker']
        cmd=[focus.JAVA,'-Dchronicle.analytics.disable=true','-Xmx256m','-cp',self.cp,
             'org.openjdk.jmh.Main',BENCH+name,'-t','1','-f','1','-wi',str(warmups),
             '-i',str(iterations),'-w','1s','-r','1s','-bm','sample','-tu','ns','-foe','true',
             '-p','backend='+spec['backend'],'-p','payload='+str(spec['payload']),
             '-p','ballastMiB='+str(spec['liveMiB']),'-jvm',focus.JAVA,
             '-jvmArgsAppend',' '.join(worker_flags),'-rf','json','-rff',str(path/'results.json')]
        focus.save(path/'command.json',dict(command=cmd,startedUtc=focus.now(),workloadForks=1,parentLaunchers=1))
        host=[focus.evidence.host_snapshot()];memory=[];done=threading.Event();errors=[]
        def monitor():
            try:
                while not done.wait(1):
                    host.append(focus.evidence.host_snapshot())
                    info=path/'worker/worker.properties'
                    if info.exists():
                        # Retry an initial metadata write rather than lose the observer thread.
                        try:pid=int(focus.properties(info).get('pid','0'))
                        except (ValueError,FileNotFoundError):continue
                        if pid<=0:continue
                        sample=focus.process_memory(pid,path/'worker/phase.txt')
                        if sample:memory.append(sample)
            except Exception as e:errors.append(str(e))
        thread=None;process=None
        try:
            with (path/'stdout.txt').open('x') as stdout,(path/'stderr.txt').open('x') as stderr:
                process=subprocess.Popen(cmd,stdout=stdout,stderr=stderr,start_new_session=True)
                thread=threading.Thread(target=monitor,daemon=True);thread.start()
                try:code=process.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    # All processes are in the exclusive accounting scope; retain outcome.
                    os.killpg(process.pid,9);process.wait();code=None
        finally:
            if process is not None:
                if process.poll() is None:os.killpg(process.pid,9);process.wait()
                else:
                    try:os.killpg(process.pid,9)
                    except ProcessLookupError:pass
            done.set()
            if thread:thread.join()
            host.append(focus.evidence.host_snapshot())
            for file,rows,fields in [('host.csv',host,list(host[0])),
                                     ('process-memory.csv',memory,focus.MEMORY_FIELDS)]:
                with (path/file).open('x',newline='') as stream:
                    writer=csv.DictWriter(stream,fields);writer.writeheader();writer.writerows(rows)
        result=derive(path,spec,code);result['warnings']+=errors
        core.immutable(result_file,result)
        self.state.update(lastLabel=spec['label'],collectedWorkloadJvms=len(self.observations()),updatedUtc=focus.now())
        self.checkpoint()
        print('OBSERVER_PROGRESS',len(self.observations()),spec['label'],result['status'],
              'warnings='+str(len(result['warnings'])),flush=True)
        return result

    def run(self):
        control=dict(label='timer-floor',backend='CAFFEINE',payload=512,liveMiB=0,block=0,seed=24301,floor=True)
        result=self.launch_jmh(control,True)
        core.check(result['status']=='OK','JMH timer control failed')
        for backend in core.BACKENDS:
            smoke=dict(label='cache-smoke-'+backend,backend=backend,payload=512,liveMiB=0,block=0,seed=24301,
                       warmups=2,iterations=1,smoke=True)
            result=self.launch_jmh(smoke,True)
            core.check(result['status']=='OK','JMH cache smoke failed')
        for spec in self.protocol['design']['schedule']:self.launch_jmh(spec)
        self.check_frozen();rows=self.observations();pair_rows=[]
        grouped=collections.defaultdict(dict)
        for r in rows:grouped[(r['payload'],r['liveMiB'],r['block'])][r['backend']]=r
        for key,arms in sorted(grouped.items()):
            valid=set(arms)==set(core.BACKENDS) and all(r['status']=='OK' for r in arms.values())
            ratios={}
            if valid:
                c,h=[arms[b]['latency']['service']['percentilesNs'] for b in core.BACKENDS]
                ratios={p:h[p]/c[p] for p in c if c[p]}
            pair_rows.append(dict(payload=key[0],liveMiB=key[1],block=key[2],valid=valid,ratios=ratios,
                                  warnings={b:r['warnings'] for b,r in arms.items()}))
        core.immutable(self.out/'study.json',dict(kind='JMH-independent-harness-sensitivity',collectionComplete=True,
                       observations=rows,pairs=pair_rows,limits='Separate harness regime; no pooling with custom-recorder forks.'))
        self.state.update(complete=True,collectionComplete=True,researchComplete=False,completedUtc=focus.now())
        self.checkpoint();print('OBSERVER_COLLECTION_COMPLETE',self.out,len(rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('attempt');args=parser.parse_args()
    core.check(focus.evidence.re.fullmatch('[A-Za-z0-9._-]+',args.attempt),'Invalid attempt')
    design=dict(kind='JMH-service-observer-v1',maxWorkloadJvms=24,schedule=schedule(),controls=3,functionalValidationJvms=0,cacheSmokeJvms=2,parentLauncherJvms=27,
                primaryEndpoint="ordinary 95/5 JMH sampled service p99.9",controlWorkloadJvms=3,
                protocol='docs/TAILCACHE_SERVICE_OBSERVER_PROTOCOL.md',
                discoveryInputs={'build/service-observer-20261117/compilation.json':focus.sha(ROOT/'build/service-observer-20261117/compilation.json')})
    Observer(ROOT/'evidence-archives'/args.attempt,design=design,
             classpath_file=ROOT/'build/service-observer-20261117/classpath.txt').run()
