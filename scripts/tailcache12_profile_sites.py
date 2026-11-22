#!/usr/bin/env python3
"""Stream retained worker JFR stacks; descriptive diagnostic only, never latency evidence."""
import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import subprocess

from tailcache12 import file_sha
from tailcache12_jfr import epoch_ns, print_events, wall_to_monotonic

EVENTS = ('jdk.ExecutionSample', 'jdk.NativeMethodSample',
          'jdk.ObjectAllocationInNewTLAB', 'jdk.ObjectAllocationOutsideTLAB')
HELPER = Path(__file__).parent/'java/TailCache12JfrExport.java'


def compact_events(java,recording,stderr_path):
    with stderr_path.open('x') as stderr:
        process=subprocess.Popen([str(java),'-Xmx256m',str(HELPER),str(recording)],
            stdout=subprocess.PIPE,stderr=stderr,text=True,encoding='utf-8')
        try:
            while True:
                line=process.stdout.readline(4*1024*1024+1)
                if not line:break
                if len(line)>4*1024*1024 or not line.endswith('\n'):
                    raise ValueError('Oversized/truncated compact profile event')
                event=json.loads(line)
                if set(event)!={'type','values'} or event['type'] not in EVENTS:
                    raise ValueError('Unexpected compact profile event')
                yield event
            if process.wait(timeout=30):raise ValueError('Compact profile export failed; retained stderr')
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


class Phases:
    def __init__(self, windows, uncertainty_ns):
        self.windows = sorted(windows, key=lambda w: w['startNs'])
        if not self.windows or any(w['endNs'] <= w['startNs'] for w in self.windows):
            raise ValueError('Missing/invalid phase intervals')
        if any(a['endNs'] > b['startNs'] for a,b in zip(self.windows,self.windows[1:])):
            raise ValueError('Overlapping phase intervals')
        self.starts = [w['startNs'] for w in self.windows]
        self.boundaries = sorted({w[k] for w in self.windows for k in ('startNs','endNs')})
        self.uncertainty = math.ceil(uncertainty_ns)

    def at(self, ns):
        pos = bisect_right(self.starts, ns)-1
        phase = self.windows[pos]['phase'] if pos >= 0 and ns < self.windows[pos]['endNs'] else 'BETWEEN_OR_SETUP_TEARDOWN'
        b = bisect_right(self.boundaries, ns)
        ambiguous = any(abs(ns-self.boundaries[i]) <= self.uncertainty
                        for i in (b-1,b) if 0 <= i < len(self.boundaries))
        return phase, ambiguous


def thread_kind(thread, worker):
    if thread is None: return 'MISSING_THREAD'
    java = thread.get('javaThreadId') == int(worker['javaThreadId'])
    native = thread.get('osThreadId') == int(worker['osThreadId'])
    if java != native: raise ValueError('Conflicting actual worker Java/native thread identity')
    if java and thread.get('javaName') != worker['javaThreadName']:
        raise ValueError('Worker thread name differs from marker')
    return 'WORKER' if java else 'OTHER_THREAD'


def frame_name(frame):
    method = frame['method']
    return (method['type']['name']+'.'+method['name']+method['descriptor']+
            ':'+str(frame['lineNumber'])+'@'+str(frame['bytecodeIndex'])+' ['+frame['type']+']')


def summarize(events, row):
    phases = Phases(row['phaseWindows'],row['profile']['maximumAnchorResidualNs'])
    groups = defaultdict(lambda: dict(count=0,boundaryAmbiguous=0,nullStacks=0,truncatedStacks=0,
                                      allocationSizeSum=0,tlabSizeSum=0,top=Counter(),inclusive=Counter(),
                                      stacks=Counter(),classes=Counter(),threads=Counter()))
    total = 0
    for event in events:
        kind = event['type']
        if kind not in EVENTS: raise ValueError('Unexpected stack export event')
        data = event['values']; ns = wall_to_monotonic(epoch_ns(data['startTime']),row['profile'])
        phase, ambiguous = phases.at(ns)
        thread = data.get('sampledThread' if kind.endswith('Sample') else 'eventThread')
        owner = thread_kind(thread,row['worker'])
        group = groups[(kind,phase,owner)];group['count'] += 1;total += 1
        group['boundaryAmbiguous'] += ambiguous
        identity=None if thread is None else {k:thread.get(k) for k in ('javaThreadId','osThreadId','javaName')}
        group['threads'][json.dumps(identity,sort_keys=True)] += 1
        stack = data.get('stackTrace')
        frames = [] if stack is None else [frame_name(f) for f in stack['frames']]
        group['nullStacks'] += not frames
        group['truncatedStacks'] += bool(stack and stack['truncated'])
        if kind.startswith('jdk.ObjectAllocation'):
            for field in ('allocationSize','tlabSize'):
                value = data.get(field,0)
                if not isinstance(value,int) or value < 0: raise ValueError('Invalid allocation size')
                group[field+'Sum'] += value
            group['classes'][data['objectClass']['name']] += 1
        group['top'][frames[0] if frames else '<missing>'] += 1
        # Inclusive means at least one frame per event, avoiding recursive double counts.
        group['inclusive'].update(set(frames))
        group['stacks'][tuple(frames)] += 1
    output=[]
    for (event,phase,owner),g in sorted(groups.items()):
        item=dict(event=event,phase=phase,owner=owner,**g)
        for field in ('top','inclusive','classes','threads'):
            item[field]=[dict(key=k,count=n) for k,n in g[field].most_common()]
        item['stacks']=[dict(frames=list(k),count=n) for k,n in g['stacks'].most_common()]
        output.append(item)
    return dict(totalEvents=total,groups=output)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('attempt',type=Path);p.add_argument('--profile-review',default='profile-review-001')
    p.add_argument('--output-id',required=True);p.add_argument('--jfr',type=Path,required=True)
    p.add_argument('--compact',action='store_true')
    args=p.parse_args();attempt=args.attempt.resolve()
    if Path(args.output_id).name != args.output_id: raise ValueError('Invalid output ID')
    review_path=attempt/args.profile_review/'review.json'
    review=json.loads(review_path.read_text());manifest=json.loads((attempt/'manifest.json').read_text())
    if (not review['profileAndQualityPass'] or review['primaryEndpointUseAllowed'] is not False
            or len(review['observations']) != 4 or len(manifest['invocations']) != 4):
        raise ValueError('Require complete validated diagnostic profile')
    destination=attempt/args.output_id;destination.mkdir()
    results=[]
    for row,inv in zip(review['observations'],manifest['invocations']):
        if row['label'] != inv['label']: raise ValueError('Profile slot identity changed')
        relative=inv['properties']['Channel']+'/jfr/worker.jfr'
        recording=Path(inv['rawDirectory'])/relative
        digest=file_sha(recording)
        if digest != inv['rawSha256'][relative]: raise ValueError('Raw recording changed')
        events=(compact_events(args.jfr.parent/'java',recording,destination/(row['label']+'.stderr')) if args.compact
                else print_events(args.jfr,recording,EVENTS,destination/(row['label']+'.stderr')))
        summary=summarize(events,row)
        summary.update(label=row['label'],recording=str(recording),recordingSha256=digest,
                       command=([str(args.jfr.parent/'java'),'-Xmx256m',str(HELPER),str(recording)] if args.compact
                                else [str(args.jfr),'print','--json','--events',','.join(EVENTS),
                                '--stack-depth','64',str(recording)]),
                       servicePercentilesNs=row['servicePercentilesNs'])
        with (destination/(row['label']+'.json')).open('x') as stream: json.dump(summary,stream,indent=2)
        results.append(dict(label=row['label'],totalEvents=summary['totalEvents'],recordingSha256=digest))
        print(row['label']+': '+str(summary['totalEvents'])+' events',flush=True)
    result=dict(diagnosticOnly=True,primaryEndpointUseAllowed=False,reportable=False,
        profileReviewSha256=file_sha(review_path),manifestSha256=file_sha(attempt/'manifest.json'),
        scriptSha256=file_sha(Path(__file__)),helperSha256=file_sha(HELPER) if args.compact else None,eventTypes=EVENTS,results=results,
        limits=['Counts are profiling events, not latency replicas or precise method durations.',
                'NewTLAB events identify triggering objects/refill sites, not every allocated object.',
                'All events retained; phase assignment near a boundary is flagged as ambiguous.',
                'Clock uncertainty is the maximum observed anchor residual, not a guaranteed error bound.',
                'Inclusive counts deduplicate repeated frames within each event; all full stacks retained.'])
    with (destination/'summary.json').open('x') as stream:json.dump(result,stream,indent=2)


if __name__=='__main__':main()
