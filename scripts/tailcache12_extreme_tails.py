#!/usr/bin/env python3
"""Derive and independently verify p99.999; never launch benchmark workloads."""
import argparse
import collections
import copy
import csv
import datetime
import decimal
import json
import math
import pathlib
import shutil
import subprocess

import tailcache12_focus_report as report

ROOT = pathlib.Path(__file__).resolve().parents[1]
PREVIOUS = ROOT / 'evidence-archives/focused-rq-p9999-20261108-001'
ORIGINAL = ROOT / 'evidence-archives/focused-rq-results-20261108-001'
DEFAULT_OUT = ROOT / 'evidence-archives/focused-rq-p99999-20261108-001'
PERCENTILES = ('50', '99', '99.9', '99.99', '99.999')
ENDPOINTS = dict(zip(PERCENTILES, ('p50Ns', 'p99Ns', 'p999Ns', 'p9999Ns', 'p99999Ns')))


def extract(bins, expected):
    values = [(int(r['upperEquivalentNs']), int(r['count'])) for r in bins]
    assert all(v >= 0 and n > 0 for v, n in values)
    assert all(a[0] < b[0] for a, b in zip(values, values[1:]))
    total = sum(n for v, n in values)
    assert total == expected
    ranks = {p: max(1, math.ceil(math.nextafter(float(p), -math.inf) * total / 100)) for p in PERCENTILES}
    quantiles = dict.fromkeys(PERCENTILES)
    support = {}
    cumulative = 0
    for value, count in values:
        cumulative += count
        for p in PERCENTILES:
            if quantiles[p] is None and cumulative >= ranks[p]:
                quantiles[p] = value
                support[p] = dict(rank=ranks[p], selectedBinCount=count,
                                  strictlyAboveSelectedBin=total-cumulative)
    for p in PERCENTILES:
        fraction = (decimal.Decimal(100)-decimal.Decimal(p))/100
        support.setdefault(p, dict(rank=None, selectedBinCount=0, strictlyAboveSelectedBin=0))
        support[p]['nominalUpperTailObservations'] = float(total*fraction)
    return quantiles, support


def paired(rows):
    groups = collections.defaultdict(list)
    for row in rows:
        groups[(row['batch'], row['liveMiB'], row['regime'])].append(row)
    result = []
    for (batch, live, regime), chosen in sorted(groups.items()):
        channel = 'response' if regime == 'arrival' else 'service'
        pairs = []
        for block in (1, 2, 3):
            by = {r['backend']: r for r in chosen if r['block'] == block}
            assert set(by) == {'CAFFEINE', 'CHRONICLE_IN_MEMORY'}
            pairs.append(dict(block=block, warningBearing=any(r['warnings'] for r in by.values()),
                ratios={p: by['CHRONICLE_IN_MEMORY']['latency'][channel]['percentilesNs'][p] /
                           by['CAFFEINE']['latency'][channel]['percentilesNs'][p] for p in PERCENTILES[1:]}))
        result.append(dict(batch=batch, ballastMiB=live, regime=regime, channel=channel, pairs=pairs,
                           warningFreeBlocks=[p['block'] for p in pairs if not p['warningBearing']]))
    return result


def markdown(rows, comparisons):
    lines = ['# Requested p99.999 extension', '',
        'Post hoc analysis of the same 132 forks; zero new benchmark runs. All warnings, contracts, durations and runtime groups remain separate. Ranges span three forks, not confidence intervals. Ratios below 1 favor Chronicle.', '',
        'At 50,000 scheduled requests/s, an 8 s window has only 4 nominal observations in the upper 0.001%; a 30 s window has 15. These are correlated responses, not independent pause episodes. Sparse tail support is shown rather than used to remove points.', '',
        '| Batch | Ballast MiB | Channel | Caffeine p99.999 µs | Chronicle p99.999 µs | Paired ratios | Clean blocks |',
        '| --- | --- | --- | --- | --- | --- | --- |']
    for comparison in comparisons:
        chosen = [r for r in rows if (r['batch'], r['liveMiB'], r['regime']) ==
                  (comparison['batch'], comparison['ballastMiB'], comparison['regime'])]
        ranges = []
        for backend in ('CAFFEINE', 'CHRONICLE_IN_MEMORY'):
            values = [r['latency'][comparison['channel']]['percentilesNs']['99.999']/1000
                      for r in chosen if r['backend'] == backend]
            ranges.append(f'{min(values):.3f}–{max(values):.3f}')
        ratios = ', '.join(f"{p['ratios']['99.999']:.4f}" for p in comparison['pairs'])
        lines.append(f"| {comparison['batch']} | {comparison['ballastMiB']} | {comparison['channel']} | "
                     f"{ranges[0]} | {ranges[1]} | {ratios} | {comparison['warningFreeBlocks']} |")
    return '\n'.join(lines)+'\n'


def run(out):
    out.mkdir(parents=True, exist_ok=False)
    setup = out/'setup'; setup.mkdir()
    decoded = out/'decoded'; decoded.mkdir()
    preserved = [PREVIOUS/'study.json', PREVIOUS/'audit.json', ORIGINAL/'study.json',
                 ROOT/'evidence-archives/focused-rq-delivery-20261108-001.tar.gz',
                 ROOT/'evidence-archives/focused-rq-p9999-delivery-20261108-001.tar.gz']
    hashes = {str(p.relative_to(ROOT)): report.sha(p) for p in preserved}
    jar = ORIGINAL/'runtime-libraries/HdrHistogram-2.2.2.jar'
    wanted = next(v['sha256'] for k, v in report.load(ORIGINAL/'runtime-libraries.json')['files'].items()
                  if k.endswith('/HdrHistogram-2.2.2.jar'))
    assert report.sha(jar) == wanted
    java = pathlib.Path('/usr/lib/jvm/java-21-openjdk/bin')
    helper = ROOT/'scripts/java/TailCacheFocusedHdrVerify.java'
    subprocess.run([str(java/'javac'), '-cp', str(jar), '-d', str(setup), str(helper)], check=True)
    hdr = {}; inventory_count = 0
    for batch in report.load(ORIGINAL/'study.json')['batches']:
        base = ROOT/'evidence-archives'/batch['batch']
        for entry in report.load(base/'inventory.json'):
            path = base/entry['path']
            assert path.stat().st_size == entry['bytes'] and report.sha(path) == entry['sha256'], path
            inventory_count += 1
        endpoint_file = decoded/(base.name+'.csv')
        done = subprocess.run([str(java/'java'), '-Xmx64m', '-cp', str(setup)+':'+str(jar),
                              'TailCacheFocusedHdrVerify', str(base), str(endpoint_file)],
                              check=True, capture_output=True, text=True)
        direct = report.csvrows(endpoint_file)
        assert len(direct) == json.loads(done.stdout)['verifiedHistograms']
        for row in direct:
            assert row['path'] not in hdr
            hdr[row['path']] = row
    original = report.load(PREVIOUS/'study.json')
    rows = copy.deepcopy(original['observations']); checks = 0
    for row in rows:
        worker = ROOT/'evidence-archives'/row['batch']/row['label']/'worker'
        for channel in ('service', 'gap', 'response'):
            latency = row['latency'][channel]
            values, support = extract(report.csvrows(worker/(channel+'-bins.csv')), latency['count'])
            direct = hdr[str(worker/(channel+'.hdr'))]
            assert int(direct['count']) == latency['count']
            for p, key in ENDPOINTS.items():
                assert (values[p] if latency['count'] else 0) == int(direct[key]), (row['label'], channel, p)
                if latency['count']: checks += 1
                if p != '99.999': assert values[p] == latency['percentilesNs'][p]
            latency['percentilesNs'] = values
            latency['tailSupport']['perPercentile'] = support
    comparisons = paired(rows)
    report.save(out/'study.json', dict(kind='user-requested-post-hoc-p99999-extension', complete=True,
        baseStudy=str((PREVIOUS/'study.json').relative_to(ROOT)), newBenchmarkRuns=0,
        percentiles=PERCENTILES, observations=rows, comparisons=comparisons, limits=original['limits']+[
        'p99.999: only 4 nominal upper-tail responses per 8 s fork, 15 per 30 s fork at 50k/s.',
        'Quantile bin counts and strictly-above counts describe finite support, not independent episodes or confidence intervals.']))
    with (out/'forks.csv').open('x', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['batch','label','payloadBytes','ballastMiB','backend','regime','block','measureMs',
            'channel','count', *['p'+p+'Ns' for p in PERCENTILES[1:]],
            'p99999NominalUpperTailObservations','p99999Rank','p99999SelectedBinCount','p99999StrictlyAboveSelectedBin','warnings'])
        for row in rows:
            for channel, latency in row['latency'].items():
                support = latency['tailSupport']['perPercentile']['99.999']
                writer.writerow([row['batch'],row['label'],row['payload'],row['liveMiB'],row['backend'],row['regime'],row['block'],row['measureMs'],
                    channel,latency['count'],*[latency['percentilesNs'][p] for p in PERCENTILES[1:]],
                    support['nominalUpperTailObservations'],support['rank'],support['selectedBinCount'],support['strictlyAboveSelectedBin'],json.dumps(row['warnings'])])
    (out/'comparisons.md').write_text(markdown(rows, comparisons))
    controls = []
    for path, direct in hdr.items():
        if '/controls/' in path:
            count = int(direct['count'])
            controls.append(dict(path=path,count=count,p99999Ns=int(direct['p99999Ns']),nominalUpperTailObservations=count/100000))
    report.save(out/'controls.json', controls)
    for path, digest in hashes.items(): assert report.sha(ROOT/path) == digest
    report.save(out/'audit.json', dict(passed=True,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        newBenchmarkRuns=0,workloadForks=len(rows),workloadHistograms=len(rows)*3,
        decodedWorkloadAndControlHistograms=len(hdr),independentPercentileChecks=checks,inventoryFilesVerified=inventory_count,
        baseArtifactsUnchanged=hashes,hdrJarSha256=wanted,
        implementationSha256={str(p.relative_to(ROOT)):report.sha(p) for p in (pathlib.Path(__file__), helper)},
        controlsNote='One-second arrival floors have only 0.5 nominal observations above p99.999; no floor subtraction.'))
    shutil.copyfile(pathlib.Path(__file__), out/'analysis-source.py')
    shutil.copyfile(helper, out/helper.name)
    print(json.dumps(report.load(out/'audit.json'), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=pathlib.Path, default=DEFAULT_OUT)
    run(parser.parse_args().out.resolve())
