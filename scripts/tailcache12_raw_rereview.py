#!/usr/bin/env python3
"""Offline host-only raw re-review; no cache construction or benchmark invocation."""
import argparse
import base64
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]


def check(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text())


def rows(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def near(actual, expected, label):
    check((actual is None and expected is None) or
          (actual is not None and expected is not None and
           math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-9)),
          f'{label}: {actual} != {expected}')


def rank(bins, percentile):
    target = max(1, math.ceil(math.nextafter(percentile, -math.inf) *
                              sum(count for _, count in bins) / 100))
    cumulative = 0
    for upper, count in bins:
        cumulative += count
        if cumulative >= target:
            return upper
    raise ValueError('Empty rank input')


def run(out):
    check(__debug__, 'Run without -O: the reused independent GC parser uses assertions')
    out.mkdir(parents=True, exist_ok=False)
    archive = ROOT / 'evidence-archives'
    paper = load(ROOT / 'docs/preprint/paper-data.json')
    sources = {name: load(ROOT / paper['provenance'][name]['path'])
               for name in ('focused', 'midpoint')}
    for name in sources:
        check(sha(ROOT / paper['provenance'][name]['path']) == paper['provenance'][name]['sha256'],
              'Frozen source input changed')
    observations = [r for d in sources.values() for r in d['observations']]
    check(len(observations) == len({(r['batch'], r['label']) for r in observations}) == 162,
          'Source observation coverage mismatch')
    tail_paths = [archive / 'focused-rq-tails-20261108-001/tails.json',
                  ROOT / paper['provenance']['tails']['path']]
    tails = {(r['batch'], r['label']): r['channels'] for p in tail_paths
             for r in load(p)['forks']}
    check(set(tails) == {(r['batch'], r['label']) for r in observations}, 'Full-tail coverage mismatch')
    batches = sorted({r['batch'] for r in observations})
    paths = sorted(p for b in batches for p in (archive / b).rglob('*.hdr'))
    check(len(paths) == len(set(paths)) and paths, 'Missing/duplicate histogram coverage')
    (out / 'paths.txt').write_text(''.join(str(p) + '\n' for p in paths))
    java = pathlib.Path('/usr/lib/jvm/java-21-openjdk/bin')
    jar = archive / 'focused-rq-results-20261108-001/runtime-libraries/HdrHistogram-2.2.2.jar'
    check(sha(jar) == '22d1d4316c4ec13a68b559e98c8256d69071593731da96136640f864fa14fad8',
          'Decoder dependency changed')
    helpers = [ROOT / 'scripts/java' / (name + '.java') for name in
               ('TailCacheFocusedHdrVerify', 'TailCacheTailVerify')]
    subprocess.run([str(java / 'javac'), '-cp', str(jar), '-d', str(out),
                    *map(str, helpers)], check=True, capture_output=True)
    command = [str(java / 'java'), '-Xmx96m', '-cp', str(out) + ':' + str(jar)]
    decoded = {}
    for i, batch in enumerate(batches):
        result = subprocess.run(command + ['TailCacheFocusedHdrVerify', str(archive / batch),
                                          str(out / f'quantiles-{i}.csv')],
                                check=True, capture_output=True, text=True)
        check(json.loads(result.stdout)['distributionMatch'], 'HDR/bin mismatch')
        for r in rows(out / f'quantiles-{i}.csv'):
            check(r['path'] not in decoded, 'Duplicated decoder identity')
            decoded[r['path']] = r
    subprocess.run(command + ['TailCacheTailVerify', str(out / 'paths.txt'), str(out / 'bounds.csv')],
                   check=True, capture_output=True)
    bounds = {r['path']: r for r in rows(out / 'bounds.csv')}
    check(set(decoded) == set(bounds) == {str(p) for p in paths}, 'Decoder coverage mismatch')
    # Reuse the prior independent unified-log parser, not a collection/parser module.
    spec = importlib.util.spec_from_file_location('prior_independent_audit',
                                                ROOT / 'ops/tailcache12_final_raw_audit.py')
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    counters = dict(workloadForks=0, controlForks=0, rawFilesVerified=0,
                    quantileEndpoints=0, thresholdBounds=0, gcSummaries=0,
                    measurementWindows=0, histogramCounts=0, freshScheduleChecks=0,
                    freshRssSummaries=0, publishedFullCurves=0, publishedThresholdBounds=0)
    # Control labels repeat across batches: retain the physical directory identity.
    control_records = [(load(p), p.parent) for b in batches
                       for p in (archive / b / 'controls').glob('*/result.json')]
    records = [(r, archive / r['batch'] / r['label']) for r in observations] + control_records
    check(len(control_records) == 3 * len(batches), 'Control coverage mismatch')
    seen = set()
    for source, directory in records:
        is_control = directory.parent.name == 'controls'
        counters['controlForks' if is_control else 'workloadForks'] += 1
        for name, digest in source['rawSha256'].items():
            check(sha(directory / name) == digest, f'Raw digest mismatch: {directory / name}')
            counters['rawFilesVerified'] += 1
        windows = rows(directory / 'worker/windows.csv')
        check(windows == source['windows'], f'Raw windows mismatch: {directory}')
        measured = [w for w in windows if w['phase'] == 'MEASUREMENT']
        check(len(measured) == 1, 'Focused/fresh measurement window count')
        w = measured[0]
        counters['measurementWindows'] += 1
        for field, value in source['measurement'].items():
            if field in w:
                near(float(w[field]), value, f'{directory}/{field}')
        near(int(w['workerAllocatedBytes']) / int(w['operations']),
             source['measurement']['workerBytesPerOperation'], 'Allocation per operation')
        check(int(w['churnDroppedBytes']) >= 0, 'Negative dropped demand')
        if not is_control and source['batch'].startswith('midpoint-'):
            check(int(w['operations']) == int(w['scheduled']) == 1500000,
                  'Fresh request conservation')
            check(int(w['offeredEndNs']) - int(w['startNs']) == 30000000000,
                  'Fresh offered duration changed')
            counters['freshScheduleChecks'] += 1
            memory = rows(directory / 'process-memory.csv')
            chosen = [r for r in memory if int(r['sampleStartNs']) >= int(w['startNs'])
                      and int(r['sampleEndNs']) <= int(w['endNs'])]
            expected = source['processMemory']
            near(max(int(r['VmRSSKiB']) for r in chosen), expected['measuredMaxRssKiB'],
                 'Measured-window sampled maximum RSS')
            counters['freshRssSummaries'] += 1
        for channel, latency in source['latency'].items():
            path = directory / 'worker' / (channel + '.hdr')
            check(str(path) not in seen, 'Duplicated source histogram')
            seen.add(str(path))
            direct = decoded[str(path)]
            check(int(direct['count']) == latency['count'], 'Distribution count mismatch')
            check(latency['count'] == (0 if channel == 'response' and source['regime'] == 'closed'
                                      else int(w['operations'])), 'Channel/operation count mismatch')
            counters['histogramCounts'] += 1
            bins = [(int(b['upperEquivalentNs']), int(b['count']))
                    for b in rows(path.with_name(channel + '-bins.csv'))]
            published = None if is_control else tails[(source['batch'], source['label'])][channel]
            if published is not None:
                decoded_curve = gzip.decompress(base64.b64decode(published['curve'], validate=True))
                flat = json.loads(decoded_curve)
                check(list(zip(flat[::2], flat[1::2])) == bins and len(flat) == 2 * len(bins),
                      'Published full curve/raw distribution mismatch')
                check(hashlib.sha256(decoded_curve).hexdigest() == published['curveSha256'] and
                      published['binBoundsSha256'] == bounds[str(path)]['binBoundsSha256'],
                      'Published full curve digest mismatch')
                counters['publishedFullCurves'] += 1
            for percentile, field in [('50', 'p50Ns'), ('99', 'p99Ns'), ('99.9', 'p999Ns'),
                                      ('99.99', 'p9999Ns'), ('99.999', 'p99999Ns')]:
                if not latency['count']:
                    continue
                actual = int(direct[field])
                near(rank(bins, float(percentile)), actual, 'Python/library percentile')
                # Controls retain the original p50/p99/p99.9 summaries only.
                if percentile in latency['percentilesNs']:
                    near(actual, latency['percentilesNs'][percentile], 'Published percentile')
                    counters['quantileEndpoints'] += 1
            for threshold, prefix in [(100000, 'gt100us'), (1000000, 'gt1ms'), (10000000, 'gt10ms')]:
                lower = sum(n for upper, n in bins
                            if upper - (1 << max(0, upper.bit_length() - 11)) + 1 > threshold)
                upper = sum(n for upper, n in bins if upper > threshold)
                check(lower == int(bounds[str(path)][prefix + 'Lower']) and
                      upper == int(bounds[str(path)][prefix + 'Upper']), 'Threshold mismatch')
                counters['thresholdBounds'] += 1
                if published is not None:
                    expected = published['rates'][str(threshold)]
                    check(lower == expected['lowerCount'] and upper == expected['upperCount'],
                          'Published threshold count mismatch')
                    near(lower / latency['count'] if latency['count'] else None,
                         expected['lowerProbability'], 'Published lower probability')
                    near(upper / latency['count'] if latency['count'] else None,
                         expected['upperProbability'], 'Published upper probability')
                    counters['publishedThresholdBounds'] += 1
        if source.get('gc'):
            actual = audit.gc_audit(directory / 'gc-through-measurement.log',
                                    [(int(w['startNs']), int(w['endNs']))])
            for key, value in actual.items():
                if key != 'occupancyCount':
                    near(value, source['gc'][key], f'{directory}/GC/{key}')
            counters['gcSummaries'] += 1
    check(seen == set(decoded), 'Orphan/missing raw histogram')
    runtime = sources['midpoint']['runtimeFiles']
    for name, digest in runtime.items():
        check(sha(pathlib.Path(name)) == digest, f'Frozen runtime changed: {name}')
    receipt = dict(passed=True, newBenchmarkRuns=0, counts=counters,
                   histogramsDecoded=len(decoded), nonemptyHistograms=sum(int(r['count']) > 0 for r in decoded.values()),
                   batches=batches, runtimeFilesVerified=len(runtime),
                   freshControlWarnings=[dict(batch=p.parent.parent.parent.name,
                                              control=p.parent.name, warnings=load(p)['warnings'])
                                         for b in batches if b.startswith('midpoint-')
                                         for p in sorted((archive / b / 'controls').glob('*/result.json'))],
                   paperDataSha256=sha(ROOT / 'docs/preprint/paper-data.json'),
                   inputs={name: sha(ROOT / paper['provenance'][name]['path']) for name in sources},
                   fullTailInputHashes={str(p.relative_to(ROOT)): sha(p) for p in tail_paths},
                   implementationSha256={str(p.relative_to(ROOT)): sha(p) for p in
                                         [pathlib.Path(__file__), *helpers, ROOT / 'ops/tailcache12_final_raw_audit.py']},
                   limits='Independent offline reconciliation reuses prior HDR decoders and independent GC parser. '
                          'No event-level causal attribution, host-neutrality proof, new performance run or human peer review.')
    (out / 'audit.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=pathlib.Path, required=True)
    run(parser.parse_args().out.resolve())
