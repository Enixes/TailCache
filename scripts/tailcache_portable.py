#!/usr/bin/env python3
"""Standalone, standard-library collection and analysis for the mechanism workload."""
import argparse
import collections
import contextlib
import csv
import datetime
import hashlib
import json
import math
import os
import pathlib
import platform
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
import zipfile

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
VERSION = 'tailcache-portable-v1'
BACKENDS = ('CAFFEINE', 'CHRONICLE_IN_MEMORY')
CHANNELS = ('service', 'response', 'gap', 'read-service', 'update-service')
WRITE_CHANNELS = ('write-value-construction', 'write-cache-put')
WRITE_CLOCK_CHANNEL = 'write-clock-floor'
WRITE_CLOCK_SAMPLES = 4096
WRITE_TAIL_CLOCK_MULTIPLE = 4
WRITE_TIMING_SUITES = ('split-write-timing', 'sampled-split-write-timing')
WRITE_PILOT_LIMITS = {
    'operationsPerSecond': .10,
    'serviceP999': .10,
    'updateServiceP999': .15,
    'backendRatioDrift': .05,
}
QUANTILES = (50, 99, 99.9, 99.99, 99.999)
RETRYABLE_OBSERVER_WARNINGS = frozenset((
    'Outside-process CPU upper bound exceeded frozen ceiling',
    'Missing outside-process CPU evidence',
    'Outside-process CPU attribution incomplete',
    'Host sampling does not cover conditioning and measurement',
    'Host sampling gap exceeds 3 seconds',
    'Final observer sample unavailable',
))
SUITES = {
    'quick': (),
    'locality': ('locality',),
    'write-ratio': ('write-ratio',),
    'locality-long': ('locality-long',),
    'locality-arrival-rate': ('locality-arrival-rate',),
    'rq-matrix': ('rq-matrix',),
    'saturated-write-pressure': ('saturated-write-pressure',),
    'write-transition': ('write-transition',),
    'split-write-timing': ('split-write-timing',),
    'sampled-split-write-timing': ('sampled-split-write-timing',),
    'all': ('locality', 'write-ratio', 'rq-matrix'),
}
MAIN = 'io.github.enixes.tailcache.workload.MechanismCrossoverRunner'
FLAGS = ['-Dchronicle.analytics.disable=true',
 '--add-exports=java.base/jdk.internal.misc=ALL-UNNAMED',
 '--add-exports=java.base/jdk.internal.ref=ALL-UNNAMED',
 '--add-exports=java.base/jdk.internal.util=ALL-UNNAMED',
 '--add-exports=java.base/sun.nio.ch=ALL-UNNAMED',
 '--add-exports=jdk.compiler/com.sun.tools.javac.file=ALL-UNNAMED',
 '--add-exports=jdk.unsupported/sun.misc=ALL-UNNAMED',
 '--add-opens=java.base/java.io=ALL-UNNAMED',
 '--add-opens=java.base/java.lang=ALL-UNNAMED',
 '--add-opens=java.base/java.lang.reflect=ALL-UNNAMED',
 '--add-opens=java.base/java.util=ALL-UNNAMED',
 '--add-opens=jdk.compiler/com.sun.tools.javac=ALL-UNNAMED']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(pathlib.Path(path).read_text(), object_pairs_hook=unique)


def save_new(path, value):
    """Publish a complete file exclusively; never replace retained evidence."""
    path = pathlib.Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = pathlib.Path(stream.name)
        stream.write(json.dumps(value, indent=2, allow_nan=False).encode() + b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(temporary, path)
    finally:
        temporary.unlink()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def integer(value, lo, hi):
    return type(value) is int and lo <= value <= hi


def validate(config):
    require(isinstance(config,dict),'Configuration must be a JSON object')
    expected = {'schemaVersion','name','purpose','heapMiB','activeProcessorCount','residents','churnMiBPerSecond',
                'warmupMs','conditioningMs','measureMs','primeCalls','seeds','orderSeed','logging','cells','quality'}
    require(set(config)-{'maxExternalRetryPairs'} == expected and type(config['schemaVersion']) is int and config['schemaVersion'] == 1,
            'Unknown/missing config fields or schema')
    require(isinstance(config['name'],str) and re.fullmatch(r'[a-zA-Z0-9-]{1,80}', config['name']) is not None, 'Invalid name')
    require(config['purpose'] in ('research', 'diagnostic'), 'Invalid purpose')
    retries = config.get('maxExternalRetryPairs', 0)
    require(integer(retries,0,8) and (retries==0 or config['purpose']=='research'), 'Invalid external retry budget')
    for key, lo, hi in [('heapMiB',128,16384),('activeProcessorCount',1,4096),('residents',16,32768),('churnMiBPerSecond',0,953),
                        ('warmupMs',1,3600000),('conditioningMs',1,3600000),('measureMs',1,3600000),
                        ('primeCalls',0,4),('orderSeed',0,2**63-1)]:
        require(integer(config[key],lo,hi), 'Invalid ' + key)
    require(config['warmupMs'] >= config['primeCalls'] * 1000, 'Priming exceeds warmup')
    require(config['logging'] in ('sync','async'), 'Invalid logging')
    seeds = config['seeds']
    require(isinstance(seeds,list) and 2 <= len(seeds) <= 100 and len(seeds)%2 == 0
            and all(integer(s,0,2**63-1) for s in seeds) and len(set(seeds)) == len(seeds),
            'Use an even number of distinct seeds (2..100) for balanced paired blocks')
    cells = config['cells']
    require(isinstance(cells,list) and 1 <= len(cells) <= 200, 'Invalid cells')
    require(all(isinstance(c,dict) for c in cells),'Cells must be JSON objects')
    require(len({canonical(c) for c in cells}) == len(cells), 'Duplicate cells')
    for c in cells:
        require(set(c)-{'splitWriteTiming','splitWriteSampleEvery'} == {'payloadBytes','liveMiB','writeBps','updateHotset','qps'},
                'Unknown/missing cell fields')
        for key, lo, hi in [('payloadBytes',16,32768),('liveMiB',0,2047),('writeBps',0,10000),
                            ('updateHotset',1,config['residents']),('qps',0,1000000)]:
            require(integer(c[key],lo,hi), 'Invalid cell ' + key)
        require(c['qps'] == 0 or 10**9 % c['qps'] == 0, 'QPS must divide one billion exactly')
        require(c['qps'] == 0 or all(config[k]*c['qps']%1000 == 0 for k in ('warmupMs','conditioningMs','measureMs')),
                'Each phase must contain an integer number of arrivals')
        if 'splitWriteTiming' in c:
            require(c['splitWriteTiming'] is True and c['writeBps'] > 0,
                    'Split write timing requires actual writes and must be true when specified')
        if 'splitWriteSampleEvery' in c:
            require(c.get('splitWriteTiming') and integer(c['splitWriteSampleEvery'],2,64),
                    'Split write sampling requires split timing and a stride of 2..64')
    q = config['quality']
    require(isinstance(q,dict),'Quality must be a JSON object')
    require(set(q) == {'minAvailableMiB','minDiskMiB','compilerWarningMs','maxOutsideCpuFraction',
                       'maxChurnRelativeError','minExpectedTailEvents'}, 'Unknown/missing quality fields')
    for key in ('minAvailableMiB','minDiskMiB','compilerWarningMs','minExpectedTailEvents'):
        require(integer(q[key],1,1000000), 'Invalid quality ' + key)
    for key in ('maxOutsideCpuFraction','maxChurnRelativeError'):
        require(type(q[key]) in (int,float) and math.isfinite(q[key]) and 0 < q[key] <= .5, 'Invalid quality ' + key)
    return config


def schedule(config):
    rows = []
    for block, seed in enumerate(config['seeds']):
        cells = list(enumerate(config['cells']))
        random.Random(config['orderSeed']+block).shuffle(cells)
        for index, cell in cells:
            first = (block+index) % 2
            for backend in (BACKENDS[first],BACKENDS[1-first]):
                rows.append(dict(label=f'b{block+1:02}-c{index+1:03}-{backend}', block=block+1,
                                 cell=index+1, seed=seed, backend=backend, **cell))
    return rows


def plan(config):
    validate(config)
    rows = schedule(config)
    seconds = len(rows)*sum(config[k] for k in ('warmupMs','conditioningMs','measureMs'))/1000
    endpoints = 'service and scheduled-response separately; p99,p99.9,p99.99,p99.999'
    if any(cell.get('splitWriteTiming') for cell in config['cells']):
        endpoints += '; write-value-construction and write-cache-put, primary p99 and p99.9'
    return dict(version=VERSION, config=config, schedule=rows,
                workloadJvms=len(rows) if config['purpose']=='research' else 0, diagnosticJvms=len(rows) if config['purpose']=='diagnostic' else 0,
                maximumExternalRetryJvms=2*config.get('maxExternalRetryPairs',0),
                nominalWorkloadMinutes=seconds/60, setupAndVerificationAdditional=True,
                controls='Functional test plus two controls per backend before workload; not research observations',
                endpoints=endpoints,
                limits='No pooled quantiles; same inputs do not imply identical hardware/performance')


def suite_plan(config_dir, suite):
    """Use a shared baseline once, with one counterbalanced research schedule."""
    smoke = plan(load(config_dir/'smoke.json'))
    require(smoke['config']['purpose']=='diagnostic', 'The smoke profile must be diagnostic')
    phases = {'smoke': smoke}
    views = {}
    cells = []
    shared = None
    for name in SUITES[suite]:
        config = validate(load(config_dir/(name+'.json')))
        require(config['purpose']=='research', 'A research profile must declare research purpose')
        common = {k: v for k, v in config.items() if k not in ('name', 'cells')}
        if shared is None:
            shared = common
        require(common==shared, 'Suite profiles must share JVM, timing, seed and quality settings')
        views[name] = []
        for cell in config['cells']:
            if cell not in cells:
                cells.append(cell)
            views[name].append(cells.index(cell)+1)
    if shared is not None:
        if suite in WRITE_TIMING_SUITES:
            pilot = plan(load(config_dir/(suite+'-pilot.json')))
            pilot_config = pilot['config']
            check_keys = {'name','purpose','seeds','orderSeed','maxExternalRetryPairs'}
            require(pilot_config['purpose']=='diagnostic' and set(pilot_config['seeds']).isdisjoint(shared['seeds']),
                    'Write timing pilot must use separate diagnostic seeds')
            require({k:v for k,v in pilot_config.items() if k not in check_keys|{'cells'}}
                    == {k:v for k,v in shared.items() if k not in check_keys},
                    'Write timing pilot must match research JVM, duration and quality settings')
            require(len(pilot_config['cells'])==2, 'Write timing pilot needs two timing modes')
            old, split = pilot_config['cells']
            require('splitWriteTiming' not in old
                    and {k:v for k,v in split.items() if k not in ('splitWriteTiming','splitWriteSampleEvery')} == old
                    and split in cells and all(c.get('splitWriteTiming')
                        and c.get('splitWriteSampleEvery') == split.get('splitWriteSampleEvery') for c in cells),
                    'Write pilot must compare original and split timing on one research cell')
            phases['write-timing-pilot'] = pilot
        phases['research'] = plan(dict(shared, name='reproduction-'+suite, cells=cells))
    result = dict(suite=suite, phases=phases, researchViews=views,
                researchJvms=sum(p['workloadJvms'] for p in phases.values()),
                diagnosticJvms=sum(p['diagnosticJvms'] for p in phases.values()),
                nominalWorkloadMinutes=sum(p['nominalWorkloadMinutes'] for p in phases.values()))
    if suite in WRITE_TIMING_SUITES:
        result['writePilotLimits'] = WRITE_PILOT_LIMITS
        result['writeTailClockMultiple'] = WRITE_TAIL_CLOCK_MULTIPLE
    return result


def capture(command, timeout=20):
    try:
        r = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        return dict(command=list(map(str,command)),exitCode=r.returncode,stdout=r.stdout,stderr=r.stderr)
    except (OSError,subprocess.TimeoutExpired) as error:
        return dict(error=str(error))


def inventory(root, exclude=()):
    return {str(p.relative_to(root).as_posix()):sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and p.name not in exclude and '__pycache__' not in p.parts}


def verify_inventory(root, expected):
    for name, digest in expected.items():
        relative = pathlib.PurePosixPath(name)
        require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe evidence path')
        require(sha(root.joinpath(*relative.parts)) == digest, 'Evidence changed: ' + name)


def bundle_identity():
    manifest = load(HERE/'bundle.json')
    require(manifest['version'] == VERSION, 'Incompatible bundle')
    require(manifest['id'] == hashlib.sha256(canonical(manifest['files'])).hexdigest(), 'Invalid bundle identity')
    verify_inventory(HERE,manifest['files'])
    require(set(p.name for p in (HERE/'lib').iterdir()) ==
            {pathlib.PurePosixPath(n).name for n in manifest['files'] if n.startswith('lib/')}, 'Unexpected runtime files')
    return manifest['id']


def java_identity(explicit=None):
    require(not any(os.environ.get(k) for k in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS')),
            'Unset JAVA_TOOL_OPTIONS, JDK_JAVA_OPTIONS and _JAVA_OPTIONS before collection')
    candidate = explicit or (str(pathlib.Path(os.environ['JAVA_HOME'])/'bin'/('java.exe' if os.name=='nt' else 'java'))
                             if os.environ.get('JAVA_HOME') else shutil.which('java'))
    require(candidate is not None, 'Java 21 required: use --java, JAVA_HOME or PATH')
    executable = pathlib.Path(candidate).resolve()
    require(executable.is_file(), 'Java executable missing')
    r = capture([str(executable),'-XshowSettings:properties','-version'])
    require(r.get('exitCode') == 0, 'Java discovery failed: ' + str(r))
    settings = r['stderr'] + r['stdout']
    version = re.search(r'^\s*java.specification.version = (\S+)', settings, re.M)
    home = re.search(r'^\s*java.home = (.+)', settings, re.M)
    require(version is not None and version[1] == '21' and home is not None, 'Use a full Java 21 runtime')
    base = pathlib.Path(home[1].strip())
    runtime = sorted({base/'release',executable,*[p for folder in ('bin','lib','conf')
                         for p in (base/folder).rglob('*') if p.is_file()]})
    require((base/'lib/modules').is_file() and all(p.is_file() for p in runtime) and len(runtime)>=4,
            'Incomplete Java runtime')
    # Relative names make identity independent of installation directory.
    hashes = {('bin/'+p.name if p==executable else str(p.relative_to(base).as_posix())):sha(p) for p in runtime}
    return dict(executable=str(executable),home=str(base),properties=r,files=hashes,
                id=hashlib.sha256(canonical(hashes)).hexdigest())


def text_file(path):
    try:
        return pathlib.Path(path).read_text().strip()
    except (OSError,UnicodeError):
        return None


def host_identity(out):
    info = dict(os=platform.platform(),architecture=platform.machine(),cpuCount=os.cpu_count(),
                processor=platform.processor(),python=platform.python_version(),
                machineIdSha256=hashlib.sha256((text_file('/etc/machine-id') or platform.node()).encode()).hexdigest(),
                cpuinfo=text_file('/proc/cpuinfo'),meminfo=text_file('/proc/meminfo'),
                cgroup=text_file('/proc/self/cgroup'),affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None)
    # Remove fluctuating cpu MHz and memory fields from resume identity.
    cpu = '\n'.join(line for line in (info['cpuinfo'] or '').splitlines() if 'cpu MHz' not in line)
    identity = {k:info[k] for k in ('os','architecture','cpuCount','machineIdSha256','affinity')}
    identity['cpuinfo'] = cpu
    info['id'] = hashlib.sha256(canonical(identity)).hexdigest()
    info['bootId'] = text_file('/proc/sys/kernel/random/boot_id')
    info['metadata'] = {label:capture(command) for label,command in {
        'mount':['findmnt','--json','--target',str(out),'-o','TARGET,SOURCE,FSTYPE,OPTIONS'],
        'storage':['lsblk','--json','-o','NAME,TYPE,SIZE,ROTA,MODEL,FSTYPE,MOUNTPOINTS'],
        'cpu':['lscpu','--json']}.items()}
    info['mountFingerprint'] = hashlib.sha256(canonical(info['metadata']['mount'])).hexdigest()
    cgroup = info['cgroup'] or ''
    cg = next((line[3:] for line in cgroup.splitlines() if line.startswith('0::')), None)
    root = pathlib.Path('/sys/fs/cgroup')/cg.lstrip('/') if cg else None
    info['cgroupLimits'] = {n:text_file(root/n) for n in ('cpu.max','memory.max','memory.swap.max','cpuset.cpus.effective')} if root else {}
    info['cpuPolicy'] = {str(p):text_file(p) for name in ('scaling_governor','scaling_driver','scaling_min_freq','scaling_max_freq')
                         for p in pathlib.Path('/sys/devices/system/cpu/cpufreq').glob('policy*/'+name)}
    info['clocksource'] = text_file('/sys/devices/system/clocksource/clocksource0/current_clocksource')
    info['swaps'] = text_file('/proc/swaps')
    info['pid1'] = text_file('/proc/1/comm')
    info['containerDetected'] = (pathlib.Path('/.dockerenv').exists() or
        any(x in cgroup for x in ('docker','kubepods','containerd')) or
        'codex-linux-san' in (info['pid1'] or ''))
    info['capability'] = 'linux-proc' if sys.platform.startswith('linux') and not info['containerDetected'] else 'diagnostic'
    return info


def snapshot(pid=None):
    """Cheap counters only. No page-table walk, forced GC or page-cache eviction."""
    result = dict(startNs=time.monotonic_ns())
    mem = text_file('/proc/meminfo') or ''
    vm = text_file('/proc/vmstat') or ''
    for name in ('MemAvailable','SwapFree'):
        match = re.search(r'^'+name+r':\s+(\d+)',mem,re.M)
        result[name+'KiB'] = int(match[1]) if match else None
    for name in ('pswpin','pswpout','zswpin','zswpout'):
        match = re.search(r'^'+name+r' (\d+)$',vm,re.M)
        result[name] = int(match[1]) if match else None
    cpu = text_file('/proc/stat') or ''
    match = re.search(r'^cpu\s+(.+)$',cpu,re.M)
    if match:
        ticks = list(map(int,match[1].split()))[:8] # guest is already in user/nice
        result.update(cpuTotal=sum(ticks),cpuBusy=sum(ticks)-ticks[3]-ticks[4])
    if pid:
        stat = text_file(f'/proc/{pid}/stat')
        if stat:
            fields = stat[stat.rfind(')')+2:].split()
            result['processTicks'] = int(fields[11])+int(fields[12])
            result.update(processMinorFaults=int(fields[7]),processMajorFaults=int(fields[9]))
        status = text_file(f'/proc/{pid}/status') or ''
        for key in ('VmRSS','VmHWM','RssAnon','RssFile'):
            match = re.search(r'^'+key+r':\s+(\d+)',status,re.M)
            result[key+'KiB'] = int(match[1]) if match else None
    power = pathlib.Path('/sys/class/power_supply')
    result['externalPower'] = {p.parent.name:text_file(p) for p in power.glob('*/online')}
    result['throttle'] = {str(p):text_file(p) for p in pathlib.Path('/sys/devices/system/cpu').glob('cpu[0-9]*/thermal_throttle/*_throttle_count')}
    cgroup=text_file('/proc/self/cgroup') or ''
    cg=next((line[3:] for line in cgroup.splitlines() if line.startswith('0::')),None)
    root=pathlib.Path('/sys/fs/cgroup')/cg.lstrip('/') if cg else None
    maximum=text_file(root/'memory.max') if root else None
    current=text_file(root/'memory.current') if root else None
    result['cgroupAvailableKiB']=max(0,(int(maximum)-int(current))//1024) if maximum and maximum.isdigit() and current and current.isdigit() else None
    result['endNs'] = time.monotonic_ns()
    return result


def power_disconnected(supplies):
    states = [state for state in supplies.values() if state in ('0', '1')]
    return bool(states) and all(state=='0' for state in states)


def quality_screen(samples, start, end, config, capability):
    warnings, startup = [], []
    if capability != 'linux-proc':
        warnings.append('Host telemetry is diagnostic: unsupported OS or detected container')
    available=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else os.cpu_count()
    if available is None or available<config['activeProcessorCount']:
        warnings.append('Available CPUs below frozen JVM processor budget; oversubscription possible')
    intervals = [(a,b) for a,b in zip(samples,samples[1:]) if a['startNs'] <= end and b['endNs'] >= start]
    if not intervals or intervals[0][0]['startNs'] > start or intervals[-1][1]['endNs'] < end:
        warnings.append('Host sampling does not cover conditioning and measurement')
    if any(b['endNs']-a['startNs']>3_000_000_000 for a,b in intervals):
        warnings.append('Host sampling gap exceeds 3 seconds')
    outside = []
    unattributed = []
    missing_cpu_intervals = 0
    unattributed_cpu_intervals = 0
    for key in ('pswpin','pswpout','zswpin','zswpout'):
        if any(a.get(key) is None or b.get(key) is None for a,b in intervals):
            warnings.append('Missing host counter: '+key)
        elif any(b[key] != a[key] for a,b in intervals):
            warnings.append('Conditioning/measurement host paging counter changed: '+key)
        if samples and samples[0].get(key) is not None and samples[-1].get(key) != samples[0][key]:
            startup.append('Whole-lifetime host paging counter changed: '+key)
    for a,b in intervals:
        if any(s.get(k) is None for s in (a,b) for k in ('cpuTotal', 'cpuBusy')):
            missing_cpu_intervals += 1
            continue
        total = b['cpuTotal']-a['cpuTotal']
        busy = b['cpuBusy']-a['cpuBusy']
        if total<=0 or not 0<=busy<=total:
            missing_cpu_intervals += 1
            continue
        before = a.get('processTicks')
        after = b.get('processTicks')
        uncertainty = (b['endNs']-b['startNs']+a['endNs']-a['startNs'])/max(1,b['startNs']-a['endNs'])
        if before is None or after is None or after<before:
            # Keep the whole-machine bound, but distinguish missing attribution
            # from a threshold crossing with worker CPU accounted for.
            unattributed_cpu_intervals += 1
            unattributed.append(min(1, busy/total+uncertainty))
            continue
        outside.append(min(1, max(0, (busy-(after-before))/total)+uncertainty))
    if not intervals or missing_cpu_intervals:
        warnings.append('Missing outside-process CPU evidence')
    if unattributed_cpu_intervals:
        warnings.append('Outside-process CPU attribution incomplete')
    if outside and max(outside)>config['quality']['maxOutsideCpuFraction']:
        warnings.append('Outside-process CPU upper bound exceeded frozen ceiling')
    if any(not s.get('externalPower') for s in samples):
        # Servers commonly have no power-supply sensor; this is capability metadata, not a noisy run.
        startup.append('External power sensor unavailable')
    if any(power_disconnected(s.get('externalPower',{})) for a,b in intervals for s in (a,b)):
        warnings.append('External power disconnected during protected window')
    if any(a.get('throttle',{}).get(k) != v for a,b in intervals for k,v in b.get('throttle',{}).items()):
        warnings.append('Thermal throttle counter changed during protected window')
    if any(s.get('MemAvailableKiB') is None for a,b in intervals for s in (a,b)):
        warnings.append('Missing available-memory evidence')
    elif any(s['MemAvailableKiB']<config['quality']['minAvailableMiB']*1024 for a,b in intervals for s in (a,b)):
        warnings.append('Host available memory below frozen reserve')
    if any(s.get('cgroupAvailableKiB') is not None and s['cgroupAvailableKiB']<config['quality']['minAvailableMiB']*1024
           for a,b in intervals for s in (a,b)):
        warnings.append('Cgroup available memory below frozen reserve')
    return dict(warnings=sorted(set(warnings)),lifetimeDiagnostics=sorted(set(startup)),
                protectedWindow='conditioning start through measurement end; overlapping 1Hz brackets',
                outsideCpuMaxUpperFraction=max(outside,default=None),outsideCpuMissingIntervals=missing_cpu_intervals,
                outsideCpuUnattributedIntervals=unattributed_cpu_intervals,
                outsideCpuUnattributedMaxUpperFraction=max(unattributed,default=None),
                sensorAttribution='Host-wide; not causal attribution to worker')


@contextlib.contextmanager
def host_lock():
    path = pathlib.Path(tempfile.gettempdir())/('tailcache-portable-'+str(getattr(os,'getuid',lambda:0)())+'.lock')
    with path.open('a+b') as stream:
        try:
            if os.name == 'nt':
                import msvcrt
                stream.seek(0); stream.write(b'0'); stream.flush(); stream.seek(0)
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError('Another portable benchmark holds the host lock') from error
        yield


def csv_rows(path):
    with pathlib.Path(path).open(newline='') as stream:
        return list(csv.DictReader(stream))


def properties(path):
    return dict(line.split('=',1) for line in pathlib.Path(path).read_text().splitlines() if '=' in line)


def histogram(path, expected):
    values = [(int(r['upperEquivalentNs']),int(r['count'])) for r in csv_rows(path)]
    require(all(v>=0 and n>0 for v,n in values) and all(a[0]<b[0] for a,b in zip(values,values[1:])), 'Malformed histogram')
    require(sum(n for v,n in values)==expected, 'Histogram/operation conservation failed')
    return values


def quantile(values, q):
    total=sum(n for v,n in values)
    if not total:
        return None
    target=max(1,math.ceil(math.nextafter(q,-math.inf)*total/100))
    count=0
    for value,n in values:
        count+=n
        if count>=target:
            return value
    raise ValueError('Quantile rank missing')


def hist_stats(values, config):
    total=sum(n for v,n in values)
    tails={}
    for q in QUANTILES:
        expected=total*(1-q/100)
        tails[str(q)] = dict(ns=quantile(values,q),expectedBeyondQuantile=expected,
            tailSupportWarning=expected<config['quality']['minExpectedTailEvents'])
    rates={}
    for threshold in (100000,1000000,10000000):
        # HDR upper-equivalent bins leave the crossing bin uncertain.
        upper=sum(n for u,n in values if u>threshold)
        lower=sum(n for u,n in values if u-(1<<max(0,u.bit_length()-11))+1>threshold)
        rates[str(threshold)] = dict(lowerCount=lower,upperCount=upper,
            lowerProbability=lower/total if total else None,upperProbability=upper/total if total else None)
    return dict(count=total,percentiles=tails,maxUpperEquivalentNs=values[-1][0] if values else None,exceedance=rates)


def analysis_module():
    import importlib.util
    path=HERE/'analysis.py' if (HERE/'analysis.py').exists() else HERE/'tailcache12_analysis.py'
    spec=importlib.util.spec_from_file_location('portable_gc_analysis',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def stall_export(worker, measurement, limit):
    total = int(measurement['stallEvents'])
    omitted = int(measurement['unexportedStallEvents'])
    require(limit>0 and total>=0 and omitted==max(0,total-limit), 'Invalid stall export counts')
    exported = csv_rows(worker/'stalls.csv')
    require(len(exported)==total-omitted, 'Stall export row count differs from measurement')
    indexes = [int(row['operationIndex']) for row in exported]
    require(all(0<=index<int(measurement['operations']) for index in indexes)
            and all(a<b for a,b in zip(indexes,indexes[1:])), 'Invalid stall export operation indexes')
    return dict(total=total, exported=len(exported), omitted=omitted)


def latency_counts(spec, operations, writes):
    counts = {'service': operations, 'response': operations if spec['qps'] else 0,
              'gap': operations, 'read-service': operations-writes, 'update-service': writes}
    if spec.get('splitWriteTiming'):
        stride = spec.get('splitWriteSampleEvery',1)
        offset = spec['seed'] % stride
        sampled = (writes + stride - 1 - offset)//stride
        require(sampled > 0, 'No writes observed for split timing')
        counts.update(dict.fromkeys(WRITE_CHANNELS, sampled))
        counts[WRITE_CLOCK_CHANNEL] = WRITE_CLOCK_SAMPLES
    return counts


def write_timer_resolved(latency, quantile='99', channels=WRITE_CHANNELS):
    floor = latency[WRITE_CLOCK_CHANNEL]['percentiles']['99']['ns']
    return floor is not None and floor > 0 and all(
        latency[channel]['percentiles'][quantile]['ns'] >= WRITE_TAIL_CLOCK_MULTIPLE*floor
        for channel in channels)


def summarize(path, spec, config, capability, code):
    result=dict(spec=spec,exitCode=code,status='FAILED',warnings=[],startedUtc=load(path/'command.json')['startedUtc'])
    try:
        require(code==0,'Worker failed; stdout/stderr retained')
        worker=path/'worker'
        require((worker/'phase.txt').read_text()=='COMPLETE', 'Worker incomplete')
        completion=properties(worker/'completion.txt')
        require(completion['status']=='OK' and int(completion['unserved'])==0, 'Censored worker')
        windows=csv_rows(worker/'windows.csv')
        expected=['PRIME'+str(i) for i in range(config['primeCalls'])]+['WARMUP','CONDITIONING','MEASUREMENT']
        if config['warmupMs']==config['primeCalls']*1000: expected.remove('WARMUP')
        require([w['phase'] for w in windows]==expected,'Unexpected phases')
        cursor=0
        for w in windows:
            phase=w['phase'];pos=properties(worker/('stream-'+phase+'.txt'))
            require(int(pos['start'])==cursor,'Stream reset between phases')
            count=int(w['operations'])
            if not spec.get('floor'):
                require(int(pos['end'])-cursor==count,'Stream operation mismatch')
            cursor=int(pos['end'])
            duration=1000 if phase.startswith('PRIME') else config['warmupMs']-config['primeCalls']*1000 if phase=='WARMUP' else config['conditioningMs'] if phase=='CONDITIONING' else config['measureMs']
            require(int(w['endNs'])>int(w['startNs']),'Invalid measurement clock')
            require(not spec['qps'] or count==int(w['scheduled'])==duration*spec['qps']//1000,'Missing scheduled operations')
        m=windows[-1];n=int(m['operations']);writes=int(m['writes'])
        require(n>0,'No operations')
        counts=latency_counts(spec,n,writes)
        bins={ch:histogram(worker/(ch+'-bins.csv'),count) for ch,count in counts.items()}
        union=collections.Counter(dict(bins['read-service']));union.update(dict(bins['update-service']))
        require(dict(union)==dict(bins['service']),'Read/update histogram union mismatch')
        actual=properties(worker/'configuration.txt')
        require(int(actual['maxHeapBytes'])==config['heapMiB']*1024**2,'Actual heap differs')
        require(actual['backend']==spec['backend'] and actual['readContract']=='ordinary-get', 'Actual cache contract differs')
        require(int(actual['primeCalls'])==config['primeCalls'], 'Actual priming differs')
        require(actual['streamPhaseReset']==actual['streamWrap']=='false','Finite/reset trace')
        require(int(actual['updateHotset'])==spec['updateHotset'],'Update population differs')
        require(actual.get('splitWriteTiming','false')==str(spec.get('splitWriteTiming',False)).lower(),
                'Actual write timing mode differs')
        require(int(actual.get('splitWriteSampleEvery',1))==spec.get('splitWriteSampleEvery',1),
                'Actual split write sample stride differs')
        require('chronicle.analytics.disable=true' in actual['jvmArgs'],'Analytics flag missing')
        integrity=properties(worker/'integrity.txt')
        require(int(integrity['residentCount'])==config['residents'],'Resident count changed')
        samples=load(path/'host.json')
        conditioning=next(w for w in windows if w['phase']=='CONDITIONING')
        screen=quality_screen(samples,int(conditioning['startNs']),int(m['endNs']),config,capability)
        warnings=screen['warnings']
        stalls = stall_export(worker, m, int(actual['eventLimit']))
        if stalls['omitted']:
            warnings.append('Stall event detail capped; complete histograms retained')
        elapsed=(int(m['endNs'])-int(m['startNs']))/1e9
        if int(m['compilerMs'])<0: warnings.append('Compiler activity unavailable')
        elif int(m['compilerMs'])>config['quality']['compilerWarningMs']: warnings.append('Measured compiler activity exceeds frozen ceiling; not app pause time')
        target=config['churnMiBPerSecond']*1024**2
        achieved=int(m['churnPayloadBytes'])/elapsed
        if target and abs(achieved/target-1)>config['quality']['maxChurnRelativeError']: warnings.append('Realized churn outside frozen relative-error ceiling')
        if int(m['churnDroppedBytes']): warnings.append('Churn demand dropped; endogenous outcome retained')
        if quantile(bins['service'],50)==0: warnings.append('Service median below timer resolution; zero latency ratios unresolved')
        require(int(m['churnJvmAllocatedBytes'])>=int(m['churnPayloadBytes']),'Churn allocation not corroborated')
        parser=analysis_module();parsed=parser.parse_gc(path/'gc.log')
        require(parsed['maxHeapBytes']==config['heapMiB']*1024**2,'GC log heap differs')
        gc=parser.gc_summary(parsed,[(int(m['startNs']),int(m['endNs']))],n)
        text=(path/'stderr.txt').read_text(errors='replace')+(path/'gc.log').read_text(errors='replace')
        if any('dropped' in line.lower() and ('log' in line.lower() or 'messages' in line.lower()) for line in text.splitlines()):
            warnings.append('Logging reported dropped messages')
        latency={ch:hist_stats(v,config) for ch,v in bins.items()}
        if spec.get('splitWriteTiming') and not write_timer_resolved(latency):
            warnings.append('Split write p99 too close to the clock floor; API tail unresolved')
        if 'splitWriteSampleEvery' in spec and any(
                latency[ch]['percentiles']['99.9']['tailSupportWarning'] for ch in WRITE_CHANNELS):
            warnings.append('Sampled split write p99.9 has insufficient tail support')
        result.update(status='COMPLETE',warnings=sorted(set(warnings)),host=screen,windows=windows,
                      integrity=integrity,configuration=actual,stallExport=stalls,
                      latency=latency,
                      gc=gc,operationsPerSecond=n/elapsed,workerAllocatedBytes=int(m['workerAllocatedBytes']),
                      workerAllocatedBytesPerOperation=int(m['workerAllocatedBytes'])/n,
                      freshWritePayloadBytes=writes*spec['payloadBytes'],
                      compilerMs=int(m['compilerMs']),achievedChurnBytesPerSecond=achieved,
                      peakObservedRssKiB=max((s.get('VmRSSKiB') or 0 for s in samples),default=0) or None)
    except (ValueError,OSError,KeyError,StopIteration) as error:
        result['failure']=str(error)
    return result


def worker_command(java, config, spec, path, observer_handshake=False):
    cp=os.pathsep.join(str(p) for p in sorted((HERE/'lib').glob('*.jar')))
    # Relative log path avoids Windows drive-letter/colon unified-log escaping.
    command=[java,*FLAGS,'-XX:+UseG1GC',f'-XX:ActiveProcessorCount={config["activeProcessorCount"]}',
             f'-Xms{config["heapMiB"]}m',f'-Xmx{config["heapMiB"]}m',
             '-XX:AsyncLogBufferSize=2097152',
             '-Xlog:gc*,safepoint:file=gc.log:uptimemillis,timenanos,level,tags:filecount=0',
             '-Xlog:gc+age=trace:file=age.log:uptimemillis,timenanos,level,tags:filecount=0']
    if config['logging']=='async': command.append('-Xlog:async')
    command += ['-cp',cp,MAIN]
    options={'out':str(path/'worker'),'backend':spec['backend'],'payload':spec['payloadBytes'],
             'live-mib':spec['liveMiB'],'residents':config['residents'],'churn-mib-sec':config['churnMiBPerSecond'],
             'qps':spec['qps'],'seed':spec['seed'],'warmup-ms':config['warmupMs'],
             'conditioning-ms':config['conditioningMs'],'measure-ms':config['measureMs'],
             'prime-calls':config['primeCalls'],'write-bps':spec['writeBps'],'update-hotset':spec['updateHotset'],
             'floor':str(spec.get('floor',False)).lower(),'supply-floor':'false','inject-stall-ms':spec.get('injectMs',0),'reuse':'false'}
    if observer_handshake:
        options['observer-handshake'] = 'true'
    if spec.get('splitWriteTiming'):
        options['split-write-timing'] = 'true'
    if 'splitWriteSampleEvery' in spec:
        options['split-write-sample-every'] = spec['splitWriteSampleEvery']
    for k,v in options.items(): command += ['--'+k,str(v)]
    return command


def launch(path, spec, config, java, capability):
    path.mkdir()
    handshake = capability == 'linux-proc'
    command=worker_command(java,config,spec,path,observer_handshake=handshake)
    save_new(path/'command.json',dict(command=command,startedUtc=now(),
        bootId=text_file('/proc/sys/kernel/random/boot_id'),capability=capability))
    samples=[];errors=[];finished=threading.Event();interrupted=False
    ready = path/'worker'/'observer-ready'
    ack = path/'worker'/'observer-ack.json'
    def observe():
        while not finished.is_set():
            try:
                # Check the marker before sampling so both counter reads follow
                # the end of measurement, even if export takes time.
                awaiting = handshake and ready.is_file() and not ack.exists()
                sample = snapshot(process.pid)
                samples.append(sample)
                if awaiting and all(k in sample for k in ('cpuTotal','cpuBusy','processTicks')):
                    save_new(ack, sample)
            except Exception as error: errors.append(str(error))
            finished.wait(1)
    with (path/'stdout.txt').open('x') as stdout,(path/'stderr.txt').open('x') as stderr:
        process=subprocess.Popen(command,cwd=path,stdout=stdout,stderr=stderr)
        save_new(path/'worker-process.json',dict(pid=process.pid,cgroup=text_file(f'/proc/{process.pid}/cgroup')))
        observer=threading.Thread(target=observe,daemon=True);observer.start()
        try:
            timeout=sum(config[k] for k in ('warmupMs','conditioningMs','measureMs'))/1000+120
            code=process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill();process.wait();code=-1
        except KeyboardInterrupt:
            interrupted=True;process.kill();process.wait();code=-1
        finally:
            finished.set();observer.join();samples.append(snapshot())
    save_new(path/'host.json',samples)
    result=summarize(path,spec,config,capability,code)
    result['warnings']+=['Observer error: '+e for e in errors]
    if handshake and result['status']=='COMPLETE':
        complete = observer_handoff_complete(path, samples, int(result['windows'][-1]['endNs']))
        result['observerHandoffComplete'] = complete
        if not complete:
            result['warnings'].append('Final observer sample unavailable')
    # Independent compressed-HDR decode occurs after worker exits.
    if result['status']=='COMPLETE':
        cp=os.pathsep.join(str(p) for p in sorted((HERE/'lib').glob('*.jar')))
        verification=capture([java,'-cp',cp,'TailCacheFocusedHdrVerify',str(path/'worker'),str(path/'hdr-endpoints.csv')])
        save_new(path/'hdr-verification.json',verification)
        try:
            require(verification.get('exitCode')==0,'Compressed HDR verification failed')
            rows=csv_rows(path/'hdr-endpoints.csv')
            require(sorted(pathlib.Path(row['path']).stem for row in rows)==sorted(result['latency']),
                    'Compressed HDR channels differ')
            for row in rows:
                ch=pathlib.Path(row['path']).stem
                stats=result['latency'][ch]
                require(int(row['count'])==stats['count'],'HDR total differs')
                for q,key in zip(QUANTILES,('p50Ns','p99Ns','p999Ns','p9999Ns','p99999Ns')):
                    if stats['count']: require(stats['percentiles'][str(q)]['ns']==int(row[key]),'HDR percentile differs')
        except (ValueError,OSError,KeyError) as error:
            result.update(status='FAILED',failure=str(error))
    if result['status']=='COMPLETE' and not spec.get('floor'):
        # Independent logical replay validates the actual phase counts and final versions.
        phases=';'.join(w['phase']+':'+w['operations'] for w in result['windows'])
        (path/'stream-audit-input.csv').write_text('label,seed,writeBps,residents,hotset,phases\n'+
            f'{spec["label"]},{spec["seed"]},{spec["writeBps"]},{config["residents"]},{spec["updateHotset"]},{phases}\n')
        verification=capture([java,'-cp',cp,'MechanismStreamAudit',str(path/'stream-audit-input.csv'),str(path/'stream-audit.csv')],
                             timeout=max(30,sum(int(w['operations']) for w in result['windows'])/1_000_000))
        save_new(path/'stream-verification.json',verification)
        try:
            require(verification.get('exitCode')==0,'Independent stream replay failed')
            audited=csv_rows(path/'stream-audit.csv')
            require([(w['phase'],int(w['writes'])) for w in result['windows']]==
                    [(w['phase'],int(w['writes'])) for w in audited[:-1]],'Independent phase write counts differ')
            require(audited[-1]['versionSha256']==result['integrity']['mutationVersionSha256'],'Independent mutation digest differs')
        except (ValueError,OSError,KeyError) as error:
            result.update(status='FAILED',failure=str(error))
    result['rawSha256']=inventory(path)
    save_new(path/'result.json',result)
    save_new(path/'seal.json',dict(resultSha256=sha(path/'result.json')))
    if interrupted:raise KeyboardInterrupt
    return result


def observer_handoff_complete(path, samples, measurement_end):
    worker = path/'worker'
    ack = worker/'observer-ack.json'
    if not ack.is_file() or (worker/'observer-timeout').exists():
        return False
    sample = load(ack)
    return (sample in samples and sample['startNs'] >= measurement_end
            and all(k in sample for k in ('cpuTotal','cpuBusy','processTicks')))


def retained(path, spec=None):
    seal=load(path/'seal.json')
    require(sha(path/'result.json')==seal['resultSha256'],'Retained result changed')
    result=load(path/'result.json')
    if spec is not None: require(result['spec']==spec,'Saved slot differs from schedule')
    require(result.get('rawSha256'),'Missing evidence inventory')
    verify_inventory(path,result['rawSha256'])
    require(set(inventory(path,('result.json','seal.json')))==set(result['rawSha256']), 'Unexpected retained slot files')
    return result


def verify_derivatives(path, result, config):
    """Offline reconstruction, independent of cached percentile/GC summaries."""
    if result['status']!='COMPLETE':return
    windows=csv_rows(path/'worker/windows.csv')
    require(windows==result['windows'],'Cached windows differ from raw')
    m=windows[-1];n=int(m['operations']);writes=int(m['writes'])
    if 'observerHandoffComplete' in result:
        handoff = observer_handoff_complete(path, load(path/'host.json'), int(m['endNs']))
        require(handoff == result['observerHandoffComplete'], 'Final observer handoff differs')
    if 'stallExport' in result:
        limit = int(properties(path/'worker/configuration.txt')['eventLimit'])
        require(stall_export(path/'worker', m, limit)==result['stallExport'], 'Cached stall export counts differ')
    spec=result['spec']
    expected=latency_counts(spec,n,writes)
    require(set(result['latency'])==set(expected),'Cached histogram channels differ from timing mode')
    if spec.get('splitWriteTiming'):
        actual = properties(path/'worker/configuration.txt')
        require(actual.get('splitWriteTiming')=='true'
                and int(actual.get('splitWriteSampleEvery',1))==spec.get('splitWriteSampleEvery',1),
                'Retained split timing mode or sample stride differs')
    bins={ch:histogram(path/'worker'/(ch+'-bins.csv'),count) for ch,count in expected.items()}
    for ch,values in bins.items():
        require(hist_stats(values,config)==result['latency'][ch],'Cached histogram statistics differ: '+ch)
    union=collections.Counter(dict(bins['read-service']));union.update(dict(bins['update-service']))
    require(dict(union)==dict(bins['service']),'Offline read/update union mismatch')
    parser=analysis_module()
    gc=parser.gc_summary(parser.parse_gc(path/'gc.log'),[(int(m['startNs']),int(m['endNs']))],n)
    require(gc==result['gc'],'Cached GC statistics differ')
    elapsed=(int(m['endNs'])-int(m['startNs']))/1e9
    for field,value in dict(workerAllocatedBytes=int(m['workerAllocatedBytes']),
        workerAllocatedBytesPerOperation=int(m['workerAllocatedBytes'])/n,compilerMs=int(m['compilerMs']),
        operationsPerSecond=n/elapsed,achievedChurnBytesPerSecond=int(m['churnPayloadBytes'])/elapsed).items():
        require(result[field]==value,'Cached measurement differs: '+field)


def readiness(config, out):
    require(shutil.disk_usage(out).free>=config['quality']['minDiskMiB']*1024**2,'Disk reserve unavailable; completed slots retained')
    snap=snapshot()
    if snap.get('MemAvailableKiB') is not None:
        require(snap['MemAvailableKiB']>=config['quality']['minAvailableMiB']*1024,'Available RAM below reserve')
    if snap.get('cgroupAvailableKiB') is not None:
        require(snap['cgroupAvailableKiB']>=config['quality']['minAvailableMiB']*1024,'Cgroup RAM below reserve')
    require(not power_disconnected(snap['externalPower']),'External power disconnected')


def same_resources(a, b):
    return all(a.get(k)==b.get(k) for k in ('id','cgroupLimits','cpuPolicy','clocksource','mountFingerprint'))


def controls(out, java, config, capability):
    """Two backends x floor/known-pause, independent of research observations."""
    root=out/'controls';root.mkdir(exist_ok=True)
    c=dict(config,purpose='diagnostic',residents=64,churnMiBPerSecond=0,warmupMs=1500,
           conditioningMs=100,measureMs=1000,primeCalls=0)
    rows=[]
    for backend in BACKENDS:
        for injected in (0,20):
            spec=dict(label=backend+'-'+str(injected),backend=backend,payloadBytes=256,liveMiB=0,
                      writeBps=500,updateHotset=64,qps=10000,seed=61700,floor=True,injectMs=injected)
            path=root/spec['label']
            r=retained(path,spec) if path.exists() else launch(path,spec,c,java,capability)
            require(r['status']=='COMPLETE','Failed/interrupted control retained: '+str(path))
            if injected:
                require(r['latency']['service']['maxUpperEquivalentNs']>=15000000 and
                        r['latency']['response']['percentiles']['99.9']['ns']>=1000000,'Known pause not observed')
            rows.append(r)
    return rows


def retry_plan(rows, observations, maximum):
    """Select by warnings alone, in frozen schedule order, at most once per seed/cell."""
    entries = []
    for a,b in zip(rows[::2], rows[1::2], strict=True):
        members = [observations.get(s['label']) for s in (a,b)]
        if not all(r and r['status']=='COMPLETE' for r in members):
            continue
        warnings = sorted({w for r in members for w in r['warnings']})
        if warnings and all(w in RETRYABLE_OBSERVER_WARNINGS or w.startswith('Observer error: ') for w in warnings):
            entries.append(dict(slots=[a,b], originalWarnings=warnings))
    return dict(eligiblePairs=len(entries),maximumPairs=maximum,selected=entries[:maximum])


def run(config, out, java_arg=None, *, host_locked=False, report_destination=None, split_qualified=False):
    validate(config);out=pathlib.Path(out).resolve()
    require(config['purpose']!='research' or split_qualified
            or not any(c.get('splitWriteTiming') for c in config['cells']),
            'Use a split-write timing suite to qualify instrumentation before research')
    require(HERE not in out.parents and out!=HERE,'Keep results outside the executable bundle')
    with (contextlib.nullcontext() if host_locked else host_lock()):
        bundle=bundle_identity();java=java_identity(java_arg)
        if not out.exists():out.mkdir(parents=True)
        host=host_identity(out)
        runfile=out/'run.json'
        if runfile.exists():
            frozen=load(runfile)
            require(frozen['config']==config and frozen['schedule']==schedule(config),'Frozen configuration changed')
            require(frozen['bundleId']==bundle and frozen['jdk']['id']==java['id'],'Frozen bundle/JDK changed')
            require(same_resources(frozen['host'],host),
                    'Different host/resources: create a separate run directory')
        else:
            require(not list(out.iterdir()),'Nonempty output without manifest: retained, not overwritten')
            save_new(runfile,dict(version=VERSION,startedUtc=now(),bundleId=bundle,jdk=java,host=host,
                                  config=config,schedule=schedule(config)))
        readiness(config,out)
        ergonomics=out/'jvm-ergonomics.json'
        if not ergonomics.exists():
            arguments=worker_command(java['executable'],config,schedule(config)[0],out)
            # A separate flags-only JVM, never inside any timed window.
            probe=capture(arguments[:arguments.index('-XX:AsyncLogBufferSize=2097152')]+['-XX:+PrintFlagsFinal','-version'])
            save_new(ergonomics,probe)
        require(load(ergonomics).get('exitCode')==0,'JVM ergonomics probe failed')
        qualification=out/'qualification.json'
        if not qualification.exists():
            # Retain the functional attempt before starting any controls.
            functional=out/'functional.json'
            if not functional.exists():
                cp=os.pathsep.join(str(p) for p in sorted((HERE/'lib').glob('*.jar')))
                save_new(functional,capture([java['executable'],*FLAGS,'-Xmx256m','-cp',cp,
                    'io.github.enixes.tailcache.workload.MechanismSelfTest']))
            require(load(functional).get('exitCode')==0,'Functional check failed; attempt retained')
            require(json.loads(load(functional)['stdout'].strip().splitlines()[-1])['passed'], 'Functional validation did not pass')
            cr=controls(out,java['executable'],config,host['capability'])
            save_new(qualification,dict(passed=True,functionalSha256=sha(functional),ergonomicsSha256=sha(ergonomics),controlResultSha256={
                r['spec']['label']:sha(out/'controls'/r['spec']['label']/'result.json') for r in cr},researchObservations=0))
        q=load(qualification)
        require(q['passed'] and sha(out/'functional.json')==q['functionalSha256'] and sha(ergonomics)==q['ergonomicsSha256'],
                'Qualification binding changed')
        require(set(q['controlResultSha256'])=={b+'-'+str(i) for b in BACKENDS for i in (0,20)},'Incomplete control qualification')
        for label,digest in q['controlResultSha256'].items():
            path=out/'controls'/label;require(sha(path/'result.json')==digest,'Control receipt changed');retained(path)
        def obtain(root, spec):
            require(bundle_identity()==bundle,'Bundle changed while running')
            # Check runtime bytes before every fresh or resumed slot.
            require(java_identity(java['executable'])['id']==java['id'],'JDK changed while running')
            path=root/spec['label']
            if path.exists():
                require((path/'result.json').exists(),'Interrupted slot retained; explicit new cohort required: '+str(path))
                return retained(path,spec)
            readiness(config,out)
            require(same_resources(host_identity(out),host), 'Host/resource settings changed during campaign')
            return launch(path,spec,config,java['executable'],host['capability'])

        slots=out/'slots';slots.mkdir(exist_ok=True)
        rows = schedule(config)
        initial = {}
        for index,spec in enumerate(rows):
            result=obtain(slots,spec)
            initial[spec['label']] = result
            print(f'{index+1}/{len(rows)} {spec["label"]}: {result["status"]}, {len(result["warnings"])} warnings',flush=True)
            # Failed pressure outcomes are retained; other scheduled slots may still run.
        if config.get('maxExternalRetryPairs',0):
            retries = retry_plan(rows,initial,config['maxExternalRetryPairs'])
            marker = out/'external-retry-plan.json'
            if marker.exists():
                require(load(marker)==retries,'Frozen external retry plan changed')
            else:
                save_new(marker,retries)
            retry_slots = out/'external-retry'
            retry_slots.mkdir(exist_ok=True)
            for entry in retries['selected']:
                for spec in entry['slots']:
                    result = obtain(retry_slots,spec)
                    print(f'Retry {spec["label"]}: {result["status"]}, {len(result["warnings"])} warnings',flush=True)
        return report(out, report_destination) if report_destination is not None else report(out)


def point_conclusions(config, summaries, results):
    points=[]
    for s in summaries:
        if s['channel'] not in ('service','response',*WRITE_CHANNELS):continue
        cell=config['cells'][s['cell']-1]
        if not cell['qps'] and s['channel']=='response':continue
        values=s['allUsablePairs'];n=values['n'];expected=len(config['seeds'])
        winner=('CHRONICLE_IN_MEMORY' if n==expected and values['chronicleWins']==n else
                'CAFFEINE' if n==expected and values['caffeineWins']==n else 'UNRESOLVED')
        by={}
        tail_flags=[]
        resolution_flags=[]
        for b in BACKENDS:
            rs=[r for r in results if r['status']=='COMPLETE' and r['spec']['cell']==s['cell'] and r['spec']['backend']==b]
            vs=[r['latency'][s['channel']]['percentiles'][str(s['quantile'])] for r in rs]
            by[b]=statistics.median(v['ns'] for v in vs if v['ns'] is not None) if any(v['ns'] is not None for v in vs) else None
            tail_flags += [v['tailSupportWarning'] for v in vs]
            if s['channel'] in WRITE_CHANNELS:
                resolution_flags += [not write_timer_resolved(r['latency'],str(s['quantile']),(s['channel'],)) for r in rs]
        if s['channel'] in WRITE_CHANNELS and (any(resolution_flags) or any(tail_flags)):
            winner='UNRESOLVED'
            conclusion='Clock floor or rare-tail support limits direction'
        else:
            conclusion=('All planned seed pairs agree' if winner!='UNRESOLVED'
                        else 'Mixed, missing or failed pairs; no resolved direction')
        points.append(dict(cell=s['cell'],inputs=cell,channel=s['channel'],quantile=s['quantile'],
            completePairDirectionsFavor=winner,medianForkQuantileNs=by,pairedSummary=values,
            cleanPairs=s['warningFreePairs']['n'],tailSupportWarning=any(tail_flags),
            conclusion=conclusion,
            limit='Descriptive finite-window result; not a significance test or universal threshold'))
    contrasts=[]
    for axis in ('liveMiB','payloadBytes','writeBps','updateHotset'):
        groups=collections.defaultdict(list)
        for point in points:
            if point['quantile'] not in (99,99.9,99.99,99.999):continue
            other={k:v for k,v in point['inputs'].items() if k!=axis}
            groups[(canonical(other),point['channel'],point['quantile'])].append(point)
        for (other,ch,q),ps in groups.items():
            ps.sort(key=lambda p:p['inputs'][axis])
            if len(ps)<2:continue
            brackets=[]
            for a,b in zip(ps,ps[1:]):
                if (a['completePairDirectionsFavor']!='UNRESOLVED' and b['completePairDirectionsFavor']!='UNRESOLVED'
                    and a['completePairDirectionsFavor']!=b['completePairDirectionsFavor']):
                    brackets.append(dict(fromValue=a['inputs'][axis],toValue=b['inputs'][axis],
                        fromBackend=a['completePairDirectionsFavor'],toBackend=b['completePairDirectionsFavor']))
            contrasts.append(dict(axis=axis,fixedInputs=json.loads(other),channel=ch,quantile=q,
                testedPoints=[dict(value=p['inputs'][axis],cell=p['cell'],direction=p['completePairDirectionsFavor'],
                                  cleanPairs=p['cleanPairs'],tailSupportWarning=p['tailSupportWarning']) for p in ps],
                observedRankingReversalBrackets=brackets,
                limit='No bracket is not proof of no crossover; warning/rare-tail limitations apply'))
    return points,contrasts


def paired_summary(values):
    if not values:return dict(n=0)
    logs=[math.log(v) for v in values]
    # Exact sign test: independent seed pairs only, ties excluded; descriptive, no multiplicity correction.
    wins=sum(v<1 for v in values);losses=sum(v>1 for v in values);n=wins+losses
    sign=min(1,2*sum(math.comb(n,k) for k in range(min(wins,losses)+1))/2**n) if n else 1
    ci=None
    if len(values)>=4:
        # Deterministic seed-block bootstrap; exploratory interval, not an extreme-tail guarantee.
        rng=random.Random(61791)
        samples=sorted(math.exp(statistics.mean(rng.choices(logs,k=len(logs)))) for _ in range(5000))
        ci=[samples[124],samples[4874]]
    return dict(n=len(values),chronicleWins=wins,caffeineWins=losses,ties=len(values)-n,
                medianRatio=statistics.median(values),geometricMeanRatio=math.exp(statistics.mean(logs)),
                minimumRatio=min(values),maximumRatio=max(values),logRatioSampleSd=statistics.stdev(logs) if len(logs)>1 else None,
                exploratoryPairedBootstrap95=ci,unadjustedTwoSidedSignP=sign,
                uncertainty='Independent seed pairs; descriptive range; bootstrap only for n>=4; no multiple-testing correction')


def variation(values):
    if not values:return dict(n=0)
    mean=statistics.mean(values);median=statistics.median(values)
    sd=statistics.stdev(values) if len(values)>1 else None
    return dict(n=len(values),median=median,mean=mean,minimum=min(values),maximum=max(values),
                sampleSd=sd,coefficientOfVariation=sd/mean if sd is not None and mean else None,
                medianAbsoluteDeviation=statistics.median(abs(v-median) for v in values))


def pair_result(a, b, by):
    members=[by.get(a['label']),by.get(b['label'])]
    good=all(r and r['status']=='COMPLETE' for r in members)
    p=dict(cell=a['cell'],block=a['block'],seed=a['seed'],labels=[a['label'],b['label']],usable=good,
           warningFree=good and not any(r['warnings'] for r in members),ratios={},invalidReason=None)
    if good:
        c,h=sorted(members,key=lambda r:BACKENDS.index(r['spec']['backend']))
        if a['qps'] and ([(w['phase'],w['operations'],w['writes']) for w in c['windows']] !=
                          [(w['phase'],w['operations'],w['writes']) for w in h['windows']] or
                          c['integrity']['mutationVersionSha256']!=h['integrity']['mutationVersionSha256']):
            p.update(usable=False,warningFree=False,invalidReason='Paired fixed-arrival write stream differs')
        else:
            channels=CHANNELS+WRITE_CHANNELS if a.get('splitWriteTiming') else CHANNELS
            for ch in channels:
                p['ratios'][ch]={str(q):(h['latency'][ch]['percentiles'][str(q)]['ns']/c['latency'][ch]['percentiles'][str(q)]['ns']
                    if c['latency'][ch]['count'] and h['latency'][ch]['count'] and
                    c['latency'][ch]['percentiles'][str(q)]['ns']>0 and h['latency'][ch]['percentiles'][str(q)]['ns']>0
                    else None) for q in QUANTILES}
    return p


def review_external_retries(out, frozen, original, pairs):
    marker = out/'external-retry-plan.json'
    if not marker.exists():
        return None
    config = frozen['config']
    design = retry_plan(frozen['schedule'], original, config.get('maxExternalRetryPairs',0))
    require(load(marker)==design,'Retained external retry plan differs')
    attempts = []
    clean = [dict(p, source='original') for p in pairs if p['warningFree']]
    for entry in design['selected']:
        a,b = entry['slots']
        retry_results = {}
        for spec in (a,b):
            path = out/'external-retry'/spec['label']
            if (path/'result.json').exists():
                result = retained(path,spec)
                verify_derivatives(path,result,config)
                retry_results[spec['label']] = result
        attempt = pair_result(a,b,retry_results)
        attempts.append(dict(pair=attempt,originalWarnings=entry['originalWarnings'],
                             warnings={label:r['warnings'] for label,r in retry_results.items()},
                             statuses={label:r['status'] for label,r in retry_results.items()}))
        if attempt['warningFree']:
            clean.append(dict(attempt, source='external-retry'))
    return dict(eligiblePairs=design['eligiblePairs'], maximumPairs=design['maximumPairs'],
                attemptedPairs=len(attempts), recoveredCleanPairs=sum(p['source']=='external-retry' for p in clean),
                cleanPairs=len(clean), attempts=attempts, cleanSensitivityPairs=clean)


def report(out, destination=None):
    out=pathlib.Path(out).resolve();frozen=load(out/'run.json');config=validate(frozen['config'])
    require(frozen['schedule']==schedule(config),'Manifest schedule differs')
    results=[];missing=[]
    for spec in frozen['schedule']:
        path=out/'slots'/spec['label']
        if (path/'result.json').exists():
            r=retained(path,spec);verify_derivatives(path,r,config);results.append(r)
        else:missing.append(spec['label'])
    by={r['spec']['label']:r for r in results};pairs=[];flat=[]
    for a,b in zip(frozen['schedule'][::2], frozen['schedule'][1::2], strict=True):
        pairs.append(pair_result(a,b,by))
    retry_review = review_external_retries(out, frozen, by, pairs)
    summaries=[]
    for cell in range(1,len(config['cells'])+1):
        channels=CHANNELS+WRITE_CHANNELS if config['cells'][cell-1].get('splitWriteTiming') else CHANNELS
        for ch in channels:
            for q in QUANTILES:
                ps=[p for p in pairs if p['cell']==cell and p['usable'] and p['ratios'][ch][str(q)] is not None]
                backend_variation={b:variation([r['latency'][ch]['percentiles'][str(q)]['ns'] for r in results
                    if r['status']=='COMPLETE' and r['spec']['cell']==cell and r['spec']['backend']==b
                    and r['latency'][ch]['percentiles'][str(q)]['ns'] is not None]) for b in BACKENDS}
                summaries.append(dict(cell=cell,channel=ch,quantile=q,backendForkVariationNs=backend_variation,
                    allUsablePairs=paired_summary([p['ratios'][ch][str(q)] for p in ps]),
                    warningFreePairs=paired_summary([p['ratios'][ch][str(q)] for p in ps if p['warningFree']])))
    for r in results:
        if r['status']!='COMPLETE':continue
        for ch in r['latency']:
            for q in QUANTILES:
                t=r['latency'][ch]['percentiles'][str(q)]
                flat.append(dict(label=r['spec']['label'],cell=r['spec']['cell'],seed=r['spec']['seed'],backend=r['spec']['backend'],
                    channel=ch,quantile=q,ns=t['ns'],count=r['latency'][ch]['count'],expectedBeyond=t['expectedBeyondQuantile'],
                    tailSupportWarning=t['tailSupportWarning'],warnings='; '.join(r['warnings'])))
    complete=not missing
    points,contrasts=point_conclusions(config,summaries,results)
    timing_controls=[]
    if (out/'qualification.json').exists():
        qualification=load(out/'qualification.json')
        for label,digest in qualification['controlResultSha256'].items():
            path=out/'controls'/label
            require(sha(path/'result.json')==digest,'Control changed before analysis')
            r=retained(path)
            timing_controls.append(dict(label=label,latency=r['latency'],warnings=r['warnings']))
    reportdata=dict(version=VERSION,runSha256=sha(out/'run.json'),bundleId=frozen['bundleId'],hostId=frozen['host']['id'],
        purpose=config['purpose'],collectionComplete=complete,allSlotsSuccessful=complete and all(r['status']=='COMPLETE' for r in results),
        scheduled=len(frozen['schedule']),completed=sum(r['status']=='COMPLETE' for r in results),failed=sum(r['status']!='COMPLETE' for r in results),
        missing=missing,pairs=pairs,summaries=summaries,observations=results,retryReview=retry_review,
        pointConclusions=points,contrasts=contrasts,
        timingControls=timing_controls,
        researchQuestionMap=dict(RQ1='Inspect liveMiB contrasts in service p99/p99.9 for each payload and pacing mode',
            RQ2='Compare payloadBytes contrasts and pressure brackets at otherwise matched inputs',
            mechanism='Inspect writeBps and updateHotset contrasts in scheduled response; separate from service'),
        claims='Per-cell paired backend comparison only; no automatic universal crossover claim. Failure/quality/tail support remain explicit.')
    destination=pathlib.Path(destination).resolve() if destination else out/('analysis-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    destination.mkdir(parents=True,exist_ok=False)
    save_new(destination/'results.json',reportdata)
    save_new(destination/'point-conclusions.json',dict(points=points,contrasts=contrasts))
    if flat:
        with (destination/'percentiles.csv').open('x',newline='') as stream:
            w=csv.DictWriter(stream,list(flat[0]));w.writeheader();w.writerows(flat)
    lines=['# Portable experiment results','',f'{reportdata["completed"]}/{reportdata["scheduled"]} successful slots; {reportdata["failed"]} failed; {len(missing)} missing.',
           '', 'Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.',
           'Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.', '',
           '| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |',
           '|---|---|---:|---:|---:|---|---:|']
    for s in summaries:
        if s['channel'] not in ('service','response',*WRITE_CHANNELS) or s['quantile']==50:continue
        v=s['allUsablePairs'];n=v['n']
        lines.append(f'| {s["cell"]} | {s["channel"]} | {s["quantile"]} | {n} | '+
                     (f'{v["medianRatio"]:.4g} | {v["minimumRatio"]:.4g}–{v["maximumRatio"]:.4g}' if n else '— | —')+
                     f' | {s["warningFreePairs"]["n"]} |')
    lines+=['','## Point conclusions','',
            '| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |',
            '|---|---|---:|---:|---:|---|---|']
    for point in points:
        if point['quantile']==50:continue
        med=point['medianForkQuantileNs']
        lines.append(f'| {point["cell"]} | {point["channel"]} | {point["quantile"]} | {med[BACKENDS[0]]} | {med[BACKENDS[1]]} | {point["completePairDirectionsFavor"]} | {point["tailSupportWarning"]} |')
    lines+=['','## Matched-input contrasts','',
            'These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.']
    for contrast in contrasts:
        if contrast['observedRankingReversalBrackets']:
            lines.append('- '+json.dumps(contrast,sort_keys=True))
    if not any(c['observedRankingReversalBrackets'] for c in contrasts):
        lines.append('No adjacent fully observed ranking reversal is resolved in this run.')
    if retry_review is not None:
        first_pass = sum(p['warningFree'] for p in pairs)
        lines += ['', '## External-noise retries', '',
                  f"{retry_review['eligiblePairs']} eligible pairs. "
                  f"{retry_review['attemptedPairs']} selected out of a cap of {retry_review['maximumPairs']}.",
                  f"First-pass warning-free pairs: {first_pass}. "
                  f"Recovered warning-free pairs: {retry_review['recoveredCleanPairs']}. "
                  f"Clean sensitivity view: {retry_review['cleanPairs']} pairs.",
                  'Original results above are preserved. The clean sensitivity view uses at most one attempt per seed and cell.']
    (destination/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(report=str(destination),collectionComplete=complete,successful=reportdata['completed'],failed=reportdata['failed'])),flush=True)
    return reportdata


def build_stage(root, *, checks=False, env=None, log=None):
    wrapper = [str(root/'gradlew.bat')] if os.name=='nt' else ['sh', str(root/'gradlew')]
    tasks = ['test'] if checks else []
    command = [*wrapper, '--no-daemon', *tasks, 'tailCachePortableStage']
    completed = subprocess.run(command, cwd=root, env=env, stdout=log,
                               stderr=subprocess.STDOUT if log is not None else None)
    require(completed.returncode==0, 'Gradle tests/build failed'+(f'. See {log.name}' if log else ''))
    return root/'build/portable/stage'


def stage_manifest(root, stage):
    files = inventory(stage, ('bundle.json',))
    return dict(version=VERSION, id=hashlib.sha256(canonical(files)).hexdigest(), files=files,
                sourceRevision=capture(['git','-C',str(root),'rev-parse','HEAD']),
                sourceStatus=capture(['git','-C',str(root),'status','--short']))


def pack(destination):
    root = HERE.parent
    require((root/'gradlew').exists(), 'Build from the source checkout')
    destination=pathlib.Path(destination).resolve()
    require(not destination.exists(),'Refusing existing ZIP')
    require(root/'build/portable/stage' not in destination.parents, 'ZIP cannot be inside the staging directory')
    stage = build_stage(root)
    manifest = stage_manifest(root, stage)
    if (stage/'bundle.json').exists():
        old=load(stage/'bundle.json')
        require(old['files']==manifest['files'] and old['version']==VERSION,'Stale staging inventory: rebuild staging first')
    else:
        save_new(stage/'bundle.json',manifest)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(stage.rglob('*')):
            if p.is_file():archive.write(p,'tailcache-portable/'+p.relative_to(stage).as_posix())
    print(json.dumps(dict(bundle=str(destination),sha256=sha(destination),id=manifest['id'])),flush=True)


def save_junit_reports(directory, setup):
    reports = sorted(directory.glob('TEST-*.xml'))
    require(reports, 'Gradle JUnit XML results are missing. Run the Gradle test task.')
    checks = [ET.parse(report).getroot() for report in reports]
    require(all(check.tag=='testsuite' for check in checks), 'Invalid Gradle JUnit XML results')
    executed = sum(int(check.get('tests', '0'))-int(check.get('skipped', '0')) for check in checks)
    failed = sum(int(check.get('failures', '0'))+int(check.get('errors', '0')) for check in checks)
    require(executed>0 and failed==0, 'Gradle JUnit tests must pass before collection')
    for report in reports:
        shutil.copyfile(report, setup/report.name)


def checkout_bundle(out, java, gradle_stage=None, gradle_test_results=None):
    """Build and test once, then preserve the exact bundle alongside the results."""
    root = HERE.parent
    stage = gradle_stage or root/'build/portable/stage'
    require(stage not in (out, *out.parents), 'Keep results outside the Gradle staging directory')
    bundle = out/'bundle'
    with host_lock():
        if bundle.exists():
            for packaged, source in (('tailcache.py', 'tailcache_portable.py'), ('analysis.py', 'tailcache12_analysis.py')):
                require(sha(bundle/packaged)==sha(HERE/source),
                        'Checkout collector changed. Resume with the frozen bundle or select a new output directory.')
            return bundle
        require(not (out/'suite.json').exists(), 'Retained suite bundle is missing')
        out.mkdir(parents=True, exist_ok=True)
        setup = pathlib.Path(tempfile.mkdtemp(prefix='setup-', dir=out))
        print(f'Collecting checkout test evidence in {setup}', flush=True)
        # The checks exercise lock contention. Give them an isolated lock path
        # while the real host lock protects setup from overlapping collection.
        with tempfile.TemporaryDirectory(dir=setup) as test_temp, (setup/'python.log').open('x') as log:
            command = [sys.executable, '-B', '-m', 'unittest', 'discover',
                       '-s', str(HERE), '-p', 'test_tailcache_portable.py']
            env = dict(os.environ, TMPDIR=test_temp)
            status = subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
        require(status==0, f'Portable Python checks failed. See {setup/"python.log"}')
        if gradle_stage is None:
            env = dict(os.environ, JAVA_HOME=java['home'])
            with (setup/'gradle.log').open('x') as log:
                stage = build_stage(root, checks=True, env=env, log=log)
        else:
            save_junit_reports(gradle_test_results, setup)
        manifest = stage_manifest(root, stage)
        manifest['checkoutChecks'] = {
            'jdkId': java['id'],
            'logs': {f.relative_to(out).as_posix(): sha(f) for f in sorted(setup.iterdir())},
        }
        with tempfile.TemporaryDirectory(prefix='.bundle-', dir=out) as temporary:
            snapshot_dir = pathlib.Path(temporary)/'bundle'
            shutil.copytree(stage, snapshot_dir, ignore=shutil.ignore_patterns('bundle.json', '__pycache__'))
            verify_inventory(snapshot_dir, manifest['files'])
            save_new(snapshot_dir/'bundle.json', manifest)
            snapshot_dir.rename(bundle)
    return bundle


def qualify_write_timing(result):
    limits = WRITE_PILOT_LIMITS
    failures = []
    changes = []
    ranking = []
    if not result['allSlotsSuccessful'] or any(not p['warningFree'] for p in result['pairs']):
        failures.append('All pilot pairs must be complete and warning-free')
        return dict(passed=False, failures=failures, changes=changes, backendRatioDrift=ranking)

    def endpoints(row):
        return dict(operationsPerSecond=row['operationsPerSecond'],
                    serviceP999=row['latency']['service']['percentiles']['99.9']['ns'],
                    updateServiceP999=row['latency']['update-service']['percentiles']['99.9']['ns'])

    groups = collections.defaultdict(dict)
    for observation in result['observations']:
        spec = observation['spec']
        groups[spec['seed']][spec['backend'],spec.get('splitWriteTiming',False)] = observation
    for seed, arms in sorted(groups.items()):
        if set(arms) != {(b, split) for b in BACKENDS for split in (False, True)}:
            failures.append(f'Seed {seed}: incomplete split-timing comparison')
            continue
        service_ratio = {}
        for backend in BACKENDS:
            off = endpoints(arms[backend,False])
            on = endpoints(arms[backend,True])
            if any(value is None or value <= 0 for value in (*off.values(),*on.values())):
                failures.append(f'Seed {seed} {backend}: incomplete timing endpoints')
                continue
            shifts = {key:on[key]/before-1 for key,before in off.items()}
            service_ratio[backend] = on['serviceP999']/off['serviceP999']
            changes.append(dict(seed=seed,backend=backend,relativeChange=shifts))
            for endpoint, change in shifts.items():
                if abs(change)>limits[endpoint]:
                    failures.append(f'Seed {seed} {backend}: {endpoint} shifted by {change:+.1%}')
        if len(service_ratio)==len(BACKENDS):
            drift=service_ratio[BACKENDS[1]]/service_ratio[BACKENDS[0]]-1
            ranking.append(dict(seed=seed,relativeChange=drift))
            if abs(drift)>limits['backendRatioDrift']:
                failures.append(f'Seed {seed}: Chronicle/Caffeine service p99.9 ratio shifted by {drift:+.1%}')
    require(groups,'Missing split-timing pilot observations')
    return dict(passed=not failures,failures=failures,changes=changes,backendRatioDrift=ranking)


def collect_suite(suite, out, java_arg):
    out = pathlib.Path(out).resolve()
    require(out!=HERE and HERE not in out.parents, 'Keep results outside the executable bundle')
    config = suite_plan(HERE/'configs', suite)
    with host_lock():
        bundle_id = bundle_identity()
        java = java_identity(java_arg)
        out.mkdir(parents=True, exist_ok=True)
        host = host_identity(out)
        checkout_checks = load(HERE/'bundle.json').get('checkoutChecks') if HERE==out/'bundle' else None
        if checkout_checks:
            require(checkout_checks['jdkId']==java['id'], 'Checkout checks used a different JDK')
            verify_inventory(out, checkout_checks['logs'])
        manifest = out/'suite.json'
        if manifest.exists():
            frozen = load(manifest)
            require(frozen['plan']==config, 'Frozen suite changed. Choose a new output directory.')
            require(frozen['bundleId']==bundle_id and frozen['jdkId']==java['id'], 'Frozen bundle/JDK changed')
            require(same_resources(frozen['host'],host), 'Frozen host resources changed')
            require(frozen['checkoutChecks']==checkout_checks, 'Checkout test evidence changed')
        else:
            require(not any((out/phase).exists() for phase in config['phases']),
                    'Phase directory already exists without a suite manifest')
            save_new(manifest, dict(version=VERSION, startedUtc=now(), plan=config, bundleId=bundle_id,
                                    jdkId=java['id'], host=host, checkoutChecks=checkout_checks))
        print(f'{suite}: {config["researchJvms"]} research JVMs, {config["diagnosticJvms"]} diagnostic JVMs, '
              f'{config["nominalWorkloadMinutes"]:.1f} nominal minutes plus setup and verification', flush=True)
        reports = pathlib.Path(tempfile.mkdtemp(prefix='suite-analysis-', dir=out))
        phases = {}
        for phase, design in config['phases'].items():
            require(same_resources(host,host_identity(out)), 'Host resources changed between suite phases')
            print(f'Running {phase}', flush=True)
            result = run(design['config'], out/phase, java['executable'],
                         host_locked=True, report_destination=reports/phase,
                         split_qualified=phases.get('write-timing-pilot',{}).get('passed',False))
            passed = result['allSlotsSuccessful'] and all(pair['usable'] for pair in result['pairs'])
            if phase == 'write-timing-pilot':
                audit = qualify_write_timing(result)
                save_new(reports/phase/'write-timing-qualification.json', audit)
                if not audit['passed']:
                    print('Write timing qualification failed: '+'; '.join(audit['failures']),flush=True)
                passed = passed and audit['passed']
            phases[phase] = dict(passed=passed, scheduled=result['scheduled'], completed=result['completed'],
                                 failed=result['failed'], usablePairs=sum(p['usable'] for p in result['pairs']),
                                 plannedPairs=len(result['pairs']), warningFreePairs=sum(p['warningFree'] for p in result['pairs']),
                                 report=f'{phase}/RESULTS.md', pointConclusions=f'{phase}/point-conclusions.json',
                                 resultsSha256=sha(reports/phase/'results.json'))
            if not passed:
                break
        passed = len(phases)==len(config['phases']) and all(phase['passed'] for phase in phases.values())
        save_new(reports/'suite-results.json', dict(passed=passed, manifestSha256=sha(manifest), phases=phases,
                                                   researchViews=config['researchViews']))
        lines = ['# TailCache reproduction', '',
                 '| Phase | Successful JVMs | Usable pairs | Warning-free pairs | Report |',
                 '|---|---:|---:|---:|---|']
        for phase, result in phases.items():
            lines.append(f'| {phase} | {result["completed"]}/{result["scheduled"]} | '
                         f'{result["usablePairs"]}/{result["plannedPairs"]} | {result["warningFreePairs"]} | '
                         f'[Results]({result["report"]}) |')
        if 'write-timing-pilot' in phases:
            lines.extend(['', '[Split write timing qualification](write-timing-pilot/write-timing-qualification.json)'])
        if config['researchViews']:
            lines.extend(['', 'Research cell numbers by profile', ''])
            for name, cells in config['researchViews'].items():
                lines.append(f'- {name} — '+', '.join(map(str,cells)))
        with (reports/'SUMMARY.md').open('x', encoding='utf-8') as stream:
            stream.write('\n'.join(lines)+'\n')
        print(f'Suite summary: {reports/"SUMMARY.md"}', flush=True)
        require(passed, 'A phase failed collection or qualification. See the suite summary.')


def reproduce(suite, out, java_arg, gradle_stage=None, gradle_test_results=None):
    out = pathlib.Path(out).resolve()
    if (HERE/'bundle.json').exists():
        collect_suite(suite, out, java_arg)
        return 0
    java = java_identity(java_arg)
    bundle = checkout_bundle(out, java, gradle_stage, gradle_test_results)
    command = [sys.executable, str(bundle/'tailcache.py'), 'reproduce', '--suite', suite,
               '--out', str(out), '--java', java['executable']]
    return subprocess.run(command).returncode


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    build=sub.add_parser('pack');build.add_argument('--out',required=True)
    for name in ('plan','run'):
        cmd=sub.add_parser(name);cmd.add_argument('--config',required=True)
        if name=='run':cmd.add_argument('--out',required=True);cmd.add_argument('--java')
    doctor=sub.add_parser('doctor');doctor.add_argument('--java')
    analyze=sub.add_parser('analyze');analyze.add_argument('--run',required=True);analyze.add_argument('--out')
    suite = sub.add_parser('reproduce', help='Build, check and collect a reproducible suite')
    suite.add_argument('--suite', choices=SUITES, default='all')
    suite.add_argument('--out', help='New or existing suite directory')
    suite.add_argument('--java')
    suite.add_argument('--gradle-stage', type=pathlib.Path, help=argparse.SUPPRESS)
    suite.add_argument('--gradle-test-results', type=pathlib.Path, help=argparse.SUPPRESS)
    suite.add_argument('--plan', action='store_true', help='Print the frozen design without building or running')
    args=p.parse_args()
    if args.command=='pack':pack(args.out)
    elif args.command=='plan':print(json.dumps(plan(load(args.config)),indent=2))
    elif args.command=='doctor':print(json.dumps(dict(bundleId=bundle_identity(),jdk=java_identity(args.java),host=host_identity(HERE)),indent=2))
    elif args.command=='run':run(load(args.config),args.out,args.java)
    elif args.command=='reproduce':
        if args.plan:
            configs = HERE/'configs' if (HERE/'bundle.json').exists() else HERE.parent/'experiments/portable'
            print(json.dumps(suite_plan(configs, args.suite), indent=2))
        else:
            require(args.out, 'reproduce requires --out unless --plan is used')
            require(bool(args.gradle_stage)==bool(args.gradle_test_results),
                    'Gradle stage and test results must be supplied together')
            return reproduce(args.suite, args.out, args.java, args.gradle_stage, args.gradle_test_results)
    else:report(args.run,args.out)


if __name__=='__main__':
    try:sys.exit(main())
    except KeyboardInterrupt:
        print('Interrupted. Retained evidence is in the output directory.',file=sys.stderr);sys.exit(130)
    except (ValueError,OSError,KeyError,ET.ParseError) as error:
        print('STOPPED: '+str(error),file=sys.stderr);sys.exit(2)
