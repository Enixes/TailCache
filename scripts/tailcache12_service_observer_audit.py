#!/usr/bin/env python3
"""Reconcile JMH raw samples/windows with archived source/runtime and GC logs."""
import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import math
import pathlib
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PERCENTILES = ('50', '99', '99.9', '99.99', '99.999')


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def require(test, message):
    if not test:
        raise ValueError(message)


def same(a, b, label):
    require((a is None and b is None) or
            (a is not None and b is not None and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9)), label)


def quantile(counts, percentile):
    target = max(1, math.ceil(math.nextafter(percentile, -math.inf) * sum(counts.values()) / 100))
    cumulative = 0
    for value, count in sorted(counts.items()):
        cumulative += count
        if cumulative >= target:
            return value
    raise ValueError('Empty sample distribution')


def properties(path):
    return dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line)


def audit(base, out):
    out.mkdir(exist_ok=False)
    protocol, study = load(base / 'protocol.json'), load(base / 'study.json')
    with tarfile.open(base / 'source.tar.gz', 'r:gz') as archive:
        sources = {}
        for member in archive.getmembers():
            require(member.isfile() and member.name in protocol['sourceFiles'] and member.name not in sources,
                    'Unexpected source archive member')
            sources[member.name] = archive.extractfile(member).read()
    require(set(sources) == set(protocol['sourceFiles']), 'Source archive coverage')
    for name, content in sources.items():
        require(hashlib.sha256(content).hexdigest() == protocol['sourceFiles'][name], 'Source identity')
    runtime = {}
    for original, retained in zip(protocol['classpath'].split(':'), protocol['archivedClasspath']):
        destination = base / retained
        if destination.is_file():
            runtime[original] = sha(destination)
        else:
            for path in destination.rglob('*'):
                if path.is_file():
                    runtime[str(pathlib.Path(original) / path.relative_to(destination))] = sha(path)
    require(runtime == protocol['runtimeSha256'], 'Archived runtime identity')
    for name, digest in protocol['preservedPaperInputs'].items():
        require(sha(ROOT / name) == digest, 'Historical paper inputs changed')
    for name, digest in protocol['design'].get('discoveryInputs', {}).items():
        require(sha(ROOT / name) == digest, 'Predeclared discovery/compilation input changed')
    parser = out / 'prior_independent_gc.py'
    parser.write_bytes(sources['ops/tailcache12_final_raw_audit.py'])
    spec = importlib.util.spec_from_file_location('archived_independent_gc', parser)
    gc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gc)
    entries = [(r, base / 'slots' / r['label']) for r in study['observations']]
    entries += [(load(p), p.parent) for p in sorted((base / 'controls').glob('*/service-result.json'))]
    counts = collections.Counter()
    native_estimators = []
    for row, directory in entries:
        for name, digest in row['rawSha256'].items():
            require(sha(directory / name) == digest, 'Raw file changed')
            counts['rawFiles'] += 1
        if row['status'] != 'OK':
            counts['failureOutcomes'] += 1
            continue
        windows = rows(directory / 'worker/windows.csv')
        require(windows == row['windows'], 'Raw iteration windows')
        require(all(int(w['startNs']) < int(w['endNs']) for w in windows), 'Iteration duration')
        require(all(int(a['endNs']) <= int(b['startNs']) for a, b in zip(windows, windows[1:])),
                'Overlapping iteration windows')
        measurement = [w for w in windows if w['phase'] == 'MEASUREMENT']
        body = load(directory / 'results.json')
        require(len(body) == 1, 'JMH result count')
        item = body[0]
        require(item['mode'] == 'sample' and item['threads'] == item['forks'] == 1 and
                item['primaryMetric']['scoreUnit'] == 'ns/op' and item['jmhVersion'] == '1.37', 'JMH regime')
        require(item['params'] == dict(backend=row['backend'], payload=str(row['payload']),
                                      ballastMiB=str(row['liveMiB'])), 'JMH parameters')
        expected_warm = row.get('warmups', 3 if row.get('floor') else 14)
        expected_measure = row.get('iterations', 3 if row.get('floor') else 8)
        require(item['warmupIterations'] == expected_warm and item['measurementIterations'] == expected_measure and
                len(windows) == expected_warm + expected_measure and len(measurement) == expected_measure,
                'JMH/window coverage')
        raw = item['primaryMetric']['rawDataHistogram']
        require(len(raw) == 1 and len(raw[0]) == len(measurement), 'Raw sample coverage')
        combined = collections.Counter()
        per_iteration = []
        for histogram, window in zip(raw[0], measurement):
            current = collections.Counter()
            for value, count in histogram:
                require(float(value).is_integer() and value >= 0 and int(count) == count and count > 0,
                        'Invalid raw sample bin')
                current[int(value)] += int(count)
            require(0 < sum(current.values()) <= int(window['operations']), 'Sample/operation conservation')
            per_iteration.append(sum(current.values()))
            combined.update(current)
            counts['sampleHistograms'] += 1
        exported = {int(r['valueNs']): int(r['count']) for r in rows(directory / 'sample-bins.csv')}
        require(exported == dict(combined), 'Exported raw sample bins')
        latency = row['latency']['service']
        require(latency['count'] == sum(combined.values()) and
                latency['perIterationSampleCounts'] == per_iteration, 'Sample conservation')
        for percentile in PERCENTILES:
            expected = quantile(combined, float(percentile))
            same(latency['percentilesNs'][percentile], expected, 'Explicit raw-sample rank')
            counts['quantileEndpoints'] += 1
        native_estimators.append(dict(label=row['label'],
            native=item['primaryMetric']['scorePercentiles'], recomputed=latency['percentilesNs'],
            samples=sum(combined.values())))
        operations = sum(int(w['operations']) for w in measurement)
        writes = sum(int(w['writes']) for w in measurement)
        allocated = sum(int(w['workerAllocatedBytes']) for w in measurement)
        seconds = sum((int(w['endNs']) - int(w['startNs'])) / 1e9 for w in measurement)
        m = row['measurement']
        for label, value in dict(operations=operations, writes=writes, samples=sum(combined.values()),
                                 seconds=seconds, workerAllocatedBytes=allocated,
                                 workerBytesPerOperation=allocated/operations, operationsPerSecond=operations/seconds,
                                 compilerMs=sum(int(w['compilerMs']) for w in measurement),
                                 churnPayloadBytes=sum(int(w['churnPayloadBytes']) for w in measurement),
                                 churnDroppedBytes=sum(int(w['churnDroppedBytes']) for w in measurement)).items():
            same(m[label], value, label)
        floor = 0 if row.get('floor') else (operations if row['backend'] == 'CHRONICLE_IN_MEMORY' else writes) * row['payload']
        require(m['minimumPayloadAllocationBytes'] == floor and
                m['materializationFloorPassed'] == (allocated >= floor), 'Materialization diagnostic')
        identity = properties(directory / 'worker/worker.properties')
        config = properties(directory / 'worker/configuration.txt')
        require(identity == row['actualWorker'] and config['heapMaxBytes'] == str(512*1024**2) and
                config['traceOperations'] == '1000003' and config['traceArrayPayloadBytes'] == '9000027' and
                '-Dchronicle.analytics.disable=true' in config['jvmArgs'], 'Actual worker contract')
        integrity = properties(directory / 'worker/integrity.txt')
        require(integrity['passed'] == 'true' and
                int(integrity['operations']) == sum(int(w['operations']) for w in windows) and
                int(integrity['writes']) == sum(int(w['writes']) for w in windows), 'Full-trial conservation')
        measured_windows = [(int(w['startNs']), int(w['endNs'])) for w in measurement]
        logs = list(directory.glob('gc-*.log'))
        require(len(logs) == 1, 'Actual fork GC log')
        independent = gc.gc_audit(logs[0], measured_windows)
        for label, value in independent.items():
            if label != 'occupancyCount':
                same(row['gc'][label], value, 'Independent GC/' + label)
        memory = rows(directory / 'process-memory.csv')
        selected = [int(r['VmRSSKiB']) for r in memory if r['VmRSSKiB'] and any(
            int(r['sampleStartNs']) >= a and int(r['sampleEndNs']) <= b for a, b in measured_windows)]
        same(row['processMemory']['measuredMaxRssKiB'], max(selected, default=None), 'RSS')
        counts['gcSummaries'] += 1
        counts['rssSummaries'] += 1
        counts['integrityChecks'] += 1
    grouped = collections.defaultdict(dict)
    for row in study['observations']:
        key = (row['payload'], row['liveMiB'], row['block'])
        require(row['backend'] not in grouped[key], 'Duplicate paired backend')
        grouped[key][row['backend']] = row
    require(len(study['observations']) == 24 and len(study['pairs']) == len(grouped) == 12,
            'Fixed matrix coverage')
    for pair in study['pairs']:
        arms = grouped[pair['payload'], pair['liveMiB'], pair['block']]
        require(set(arms) == {'CAFFEINE', 'CHRONICLE_IN_MEMORY'}, 'Missing paired arm')
        if pair['valid']:
            require(all(r['status'] == 'OK' and r['latencyVerified'] for r in arms.values()), 'Invalid valid pair')
            require(len({r['trace']['traceSha256'] for r in arms.values()}) == 1, 'Paired trace identity')
            for percentile, value in pair['ratios'].items():
                same(value, arms['CHRONICLE_IN_MEMORY']['latency']['service']['percentilesNs'][percentile] /
                     arms['CAFFEINE']['latency']['service']['percentilesNs'][percentile], 'Paired sample ratio')
                counts['pairedRatios'] += 1
    (out / 'native-estimators.json').write_text(json.dumps(native_estimators, indent=2) + '\n')
    result = dict(passed=True, workloadForks=24, controlForks=len(entries)-24,
                  parentLauncherJvms=len(entries), runtimeFilesVerified=len(runtime), counts=dict(counts),
                  protocolSha256=sha(base/'protocol.json'), studySha256=sha(base/'study.json'),
                  sourceArchiveSha256=sha(base/'source.tar.gz'),
                  limits='Independent raw reconciliation, not a new performance replication or proof of sampler neutrality.')
    (out / 'audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Run without -O: archived independent GC checker uses assertions')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('attempt')
    parser.add_argument('--out', type=pathlib.Path)
    args = parser.parse_args()
    base = ROOT / 'evidence-archives' / args.attempt
    audit(base, args.out or base / 'independent-audit-001')
