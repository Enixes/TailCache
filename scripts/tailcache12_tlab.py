"""Diagnostic per-GC TLAB totals; never worker-specific size or latency evidence."""
import re
import statistics

PREFIX = re.compile(r'\[(\d+)ns\]\[(\d+)\]\[(\d+)\]\[debug\]\[gc,tlab\]\s*')
TOTALS = re.compile(r'GC\((\d+)\) TLAB totals: thrds:\s*(\d+)\s+refills:\s*(\d+) max:\s*(\d+)'
    r'\s+slow allocs:\s*(\d+) max\s*(\d+) waste:\s*([\d.]+)%\s+gc:\s*(\d+)B max:\s*(\d+)B'
    r'\s+slow:\s*(\d+)B max:\s*(\d+)B\s*$')
FIELDS = ('gcId', 'allocatingThreads', 'refills', 'maxThreadRefills', 'slowAllocations',
          'maxThreadSlowAllocations', 'wastePercent', 'gcWasteBytes', 'maxThreadGcWasteBytes',
          'refillWasteBytes', 'maxThreadRefillWasteBytes')


def parse(text, worker_pid, framing_repairs=None):
    records = {}
    for line in text.splitlines():
        if 'TLAB totals:' not in line:
            continue
        prefix = PREFIX.search(line)
        if prefix is None:
            raise ValueError('TLAB line lacks unambiguous declared clock/PID decorators')
        if int(prefix[2]) != worker_pid:
            continue
        # Captions before the logger prefix need no repair. Only record an
        # interruption inside the structured payload, preserving its receipt.
        normalized = line[:prefix.end()] + re.sub(r'# Warmup Iteration +\d+: *', '', line[prefix.end():])
        if normalized != line:
            if framing_repairs is not None:
                framing_repairs.append(dict(original=line, normalized=normalized))
            line = normalized
            prefix = PREFIX.search(line)
        values = TOTALS.fullmatch(line[prefix.end():])
        if values is None:
            raise ValueError('Unrecognized actual-worker TLAB totals')
        row = {key: (float(value) if key == 'wastePercent' else int(value))
               for key, value in zip(FIELDS, values.groups())}
        row.update(endNs=int(prefix[1]), pid=worker_pid, loggingThreadId=int(prefix[3]))
        if (row['refills'] < row['maxThreadRefills'] or row['allocatingThreads'] < 1
                or row['slowAllocations'] < row['maxThreadSlowAllocations']
                or not 0 <= row['wastePercent'] <= 100):
            raise ValueError('Inconsistent aggregate TLAB totals')
        previous = records.get(row['gcId'])
        if previous is not None and previous != row:
            raise ValueError('Conflicting/ambiguous TLAB records for one worker GC')
        records[row['gcId']] = row  # Identical console/JMH copies are one record.
    if not records:
        raise ValueError('No actual-worker TLAB statistics')
    result = sorted(records.values(), key=lambda row: row['gcId'])
    if any(b['endNs'] <= a['endNs'] for a, b in zip(result, result[1:])):
        raise ValueError('Nonmonotone actual-worker TLAB clocks')
    return result


def summarize(records, pauses):
    events = [p for p in pauses if p['kind'].startswith(('Pause Young', 'Pause Full'))]
    if not events:
        raise ValueError('No eligible analysed collection exposure for TLAB observation')
    indexed = {row['gcId']: row for row in records}
    if any(int(p['gcId']) not in indexed for p in events):
        raise ValueError('Missing TLAB record for an analysed collection')
    selected = []
    for event in events:
        row = indexed[int(event['gcId'])]
        # Stats publish during the collection; allow a declared10ms logging
        # adjacency envelope. Failure makes the whole observation inconclusive.
        if not event['startNs'] - 10_000_000 <= row['endNs'] <= event['endNs'] + 10_000_000:
            raise ValueError('TLAB/GC collection clocks do not agree')
        selected.append(dict(row, collectionStartNs=event['startNs'], collectionEndNs=event['endNs']))
    fields = ('allocatingThreads', 'refills', 'maxThreadRefills', 'slowAllocations', 'wastePercent')
    return dict(collections=len(selected), observations=selected,
        perCollection={key: dict(min=min(r[key] for r in selected), median=statistics.median(r[key] for r in selected),
                                max=max(r[key] for r in selected)) for key in fields},
        limits=['Aggregate counts per GC; no known worker-specific buffer size/refill latency.',
                'Boundary collections can include earlier partial intervals; final unfinished cycles are absent.'])
