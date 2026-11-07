"""Worker-only diagnostic recording checks and bounded streaming JDK JSON export."""
import hashlib
import datetime
import json
import math
import re
import subprocess


def epoch_ns(value):
    match = re.fullmatch(r'(.+T\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?([+-]\d\d:\d\d|Z)', value)
    if not match: raise ValueError('Unsupported JFR event timestamp')
    base = datetime.datetime.fromisoformat(match[1] + match[3].replace('Z', '+00:00'))
    return int(base.timestamp()) * 10**9 + int((match[2] or '').ljust(9, '0'))


def gc_clock_alignment(events, pauses):
    indexed = {int(p['gcId']): p for p in pauses if p['kind'].startswith(('Pause Young', 'Pause Full'))}
    anchors = []
    seen = set()
    for event in events:
        if event['type'] != 'jdk.GarbageCollection': continue
        data = event['values']; gc = indexed.get(data['gcId'])
        if gc is None: continue
        if data['gcId'] in seen: raise ValueError('Ambiguous recording GC identity')
        seen.add(data['gcId'])
        wall = epoch_ns(data['startTime'])
        anchors.append(dict(gcId=data['gcId'],wallStartNs=wall,monotonicStartNs=gc['startNs'],
                            offsetNs=wall-gc['startNs']))
    if len(anchors) < 3: raise ValueError('Insufficient independent recording/raw-GC clock anchors')
    anchors.sort(key=lambda a:a['monotonicStartNs'])
    wall0,mono0=anchors[0]['wallStartNs'],anchors[0]['monotonicStartNs']
    pairs=[(a['wallStartNs']-wall0,a['monotonicStartNs']-mono0) for a in anchors]
    train=pairs[::2]
    xbar=sum(x for x,y in train)/len(train);ybar=sum(y for x,y in train)/len(train)
    denominator=sum((x-xbar)**2 for x,y in train)
    if denominator<=0:raise ValueError('Degenerate recording/raw-GC clock anchors')
    slope=sum((x-xbar)*(y-ybar) for x,y in train)/denominator
    intercept=ybar-slope*xbar
    if not math.isfinite(slope) or slope<=0 or abs(slope-1)>.01:
        raise ValueError('Invalid or excessive recording clock-rate correction')
    residuals=[abs(y-(slope*x+intercept)) for x,y in pairs]
    residual=max(residuals)
    if residual > 2_000_000: raise ValueError('Recording/raw-GC clock residual exceeded2ms')
    return dict(model='gc-clock-affine-v1',wallOriginNs=wall0,monotonicOriginNs=mono0,
                slope=slope,interceptNs=intercept,relativeRateCorrectionPpm=(slope-1)*1e6,
                maximumAnchorResidualNs=residual,maximumHeldOutResidualNs=max(residuals[1::2]),
                training='alternating GC anchors; all remaining anchors held out',discardedAnchors=0,anchors=anchors)


def wall_to_monotonic(wall_ns,clock):
    return clock['monotonicOriginNs']+round(clock['slope']*(wall_ns-clock['wallOriginNs'])+clock['interceptNs'])


def verify_metadata(events, worker_pid, worker_main, pauses, windows, runtime_identity=None):
    info = [e['values'] for e in events if e['type'] == 'jdk.JVMInformation']
    shutdown = [e['values'] for e in events if e['type'] == 'jdk.Shutdown']
    if (not info or not shutdown or any(e.get('pid') != worker_pid or worker_main not in e.get('javaArguments', '')
                                       for e in info)):
        raise ValueError('Missing/wrong-worker JVM identity or incomplete recording shutdown')
    if any(e['type'] == 'jdk.DataLoss' for e in events):
        raise ValueError('Recording reported data loss')
    if runtime_identity and any(e.get('jvmName')!=runtime_identity['vmName']
            or '('+runtime_identity['vmVersion']+')' not in e.get('jvmVersion','') for e in info):
        raise ValueError('Recording JVM build differs from the actual worker controls')
    clock=gc_clock_alignment(events,pauses)
    start = min(wall_to_monotonic(epoch_ns(e['startTime']),clock) for e in info)
    end = max(wall_to_monotonic(epoch_ns(e['startTime']),clock) for e in shutdown)
    if start > min(a for a,b in windows)-60*10**9 or end < max(b for a,b in windows):
        raise ValueError('Recording does not cover preparation and complete analysed windows')
    return dict(workerPid=worker_pid,workerMain=worker_main,**clock,recordingStartNs=start,recordingEndNs=end,
                dataLossEvents=0,metadataPass=True)


def validate_instrumentation(jvm_args, inputs, diagnostic=False):
    text = jvm_args if isinstance(jvm_args, str) else ' '.join(jvm_args)
    count = text.count('-XX:StartFlightRecording=')
    declared = inputs.get('FlightRecorder') == 'true' or inputs.get('DiagnosticOnly') == 'true'
    if not diagnostic:
        if count or declared or '-XX:FlightRecorderOptions=' in text:
            raise ValueError('Flight Recorder diagnostics cannot supply ordinary endpoints')
        return
    if count != 1 or inputs.get('FlightRecorder') != 'true' or inputs.get('DiagnosticOnly') != 'true':
        raise ValueError('Explicit worker-only diagnostic recording controls are missing')
    if text.count('-XX:FlightRecorderOptions=maxchunksize=256m,stackdepth=64')!=1:
        raise ValueError('Profile chunk/stack controls differ from the declaration')


def recording_file(directory, settings_sha256):
    paths = list((directory / 'jfr').glob('*'))
    if (len(paths) != 1 or paths[0].name != 'worker.jfr' or paths[0].is_symlink()
            or not paths[0].is_file() or paths[0].stat().st_size == 0):
        raise ValueError('Missing, multiple or unexpected worker recording')
    settings = directory / 'flight-recorder.jfc'
    if settings.is_symlink() or hashlib.sha256(settings.read_bytes()).hexdigest() != settings_sha256:
        raise ValueError('Actual worker recording settings changed')
    return paths[0]


def event_stream(stream, chunk_chars=65536, maximum_event_chars=4 * 1024 * 1024):
    """Read the pinned JDK's JSON envelope one event at a time, with hard bounds."""
    decoder = json.JSONDecoder()
    buffer = ''
    eof = False
    def read_more():
        nonlocal buffer, eof
        chunk = stream.read(chunk_chars)
        if chunk: buffer += chunk
        else: eof = True
        if len(buffer) > maximum_event_chars:
            raise ValueError('JFR JSON event exceeded the declared streaming bound')
    while True:
        match = re.match(r'\s*\{\s*"recording"\s*:\s*\{\s*"events"\s*:\s*\[', buffer)
        if match:
            buffer = buffer[match.end():]
            break
        if eof or len(buffer) > 4096:
            raise ValueError('Unexpected or truncated JDK recording JSON envelope')
        read_more()
    need_comma = False
    after_comma = False
    while True:
        buffer = buffer.lstrip()
        if not buffer:
            if eof: raise ValueError('Truncated recording event list')
            read_more(); continue
        if buffer.startswith(']'):
            if after_comma: raise ValueError('Trailing recording event separator')
            while not eof: read_more()
            if not re.fullmatch(r'\]\s*\}\s*\}\s*', buffer):
                raise ValueError('Unexpected recording JSON trailer')
            return
        if need_comma:
            if not buffer.startswith(','): raise ValueError('Missing recording event separator')
            buffer = buffer[1:].lstrip()
            need_comma = False
            after_comma = True
            if not buffer:
                if eof: raise ValueError('Truncated recording event')
                read_more(); continue
        try:
            event, end = decoder.raw_decode(buffer)
        except json.JSONDecodeError as error:
            if eof: raise ValueError('Malformed/truncated recording event') from error
            read_more(); continue
        if (not isinstance(event, dict) or set(event) != {'type', 'values'}
                or not isinstance(event['type'], str) or not isinstance(event['values'], dict)):
            raise ValueError('Unexpected JDK recording event shape')
        buffer = buffer[end:]
        need_comma = True
        after_comma = False
        yield event


def print_events(jfr, path, event_names, stderr_path):
    command = [str(jfr), 'print', '--json', '--events', ','.join(event_names), '--stack-depth', '64', str(path)]
    with stderr_path.open('x') as stderr:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr, text=True, encoding='utf-8')
        try:
            yield from event_stream(process.stdout)
            if process.wait(timeout=30):
                raise ValueError('JDK recording export failed; retained stderr explains the failure')
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)


def verify_single_chunk(jfr,path,destination):
    command=[str(jfr),'summary',str(path)]
    result=subprocess.run(command,capture_output=True,text=True,timeout=60)
    with (destination/'recording-summary.txt').open('x') as stream:stream.write(result.stdout)
    with (destination/'recording-summary.stderr').open('x') as stream:stream.write(result.stderr)
    counts=re.findall(r'^\s*Chunks:\s*(\d+)\s*$',result.stdout,re.M)
    if result.returncode or counts!=['1']:
        raise ValueError('Recording must contain exactly one validated clock chunk')
    return dict(chunks=1,summaryCommand=command)
