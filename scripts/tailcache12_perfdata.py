"""External shared-PerfData diagnostics; never primary endpoint or task-duration evidence."""
import json
import os
import pathlib
import subprocess
import time

import tailcache12 as evidence
import tailcache12_calibrate as calibration

EXPORT='jdk.internal.jvmstat/sun.jvmstat.monitor=ALL-UNNAMED'
REQUIRED={'java.ci.totalTime','sun.ci.totalCompiles','sun.ci.lastMethod','sun.os.hrt.frequency'}


def compile_helper():
    directory=evidence.ROOT/'build/tools/tailcache12-perfdata'
    directory.mkdir(parents=True,exist_ok=True)
    sources=[evidence.ROOT/'scripts/java'/name for name in
             ('TailCacheCompilerPerfSampler.java','TailCachePerfSmoke.java')]
    command=[str(pathlib.Path(os.environ['JAVA_HOME'])/'bin/javac'),'-J-Xms16m','-J-Xmx128m',
        '--add-modules','jdk.internal.jvmstat','--add-exports',EXPORT,'-d',str(directory),*map(str,sources)]
    result=subprocess.run(command,text=True,capture_output=True,timeout=30)
    if result.returncode: raise ValueError('PerfData helper compilation failed: '+result.stderr)
    return dict(directory=str(directory),command=command,sourceSha256={p.name:calibration.sha(p) for p in sources},
                classSha256={p.name:calibration.sha(p) for p in sorted(directory.glob('*.class'))})


def helper_command(build,pid,output,stop,maximum=240):
    directory=pathlib.Path(build['directory'])
    verify_build(build)
    return [str(pathlib.Path(os.environ['JAVA_HOME'])/'bin/java'),'-Xms16m','-Xmx64m',
        '--add-modules','jdk.internal.jvmstat','--add-exports',EXPORT,'-cp',str(directory),
        'TailCacheCompilerPerfSampler',str(pid),str(output),str(stop),'10',str(maximum)]


def verify_build(build,directory=None):
    directory=pathlib.Path(directory or build['directory'])
    if 'TailCacheCompilerPerfSampler.class' not in build['classSha256'] or any(
            pathlib.Path(name).name!=name or not name.endswith('.class') or calibration.sha(directory/name)!=digest
            for name,digest in build['classSha256'].items()):
        raise ValueError('Compiled PerfData helper changed')


def freeze_build(build,attempt):
    directory=attempt/'perfdata-helper';directory.mkdir()
    for name,digest in build['classSha256'].items():
        if pathlib.Path(name).name!=name or not name.endswith('.class'):
            raise ValueError('Invalid helper class inventory')
        source=pathlib.Path(build['directory'])/name
        if calibration.sha(source)!=digest: raise ValueError('Helper class changed before freezing')
        with (directory/name).open('xb') as stream:stream.write(source.read_bytes())
    return dict(build,directory=str(directory))


def sample_worker(raw,control,stop,result,build,channel='every-operation',marker_timeout=60):
    from tailcache12_jit_events import worker_identity
    record=dict(method='shared-perfdata-v1',channel=channel,success=False)
    process=None
    try:
        deadline=time.monotonic()+marker_timeout;markers=[]
        while time.monotonic()<deadline and not stop.is_set():
            markers=list(raw.rglob('worker-process-*.properties'))
            if len(markers)>1: raise ValueError('Ambiguous actual worker marker')
            if markers:break
            stop.wait(.2)
        if len(markers)!=1: raise ValueError('Actual worker marker deadline expired')
        metadata=dict(line.split('=',1) for line in markers[0].read_text().splitlines() if '=' in line)
        pid=int(metadata['pid'])
        if markers[0].name!=f'worker-process-{pid}.properties':raise ValueError('Worker marker PID mismatch')
        identity=worker_identity(pid,channel)
        output=control/'perfdata.jsonl';stop_file=control/'perfdata.stop'
        command=helper_command(build,pid,output,stop_file)
        record.update(identity=identity,pid=pid,command=command,startNs=time.monotonic_ns())
        with (control/'perfdata.stdout').open('x') as stdout,(control/'perfdata.stderr').open('x') as stderr:
            process=subprocess.Popen(command,stdout=stdout,stderr=stderr)
            record['samplerPid']=process.pid
            if worker_identity(pid,channel)!=identity:raise ValueError('Worker identity changed during sampler startup')
            while process.poll() is None and not stop.wait(.1):pass
            if process.poll() is None:
                with stop_file.open('x') as stream:stream.write('diagnostic worker finished\n')
            code=process.wait(timeout=5)
        record.update(exitCode=code,endNs=time.monotonic_ns())
        if code:raise ValueError('PerfData helper failed; inspect retained stderr')
        parsed=read_samples(output,expected_pid=pid)
        if parsed['metadata']['samplerPid']!=process.pid:raise ValueError('Sampler PID metadata mismatch')
        record['success']=True
    except Exception as error:record['error']=f'{type(error).__name__}: {error}'
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        record['endNs']=time.monotonic_ns()
        control.mkdir(parents=True,exist_ok=True)
        evidence.save(control/'perfdata-receipt.json',record);result.update(record)


def verify_sampler(control,pid,windows,channel):
    record=json.loads((control/'perfdata-receipt.json').read_text())
    from tailcache12_jit_events import worker_main_class
    if (record.get('method')!='shared-perfdata-v1' or record.get('success') is not True
            or record.get('pid')!=int(pid) or record.get('exitCode')!=0 or record.get('channel')!=channel
            or record.get('identity',{}).get('mainClass')!=worker_main_class(channel)):
        raise ValueError('Missing or changed actual-worker PerfData receipt')
    result=read_samples(control/'perfdata.jsonl',windows,int(pid))
    if (result['metadata']['samplerPid']!=record['samplerPid']
            or not 0<record['startNs']<=result['firstNs']<=min(a for a,b in windows)-60*10**9
            or result['lastNs']>record['endNs']):
        raise ValueError('Late sampler startup or mismatched lifecycle')
    return result


def read_samples(path,windows=(),expected_pid=None):
    records=[json.loads(line) for line in pathlib.Path(path).read_text().splitlines()]
    if (len(records)<4 or records[0].get('kind')!='metadata' or records[0].get('version')!=1
            or records[0].get('intervalMs')!=10 or records[-1].get('kind')!='end'):
        raise ValueError('Missing or incomplete PerfData sampler lifecycle')
    meta=records[0];rows=records[1:-1]
    if (type(meta.get('targetPid')) is not int or meta['targetPid']<=0
            or type(meta.get('samplerPid')) is not int or meta['samplerPid']<=0
            or meta['targetPid']==meta['samplerPid']
            or (expected_pid is not None and meta['targetPid']!=expected_pid)
            or (records[-1].get('targetAlive') is not False and records[-1].get('stopRequested') is not True)):
        raise ValueError('Invalid sampler/target identity or unfinished sampling')
    if not REQUIRED.issubset({c['name'] for c in meta['counters']}):
        raise ValueError('Missing required PerfData counter metadata')
    units={c['name']:c.get('units') for c in meta['counters']}
    expected={'java.ci.totalTime':'Ticks','sun.ci.totalCompiles':'Events',
              'sun.ci.lastMethod':'String','sun.os.hrt.frequency':'Hertz'}
    if any(units[k]!=unit for k,unit in expected.items()):raise ValueError('Unexpected compiler counter units')
    for index,row in enumerate(rows):
        values=row.get('values',{})
        if (row.get('kind')!='sample' or not REQUIRED.issubset(values)
                or not 0<row['startNs']<=row['endNs']
                or not isinstance(values['sun.ci.lastMethod'],str)
                or any(type(values[k]) is not int or values[k]<0 for k in
                       ('java.ci.totalTime','sun.ci.totalCompiles','sun.os.hrt.frequency'))
                or values['sun.os.hrt.frequency']==0):
            raise ValueError('Invalid PerfData snapshot')
        if index:
            before=rows[index-1]
            if (row['startNs']<=before['endNs'] or any(values[k]<before['values'][k] for k in
                    ('java.ci.totalTime','sun.ci.totalCompiles'))
                    or values['sun.os.hrt.frequency']!=before['values']['sun.os.hrt.frequency']):
                raise ValueError('Nonmonotone or changed PerfData compiler clock/counters')
    if records[-1].get('endNs',0)<rows[-1]['endNs']:
        raise ValueError('Sampler end precedes final snapshot')
    if windows and (rows[0]['endNs']>min(a for a,b in windows) or rows[-1]['startNs']<max(b for a,b in windows)):
        raise ValueError('Incomplete worker-window PerfData coverage')
    max_read=max((r['endNs']-r['startNs'])/1e6 for r in rows)
    max_gap=max((b['endNs']-a['startNs'])/1e6 for a,b in zip(rows,rows[1:]))
    if windows and (max_read>50 or max_gap>250):
        raise ValueError('PerfData sampling exceeded declared read/gap bounds')
    candidates=[]
    for before,after in zip(rows,rows[1:]):
        delta=after['values']['java.ci.totalTime']-before['values']['java.ci.totalTime']
        if delta and (not windows or any(after['endNs']>=a and before['startNs']<=b for a,b in windows)):
            candidates.append(dict(startNs=before['startNs'],endNs=after['endNs'],
                compilationDeltaMs=1000*delta/after['values']['sun.os.hrt.frequency'],
                completedCountDelta=after['values']['sun.ci.totalCompiles']-before['values']['sun.ci.totalCompiles'],
                lastMethodBefore=before['values']['sun.ci.lastMethod'],lastMethodAfter=after['values']['sun.ci.lastMethod']))
    return dict(metadata=meta,sampleCount=len(rows),firstNs=rows[0]['startNs'],lastNs=rows[-1]['endNs'],
        maximumReadMs=max_read,maximumEmittedGapMs=max_gap,
        compilerCounterCandidates=candidates,
        limits=['Shared counters/method strings are non-atomic snapshots, not a complete task event stream.',
                'Compilation deltas are global compiler accounting, not method CPU durations or JVM pause times.',
                'Read sampling can perturb CPU/cache scheduling; fast methods and intermediate updates may be missed.'])
