#!/usr/bin/env python3
"""Prepare and render the paper's derived evidence. Never launches a benchmark."""
import argparse
import base64
import collections
import csv
import gzip
import hashlib
import io
import json
import math
import os
import pathlib
from decimal import Decimal

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'docs/preprint'
PERCENTILES = ('99', '99.9', '99.99', '99.999')
BACKENDS = ('CAFFEINE', 'CHRONICLE_IN_MEMORY')
THRESHOLDS = (100_000, 1_000_000, 10_000_000)
COLORS = {'CAFFEINE': '#b34b37', 'CHRONICLE_IN_MEMORY': '#176b91'}
INPUTS = {
    'focused': 'evidence-archives/focused-rq-p99999-20261108-001/study.json',
    'midpoint': 'evidence-archives/midpoint-results-20261110-001/study.json',
    'tails': 'evidence-archives/midpoint-results-20261110-001/tails.json',
    'audit': 'evidence-archives/midpoint-results-20261110-001/audit.json',
    'original': 'docs/TAILCACHE_12_FINAL_ACCEPTANCE.json',
    'environment': 'evidence-archives/midpoint-study-20261110-001-primary/setup/environment.json',
}


class EvidenceError(ValueError):
    """Invalid/incomplete evidence; active even when Python assertions are disabled."""


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value, immutable=False):
    text = json.dumps(value, indent=2, sort_keys=True) + '\n'
    if immutable and path.exists() and path.read_text() != text:
        raise ValueError(f'Refusing changed frozen paper input: {path}')
    path.write_text(text)


def identity(row):
    return row['dataset'], row['batch'], row['label']


def pair_rows(rows, *, reuse=False):
    """Pair only inside a batch, payload, pressure, workload, seed and runtime."""
    groups = collections.defaultdict(list)
    for row in rows:
        if row['backend'] == 'CHRONICLE_IN_MEMORY' and row['reuse'] != reuse:
            continue
        key = tuple(row[k] for k in ('dataset', 'batch', 'payload', 'liveMiB',
                                    'regime', 'qps', 'seed', 'runtimeGroup', 'measureMs', 'block'))
        groups[key].append(row)
    result = []
    for key, values in sorted(groups.items()):
        by_backend = {r['backend']: r for r in values}
        if len(by_backend) != len(values):
            raise ValueError(f'Duplicate backend in pair: {key}')
        if set(by_backend) != set(BACKENDS):
            raise ValueError(f'Incomplete pair: {key}')
        result.append((by_backend[BACKENDS[0]], by_backend[BACKENDS[1]]))
    return result


def decode_curve(channel):
    if channel['encoding'] != 'gzip-base64-flat-upper-ns-count':
        raise ValueError('Unknown curve encoding')
    raw = gzip.decompress(base64.b64decode(channel['curve'], validate=True))
    require(hashlib.sha256(raw).hexdigest() == channel['curveSha256'], 'Curve content hash mismatch')
    flat = json.loads(raw)
    require(isinstance(flat,list) and flat and all(type(n) is int for n in flat), 'Histogram values/counts must be nonempty integers')
    if len(flat) % 2:
        raise ValueError('Odd histogram array')
    bins = list(zip(flat[::2], flat[1::2]))
    if any(n <= 0 for x, n in bins) or any(a[0] >= b[0] for a, b in zip(bins, bins[1:])):
        raise ValueError('Invalid histogram bins')
    if sum(n for x, n in bins) != channel['count']:
        raise ValueError('Histogram count mismatch')
    require(channel['bins'] == len(bins), 'Histogram bin-count mismatch')
    digest = hashlib.sha256()
    for upper, n in bins:
        lower = lower_equivalent(upper)
        require(lower >= 0 and lower % (1 << max(0,upper.bit_length()-11)) == 0,
                'Invalid HDR upper-bin boundary')
        digest.update(f'{lower},{upper},{n}\n'.encode())
    require(digest.hexdigest() == channel['binBoundsSha256'], 'Histogram boundary hash mismatch')
    require(channel['maximumBinUpperNs'] == bins[-1][0] and
            channel['minimumBinLowerNs'] == lower_equivalent(bins[0][0]), 'Histogram extrema mismatch')
    require(channel['empiricalResolution'] == 1/channel['count'], 'Histogram empirical resolution mismatch')
    return bins


def lower_equivalent(upper):
    # HdrHistogram 2.2.2: lowest discernible value=1, three significant digits.
    return upper - (1 << max(0,upper.bit_length()-11)) + 1


def validate_rates(distribution):
    count = distribution['count']
    require(type(count) is int and count > 0, 'Invalid exceedance denominator')
    require(set(distribution['rates']) == {str(t) for t in THRESHOLDS}, 'Missing/extra threshold')
    for rate in distribution['rates'].values():
        lo,hi = rate['lowerCount'],rate['upperCount']
        require(type(lo) is int and type(hi) is int and 0 <= lo <= hi <= count, 'Invalid exceedance count bounds')
        require(rate['lowerProbability'] == lo/count and rate['upperProbability'] == hi/count,
                'Exceedance probability/count mismatch')


def verify_curve_rates(channel,bins):
    validate_rates(channel)
    for t in THRESHOLDS:
        rate = channel['rates'][str(t)]
        require(rate['lowerCount'] == sum(n for u,n in bins if lower_equivalent(u)>t),
                'Definite exceedance count differs from histogram')
        require(rate['upperCount'] == sum(n for u,n in bins if u>t),
                'Possible exceedance count differs from histogram')


def hdr_percentile(bins, percentile):
    total = sum(n for x, n in bins)
    rank = max(1, math.ceil(math.nextafter(float(percentile), -math.inf) * total / 100))
    cumulative = 0
    for value, n in bins:
        cumulative += n
        if cumulative >= rank:
            return value
    raise ValueError('Empty histogram')


def direction(values):
    require(values and all(math.isfinite(v) and v>0 for v in values), 'Comparison requires finite positive ratios')
    if all(v < 1 for v in values):
        return 'Chronicle lower'
    if all(v > 1 for v in values):
        return 'Caffeine lower'
    return 'Mixed or equal'


def prepare(out):
    out.mkdir(parents=True, exist_ok=True)
    data = {name: json.loads((ROOT / path).read_text()) for name, path in INPUTS.items()}
    require(data['audit']['passed'] and data['audit']['workloadForks'] == 30, "Evidence check failed: data['audit']['passed'] and data['audit']['workloadForks'] == 30")
    require(sha(ROOT / INPUTS['midpoint']) == data['audit']['studySha256'], "Evidence check failed: sha(ROOT / INPUTS['midpoint']) == data['audit']['studySha256']")
    require(sha(ROOT / INPUTS['tails']) == data['audit']['tailsSha256'], "Evidence check failed: sha(ROOT / INPUTS['tails']) == data['audit']['tailsSha256']")
    rows = []
    keep = ('label', 'backend', 'payload', 'liveMiB', 'block', 'regime', 'qps',
            'status', 'warnings', 'measurement', 'latency', 'gc', 'batch',
            'measureMs', 'runtimeGroup', 'processMemory', 'stallRates')
    for name in ('focused', 'midpoint'):
        for source in data[name]['observations']:
            row = {k: source[k] for k in keep if k in source}
            row.update(dataset=name, reuse=source.get('reuse', False),
                       seed=source.get('seed', 24301),
                       cohort=source.get('cohort', 'historical'))
            rows.append(row)
    rows.sort(key=identity)
    require(len(rows) == len({identity(r) for r in rows}) == 162, 'Evidence check failed: len(rows) == len({identity(r) for r in rows}) == 162')
    require(all((r['status'] == 'OK' for r in rows)), "Evidence check failed: all((r['status'] == 'OK' for r in rows))")
    by_id = {(r['batch'], r['label']): r for r in rows if r['dataset'] == 'midpoint'}
    curves = []
    for fork in data['tails']['forks']:
        row = by_id[(fork['batch'], fork['label'])]
        if row['cohort'] == 'primary':
            channel = fork['channels']['response']
            bins = decode_curve(channel)
            require(channel['count'] == row['latency']['response']['count'] == 1500000, "Evidence check failed: channel['count'] == row['latency']['response']['count'] == 1500000")
            for p in PERCENTILES:
                require(hdr_percentile(bins, p) == row['latency']['response']['percentilesNs'][p], "Evidence check failed: hdr_percentile(bins, p) == row['latency']['response']['percentilesNs'][p]")
            curves.append(dict(batch=fork['batch'], label=fork['label'], response=channel))
    require(len(curves) == 18, 'Evidence check failed: len(curves) == 18')
    env = data['environment']
    cpu = json.loads(env['cpu']['stdout'])['lscpu']
    hardware = {r['field'].rstrip(':'): r['data'] for r in cpu
                if r['field'] in ('Model name:', 'CPU(s):', 'Socket(s):',
                                  'Core(s) per socket:', 'Thread(s) per core:')}
    package = dict(schema='tailcache-paper-derived-v1', observations=rows, curves=curves,
                   hardware=hardware, java=env['java']['stderr'].strip(),
                   limits=['Derived evidence only; full raw evidence is retained locally.',
                           'No pooling across forks, seeds, runtimes or workload/ownership contracts.',
                           'Historical extreme percentiles are post hoc exploratory endpoints.',
                           'A point is an observation, not a confidence interval.'],
                   provenance={k: dict(path=v, sha256=sha(ROOT / v)) for k, v in INPUTS.items()})
    write_json(out / 'paper-data.json', package, immutable=True)
    checks = verify(package)
    write_json(out / 'data-audit-v2.json', checks, immutable=True)
    print(json.dumps(checks))


def verify(package):
    require(package['schema']=='tailcache-paper-derived-v1', 'Unknown derived-data schema')
    rows = package['observations']
    require(all(r['status']=='OK' for r in rows), 'Non-OK workload observation')
    for row in rows:
        require(row['dataset'] in ('focused','midpoint') and row['backend'] in BACKENDS, 'Unknown observation cohort/backend')
        require(row['regime'] in ('closed','arrival') and row['qps']==(0 if row['regime']=='closed' else 50000),
                'Workload regime/offered-rate mismatch')
        require(row['payload'] in (256,4096) and type(row['reuse']) is bool and
                not (row['backend']=='CAFFEINE' and row['reuse']), 'Unsupported payload/read contract')
        require(set(row['latency'])=={'service','gap','response'}, 'Missing observation channel')
        for channel,latency in row['latency'].items():
            expected_count=row['measurement']['scheduled'] if channel=='response' else row['measurement']['operations']
            require(latency['count']==expected_count, 'Observation channel count conservation failed')
            if latency['count']:
                values=[latency['percentilesNs'][p] for p in PERCENTILES]
                require(all(type(v) is int and v>0 for v in values) and values==sorted(values)
                        and values[-1]<=latency['maxNs'], 'Invalid observation percentile ordering/range')
    require(len(rows) == len({identity(r) for r in rows}) == 162, 'Evidence check failed: len(rows) == len({identity(r) for r in rows}) == 162')
    require(sum((r['dataset'] == 'focused' for r in rows)) == 132, "Evidence check failed: sum((r['dataset'] == 'focused' for r in rows)) == 132")
    fresh = [r for r in rows if r['dataset'] == 'midpoint']
    require(len(fresh) == 30 and sum((bool(r['warnings']) for r in fresh)) == 5, "Evidence check failed: len(fresh) == 30 and sum((bool(r['warnings']) for r in fresh)) == 5")
    require(len({r['runtimeGroup'] for r in fresh}) == 1, "Evidence check failed: len({r['runtimeGroup'] for r in fresh}) == 1")
    require(len(pair_rows(fresh)) == 15, 'Evidence check failed: len(pair_rows(fresh)) == 15')
    primary = [r for r in fresh if r['cohort'] == 'primary']
    require(len(primary) == 18, 'Evidence check failed: len(primary) == 18')
    for live, expected in ((0, 'Caffeine lower'), (104, 'Mixed or equal'), (208, 'Chronicle lower')):
        pairs = pair_rows([r for r in primary if r['liveMiB'] == live])
        ratios = [b['latency']['response']['percentilesNs']['99.9'] /
                  a['latency']['response']['percentilesNs']['99.9'] for a, b in pairs]
        require(direction(ratios) == expected, 'Evidence check failed: direction(ratios) == expected')
        require(sum((not a['warnings'] and (not b['warnings']) for a, b in pairs)) == (1 if live == 104 else 3), "Evidence check failed: sum((not a['warnings'] and (not b['warnings']) for a, b in pairs)) == (1 if live == 104 else 3)")
    for r in fresh:
        require(r['measurement']['operations'] == r['latency']['response']['count'] == 1500000, "Evidence check failed: r['measurement']['operations'] == r['latency']['response']['count'] == 1500000")
        require(r['measurement']['scheduled'] == 1500000, "Evidence check failed: r['measurement']['scheduled'] == 1500000")
        require((r['payload'],r['regime'],r['qps'],r['reuse'],r['measureMs'])==(4096,'arrival',50000,False,30000),
                'Fresh workload protocol mismatch')
        require(r['measurement']['offeredEndNs']-r['measurement']['startNs']==30_000_000_000,
                'Fresh offered-window duration mismatch')
        require(r['measurement']['endNs']>r['measurement']['startNs'], 'Invalid measured timing envelope')
        require(set(r['latency'])==set(r['stallRates'])=={'response','service','gap'}, 'Missing fresh channel')
        for ch,latency in r['latency'].items():
            require(latency['count']==1_500_000 and r['stallRates'][ch]['count']==latency['count'],
                    'Fresh channel count mismatch')
            vals=[latency['percentilesNs'][p] for p in PERCENTILES]
            require(all(type(v) is int and v>0 for v in vals) and vals==sorted(vals)
                    and latency['maxNs']>=vals[-1], 'Invalid percentile ordering/range')
            validate_rates(r['stallRates'][ch])
    expected={(cohort,seed,live,block,backend)
              for cohort,seed,blocks in [('primary',24301,range(1,4)),('seed24302',24302,[1]),('seed24303',24303,[1])]
              for live in (0,104,208) for block in blocks for backend in BACKENDS}
    actual=[(r['cohort'],r['seed'],r['liveMiB'],r['block'],r['backend']) for r in fresh]
    require(len(actual)==len(set(actual)) and set(actual)==expected, 'Fresh seed/block/pressure schedule mismatch')
    look = {(r['batch'], r['label']): r for r in primary}
    curve_ids=[(c['batch'],c['label']) for c in package['curves']]
    require(len(curve_ids)==len(set(curve_ids)) and set(curve_ids)==set(look),
            'Missing, duplicate or unexpected primary response curve')
    checked=0
    for curve in package['curves']:
        bins = decode_curve(curve['response'])
        row = look[(curve['batch'], curve['label'])]
        require(curve['response']['count']==row['latency']['response']['count'], 'Curve denominator differs from observation')
        verify_curve_rates(curve['response'],bins)
        require(curve['response']['rates']==row['stallRates']['response']['rates'], 'Curve/observation rates differ')
        for p in PERCENTILES:
            require(hdr_percentile(bins, p) == row['latency']['response']['percentilesNs'][p], "Evidence check failed: hdr_percentile(bins, p) == row['latency']['response']['percentilesNs'][p]")
            checked+=1
    for a, b in pair_rows(fresh):
        for p in ('99.99', '99.999'):
            require(b['latency']['response']['percentilesNs'][p] < a['latency']['response']['percentilesNs'][p], "Evidence check failed: b['latency']['response']['percentilesNs'][p] < a['latency']['response']['percentilesNs'][p]")
    service4k = [r for r in rows if r['dataset']=='focused' and r['payload']==4096
                 and r['regime']=='closed' and not r['reuse']]
    require(len(service4k) == 30, 'Evidence check failed: len(service4k) == 30')
    for a,b in pair_rows(service4k):
        for p in ('99','99.9','99.99'):
            require(b['latency']['service']['percentilesNs'][p] > a['latency']['service']['percentilesNs'][p], "Evidence check failed: b['latency']['service']['percentilesNs'][p] > a['latency']['service']['percentilesNs'][p]")
        require(b['latency']['service']['percentilesNs']['99.999'] < a['latency']['service']['percentilesNs']['99.999'], "Evidence check failed: b['latency']['service']['percentilesNs']['99.999'] < a['latency']['service']['percentilesNs']['99.999']")
    service256 = [r for r in rows if r['dataset']=='focused' and r['batch']=='focused-rq2-256-20261108-001' and r['regime']=='closed']
    require(len(service256) == 12, 'Evidence check failed: len(service256) == 12')
    for a,b in pair_rows(service256):
        for p,want_lower in [('99.9',a['liveMiB']==448),('99.999',a['liveMiB']==480)]:
            require((b['latency']['service']['percentilesNs'][p] < a['latency']['service']['percentilesNs'][p]) == want_lower, "Evidence check failed: (b['latency']['service']['percentilesNs'][p] < a['latency']['service']['percentilesNs'][p]) == want_lower")
        require(b['latency']['service']['percentilesNs']['99.99'] > a['latency']['service']['percentilesNs']['99.99'], "Evidence check failed: b['latency']['service']['percentilesNs']['99.99'] > a['latency']['service']['percentilesNs']['99.99']")
    return dict(passed=True, derivedForks=162, historicalForks=132, freshForks=30,
                primaryPairs=9, additionalSeedPairs=6, freshWarningForks=5,
                fullResponseCurvesChecked=len(curve_ids), histogramPercentileChecks=checked,
                primaryHistogramThresholdChecks=len(curve_ids)*len(THRESHOLDS),
                freshChannelThresholdConsistencyChecks=len(fresh)*3*len(THRESHOLDS),
                freshEndpointDirection='Caffeine at 0; mixed at 104; Chronicle at 208',
                extremeResponseDirection='Chronicle lower at every fresh point, including baseline',
                rawEvidenceReaudit=False, newBenchmarkRuns=0)


def export_tables(package, out):
    rows = package['observations']
    buffer = io.StringIO(newline='')
    fields = ['dataset', 'cohort', 'batch', 'runtimeGroup', 'seed', 'payload', 'liveMiB',
              'regime', 'reuse', 'backend', 'block', 'measureMs', 'warnings', 'channel',
              'percentile', 'count', 'latencyNs', 'nominalUpperTailObservations']
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator='\n'); writer.writeheader()
    for r in rows:
        for channel, values in r['latency'].items():
            if not values['count']:
                continue
            for p in PERCENTILES:
                entry = {k: r.get(k) for k in fields if k in r}
                entry.update(warnings='; '.join(r['warnings']), channel=channel,
                             percentile=p, count=values['count'], latencyNs=values['percentilesNs'][p],
                             nominalUpperTailObservations=Decimal(values['count']) * (1 - Decimal(p) / 100))
                writer.writerow(entry)
    (out / 'fork-endpoints.csv').write_bytes(buffer.getvalue().encode())
    records = []
    for r in rows:
        if r['dataset'] != 'midpoint':
            continue
        for channel, ch in r['stallRates'].items():
            for threshold, rate in ch['rates'].items():
                records.append(dict(batch=r['batch'], label=r['label'], cohort=r['cohort'],
                                    backend=r['backend'], seed=r['seed'], ballastMiB=r['liveMiB'],
                                    block=r['block'], warnings='; '.join(r['warnings']),
                                    channel=channel, thresholdNs=threshold, count=ch['count'], **rate))
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(records[0]), lineterminator='\n'); writer.writeheader(); writer.writerows(records)
    (out / 'fresh-stall-rates.csv').write_bytes(buffer.getvalue().encode())
    lines = ['# Derived result tables', '', 'Generated from `paper-data.json`. All ranges span individual forks; they are not confidence intervals. Ratios use paired quantiles, never pooled histograms.', '',
             '## Fresh primary scheduled response p99.9', '',
             '| Ballast (MiB) | Caffeine range (µs) | Chronicle range (µs) | Paired Ch/C ratios | Clean pairs / all pairs |',
             '| --- | --- | --- | --- | --- |']
    for live in (0,104,208):
        selected=[r for r in rows if r['dataset']=='midpoint' and r['cohort']=='primary' and r['liveMiB']==live]
        pairs=pair_rows(selected)
        ranges=[]
        for backend in BACKENDS:
            values=[r['latency']['response']['percentilesNs']['99.9']/1000 for r in selected if r['backend']==backend]
            ranges.append(f'{min(values):.3f}–{max(values):.3f}')
        values=[b['latency']['response']['percentilesNs']['99.9']/a['latency']['response']['percentilesNs']['99.9'] for a,b in pairs]
        clean=sum(not a['warnings'] and not b['warnings'] for a,b in pairs)
        lines.append(f'| {live} | {ranges[0]} | {ranges[1]} | '+', '.join(f'{v:.6f}' for v in values)+f' | {clean}/{len(pairs)} |')
    lines += ['', '## Historical 256 B saturated service — earlier runtime only', '',
              'Batch `focused-rq2-256-20261108-001`, ordinary get, 512 MiB G1 heap, 8 s measured windows. All selected pairs are warning-free. This is not the fresh scheduled-response protocol.', '',
              '| Ballast (MiB) | Endpoint | Three paired Ch/C ratios | Direction |', '| --- | --- | --- | --- |']
    for live in (448,480):
        selected=[r for r in rows if r['dataset']=='focused' and r['batch']=='focused-rq2-256-20261108-001' and r['regime']=='closed' and r['liveMiB']==live]
        for p in PERCENTILES:
            values=[b['latency']['service']['percentilesNs'][p]/a['latency']['service']['percentilesNs'][p] for a,b in pair_rows(selected)]
            lines.append(f'| {live} | p{p} | '+', '.join(f'{v:.6f}' for v in values)+f' | {direction(values)} |')
    lines += ['', '## Historical 4 KiB saturated service — runtime groups preserved', '',
              'Ordinary get, 8 s measured windows. Each row is three pairs at one point; no cross-runtime interpolation. All selected forks are warning-free. Runtime fingerprints are the historical class-set fingerprints, not the fresh all-runtime-file digest.', '',
              '| Ballast (MiB) | Historical runtime fingerprint | Endpoint | Three paired Ch/C ratios | Direction |',
              '| --- | --- | --- | --- | --- |']
    for live in (328,352,360,364,368):
        selected=[r for r in rows if r['dataset']=='focused' and r['payload']==4096 and r['regime']=='closed' and not r['reuse'] and r['liveMiB']==live]
        require(len(selected) == 6 and len({r['runtimeGroup'] for r in selected}) == 1, "Evidence check failed: len(selected) == 6 and len({r['runtimeGroup'] for r in selected}) == 1")
        for p in PERCENTILES:
            values=[b['latency']['service']['percentilesNs'][p]/a['latency']['service']['percentilesNs'][p] for a,b in pair_rows(selected)]
            lines.append(f'| {live} | `{selected[0]["runtimeGroup"][:12]}` | p{p} | '+', '.join(f'{v:.6f}' for v in values)+f' | {direction(values)} |')
    (out/'RESULT_TABLES.md').write_text('\n'.join(lines)+'\n')


def claims(package, out):
    rows = package['observations']
    fresh = [r for r in rows if r['dataset'] == 'midpoint']
    primary = [r for r in fresh if r['cohort'] == 'primary']
    historical = [r for r in rows if r['dataset'] == 'focused']
    service4k = [r for r in historical if r['payload'] == 4096 and r['regime'] == 'closed' and not r['reuse']]
    service256 = [r for r in historical if r['batch'] == 'focused-rq2-256-20261108-001' and r['regime'] == 'closed']
    result = []

    def add(key, text, evidence, endpoint, figure, limit, status='descriptive result'):
        result.append(dict(id=key, claim=text, status=status, endpoint=endpoint,
                           figure=figure, evidence=[list(identity(r)) for r in sorted(evidence,key=identity)],
                           warningForks=sum(bool(r['warnings']) for r in evidence),
                           sourceGroups=sorted({r['runtimeGroup'] for r in evidence}), limit=limit))

    add('C01', 'The fresh scheduled-response p99.9 ranking changes from Caffeine at 0 MiB to Chronicle at 208 MiB.',
        [r for r in primary if r['liveMiB'] in (0,208)], '4 KiB ordinary get; response p99.9; primary seed; 30 s',
        'fig01_response_replication', 'Three paired forks per endpoint, all clean. Bracket means observed opposite endpoint directions, not a population-threshold confidence interval or an exact/universal threshold.')
    add('C02', '104 MiB remains unresolved; further bisection was skipped under the frozen adaptive rule.',
        [r for r in fresh if r['liveMiB']==104], 'Response p99.9; primary and additional seeds kept separate',
        'fig01_response_replication', 'Primary ratios are mixed with only one clean pair; the two clean additional-seed pairs disagree. No favourable-pair selection.')
    add('C03', 'At response p99.99 and p99.999 Chronicle is lower in every fresh pair, including baseline.',
        fresh,'4 KiB ordinary get; response p99.99/p99.999; 30 s','fig06_percentile_sensitivity',
        'Baseline advantage is not a pressure-emergent crossover. Approximately 15 nominal upper-tail responses per fork at p99.999; not independent stall episodes.')
    add('C04', 'At all five historical 4 KiB saturated points, Caffeine is lower at service p99/p99.9/p99.99.',
        service4k,'Ordinary get; saturated service; 328/352/360 MiB earlier runtime, 364/368 MiB later runtime; 8 s',
        'fig02_estimands','No observed forward service crossover at these endpoints. Do not join runtime groups into one threshold estimate.')
    add('C05', 'Historical 4 KiB saturated service p99.999 favors Chronicle at every tested point, including 328 MiB.',
        service4k,'Ordinary get; saturated service p99.999; 8 s','fig02_estimands',
        'Post hoc extreme endpoint. No newly bracketed pressure crossover; short windows and correlated pauses limit generalisation.')
    add('C06', 'The historical 256 B service ranking is percentile-dependent: p99.9 reverses toward Caffeine, p99.999 toward Chronicle from 448 to 480 MiB.',
        service256,'Earlier runtime only; 256 B; ordinary saturated service; 8 s', 'table: historical payload sensitivity',
        'p99.99 favors Caffeine at both points. Focused payloads use disjoint ballast ranges; this is a within-256 B observation and does not isolate a payload effect or scheduled-response threshold shift.')
    add('C07', 'At 104 MiB, Caffeine response >100 µs probabilities straddle the 0.1% p99.9 tail boundary.',
        [r for r in primary if r['liveMiB']==104 and r['backend']=='CAFFEINE'],
        'Strict response exceedance probability at 100,000 ns', 'fig05_stall_probabilities',
        'Histogram-resolution bounds are not confidence intervals. Explains quantile sensitivity, not the unique cause of each stall.')
    add('C08', 'Ordinary 4 KiB Chronicle access allocates about 4,121.6 worker B/op versus 205.6 for Caffeine.',
        primary,'Worker-thread allocation per completed operation, excluding common churn','fig04_resources',
        'Observed API/workload cost, not universal library overhead; aggregate GC/allocation does not establish event-level causality.')
    add('C09', 'Chronicle lowers retained Java heap occupancy but has higher sampled RSS in the fresh primary cohort.',
        primary,'Post-GC heap fraction and 1 Hz measured-window sampled maximum RSS','fig04_resources',
        'RSS is not PSS or exact native allocation; heap sizes and common demand are equal, total process-memory budgets are not.')
    add('C10', 'Additional seeds repeat the endpoint directions but disagree at 104 MiB.',
        [r for r in fresh if r['cohort']!='primary'],'Response p99.9; one pair per seed per point',
        'fig01_response_replication','Limited descriptive robustness. Three of these forks have JIT warnings; no precise seed-level uncertainty.')
    add('C11', 'Reuse sensitivities compare Caffeine with a different Chronicle borrowed-buffer contract.',
        [r for r in historical if r['batch'].startswith('focused-reuse-') and r['regime']=='arrival'],
        'Scheduled response; 256 B at 480 MiB or 4 KiB at 352 MiB; later runtime; 8 s',
        'fig07_ownership_sensitivity','No contemporaneous ordinary-Chronicle arm in these batches; do not claim a matched three-arm causal improvement or a payload-only effect.')
    add('C12', 'The original unconditional protocol remains NO_GO; conditional completion is preserved.',
        [],'Original campaign acceptance, separate from focused/midpoint datasets','docs/TAILCACHE_12_FINAL_ACCEPTANCE.json',
        '402 planned invocations attempted; 191 conditionally usable campaign forks, one hard rejection, no replacement. Historical stopping-policy amendment stays explicit.',
        'historical qualification limit')
    add('C13', 'No tested universal G1 occupancy threshold, production SLA, or payload-only response threshold shift is established.',
        [],'Scope exclusion','methods and threats to validity',
        'Single host/collector/heap/load; instrumented in-process scheduler; no independent externally arriving load, equal-total-memory intervention or matched 256 B response midpoint study.',
        'unsupported claim boundary')
    add('C14', 'Original same-ballast conditional every-operation p99.9 favors Chronicle at 256 B and Caffeine at 4 KiB at 0/96/208 MiB.',
        [],'Original observer-conditional campaign, separate from the 162 focused/follow-up forks',
        'original-campaign-summary.json', 'Recorder-specific conditional result. No original unconditional qualification or common scheduled-response threshold estimate.',
        'historical conditional observation')
    write_json(out/'claims.json',result)
    lines=['# Claim-to-evidence map', '', 'Prepared from frozen derived inputs; each evidence identity is `(dataset, batch, label)`. The complete identities, warning counts and source groups are in [claims.json](claims.json). No claims are upgraded to confirmatory or causal status.', '',
           '| ID | Allowed statement | Evidence / figure | Limit |','| --- | --- | --- | --- |']
    for r in result:
        lines.append(f'| {r["id"]} | {r["claim"]} | {len(r["evidence"])} forks; {r["warningForks"]} warning-bearing. `{r["figure"]}` | {r["limit"]} |')
    lines += ['', '## Historical-note reconciliation', '',
              '- The cliff diagnostic remains discovery evidence. Its synthetic expected-interval correction is distinct from directly measured intended-arrival response.',
              '- A single diagnostic service win does not override the later repeated ordinary-service findings. “Exact ~97% cliff” and “reuse is mandatory” are not paper claims.',
              '- Lower GC-managed heap and lower RSS are distinct. The fresh RSS observation must appear wherever a memory-saving claim is made.',
              '- Original RQ1 concerns ordinary operation p99/p99.9. Scheduled response and post hoc extreme percentiles are explicitly identified follow-ups.',
              '- RQ2 receives a limited payload-dependent service comparison, not a precise estimate of how the scheduled-response crossover moves with payload.', '']
    (out/'CLAIMS.md').write_text('\n'.join(lines))


def render(package, out):
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/tailcache-paper-mpl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    matplotlib.rcParams.update({'font.size': 9, 'axes.titlesize': 10, 'axes.labelsize': 9,
                               'figure.titlesize': 12, 'svg.fonttype': 'none', 'pdf.fonttype': 42,
                               'axes.spines.top': False, 'axes.spines.right': False,
                               'axes.grid': True, 'grid.alpha': .18, 'savefig.dpi': 240,
                               'svg.hashsalt': 'tailcache-paper-v1', 'path.simplify': False})
    folder = out / 'figures'; folder.mkdir(exist_ok=True)
    rows = package['observations']
    primary = [r for r in rows if r['dataset'] == 'midpoint' and r['cohort'] == 'primary']
    fresh = [r for r in rows if r['dataset'] == 'midpoint']
    figures = []

    def save(fig, name, title, caption, used):
        fig.suptitle(title, fontweight='bold')
        fig.tight_layout(rect=(0, .04, 1, .93))
        fig.text(.02, .015, 'Forks remain separate; hollow markers or dashed curves carry warnings. No pooling or confidence intervals.', fontsize=7)
        for ext in ('svg', 'png', 'pdf'):
            metadata={'Creator': 'TailCache offline paper renderer'}
            if ext=='pdf': metadata.update(CreationDate=None,ModDate=None)
            if ext=='svg': metadata.update(Date=None)
            fig.savefig(folder / f'{name}.{ext}', metadata=metadata)
            if ext=='svg':
                path=folder/f'{name}.{ext}'
                path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
        plt.close(fig)
        figures.append(dict(id=name, title=title, caption=caption,
                            forks=[list(identity(r)) for r in sorted(used, key=identity)]))

    def dot(ax, x, value, row, color, marker='o', size=26):
        ax.scatter(x, value, s=size, marker=marker, edgecolors=color,
                   facecolors='white' if row['warnings'] else color, linewidths=1, zorder=3)

    def ratios(ax, selected, channel, percentiles=PERCENTILES, shift=0, color=None, marker='o'):
        for a, b in pair_rows(selected):
            warning = dict(b, warnings=a['warnings'] + b['warnings'])
            for i, p in enumerate(percentiles):
                dot(ax, i + shift + (a['block'] - 2) * .035,
                    b['latency'][channel]['percentilesNs'][p] / a['latency'][channel]['percentilesNs'][p],
                    warning, color or COLORS[b['backend']], marker)
        ax.axhline(1, color='#555555', ls='--', lw=.8)
        ax.set_yscale('log'); ax.set_xticks(range(len(percentiles)), ['p' + p for p in percentiles])
        ax.set_ylabel('Chronicle / Caffeine latency ratio')

    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.8))
    for r in primary:
        x = r['liveMiB'] + (-5 if r['backend'] == BACKENDS[0] else 5) + (r['block'] - 2) * 1.8
        dot(axes[0], x, r['latency']['response']['percentilesNs']['99.9'] / 1000, r, COLORS[r['backend']])
    axes[0].set(yscale='log', ylabel='Scheduled response p99.9 (µs)', title='(a) Primary seed: three pairs per point')
    for seed, marker, color, offset in ((24301, 'o', '#30363d', -5), (24302, '^', '#a05a00', 0), (24303, 's', '#7756a0', 5)):
        for a, b in pair_rows([r for r in fresh if r['seed'] == seed]):
            warning = dict(b, warnings=a['warnings'] + b['warnings'])
            dot(axes[1], a['liveMiB'] + offset + (a['block'] - 2) * 1.6,
                b['latency']['response']['percentilesNs']['99.9'] / a['latency']['response']['percentilesNs']['99.9'],
                warning, color, marker)
    axes[1].axhline(1, color='#555555', ls='--', lw=.8)
    axes[1].set(yscale='log', ylabel='Paired Chronicle / Caffeine ratio', title='(b) Seeds kept separate; below 1 favors Chronicle')
    for ax in axes:
        ax.set_xticks([0, 104, 208]); ax.set_xlabel('Common application ballast (MiB)')
    axes[0].legend(handles=[Line2D([], [], color=COLORS[b], marker='o', ls='', label=n)
                           for b, n in zip(BACKENDS, ('Caffeine', 'Chronicle ordinary get'))], fontsize=8)
    axes[1].legend(handles=[Line2D([], [], color=c, marker=m, ls='', label=str(s) + (' (3 pairs)' if s == 24301 else ' (1 pair)'))
                           for s, m, c in ((24301, 'o', '#30363d'), (24302, '^', '#a05a00'), (24303, 's', '#7756a0'))], fontsize=7)
    save(fig, 'fig01_response_replication', 'Fresh response crossover: endpoints repeat; 104 MiB remains mixed',
         '4 KiB ordinary get, 512 MiB G1 heap, 50,000 intended arrivals/s, 30 s offered windows. Each marker is a fork (a) or paired ratio (b); horizontal offsets separate observations and do not change ballast. Primary endpoint pairs are clean. At 104 MiB only one primary pair is clean; the two clean additional-seed observations disagree. No curve or exact crossover threshold is fitted.', fresh)

    selected = [r for r in rows if r['dataset'] == 'focused' and r['payload'] == 4096
                and r['batch'] == 'focused-rq1-4k-20261108-001' and r['liveMiB'] == 352 and not r['reuse']]
    require(len(selected) == 12 and len({r['runtimeGroup'] for r in selected}) == 1, "Evidence check failed: len(selected) == 12 and len({r['runtimeGroup'] for r in selected}) == 1")
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.8))
    for ax, regime, channel, title in zip(axes, ('closed', 'arrival'), ('service', 'response'),
                                         ('(a) Saturated service: separate JVMs', '(b) Scheduled response: 50,000/s')):
        use = [r for r in selected if r['regime'] == regime]
        ratios(ax, use, channel); ax.set_title(title)
    save(fig, 'fig02_estimands', 'The latency objective changes the backend ordering',
         'Historical earlier-runtime cohort only: 4 KiB, 352 MiB common ballast, 8 s windows, three pairs per regime. Saturated service and scheduled response use separate JVMs; they are not interchangeable measurements of one run. Points are paired quantile ratios, not ratios of pooled quantiles. Higher percentiles were computed post hoc from retained histograms. No measured compiler warnings occur in these selected forks.', selected)

    fig, axes = plt.subplots(1, 3, figsize=(9.4, 3.6), sharey=True)
    look = {(r['batch'], r['label']): r for r in primary}
    for ax, live in zip(axes, (0, 104, 208)):
        for curve in package['curves']:
            r = look[(curve['batch'], curve['label'])]
            if r['liveMiB'] != live: continue
            bins = decode_curve(curve['response']); total = curve['response']['count']; cumulative = 0; x = []; y = []
            for value, n in bins:
                cumulative += n
                if cumulative < total:
                    x.append(value / 1000); y.append((total - cumulative) / total)
            ax.step(x, y, where='post', color=COLORS[r['backend']], lw=.8,
                    ls='--' if r['warnings'] else '-', alpha=.8)
        ax.axhline(.001, color='#555555', ls=':', lw=.7)
        ax.axhline(1 / 1_500_000, color='#888888', ls=':', lw=.7)
        ax.set(xscale='log', yscale='log', xlim=(10, 10000), ylim=(4e-7, .1),
               xlabel='Response threshold t (µs)', title=f'{live} MiB ballast')
    axes[0].set_ylabel('Empirical P(response > t)')
    axes[0].legend(handles=[Line2D([], [], color=COLORS[b], label=n) for b, n in zip(BACKENDS, ('Caffeine', 'Chronicle'))], fontsize=7)
    save(fig, 'fig03_full_tails', 'Per-fork response tails expose frequency and severity',
         'Fresh primary cohort, three curves per backend per point. Curves preserve every occupied HDR upper-bin boundary in the displayed domain; no pooling or smoothing. Dashed curves carry warnings (rather than the marker convention used elsewhere). P(response > t) is exact for the retained binned distribution at upper boundaries. Dotted horizontal lines mark 0.1% and 1/N (N=1,500,000); they are not confidence bounds. Zero survival beyond a fork maximum is omitted on the logarithmic axis, not replaced with an invented probability. The left edge truncates ordinary fast responses.', primary)

    fig, axes = plt.subplots(2, 2, figsize=(8.8, 6.2))
    metrics = [(lambda r:r['measurement']['workerBytesPerOperation'], 'Worker allocation (B/op)', '(a) Ordinary-get workload allocation'),
               (lambda r:r['gc']['pauseExposureFraction'] * 100, 'GC pause overlap (% wall time)', '(b) GC pause exposure'),
               (lambda r:r['gc']['postGcUsedHeapMedianFraction'] * 100, 'Median post-GC used heap (%)', '(c) GC-managed heap occupancy'),
               (lambda r:r['processMemory']['measuredMaxRssKiB'] / 1024, 'Sampled maximum RSS (MiB)', '(d) Process residency, sampled at 1 Hz')]
    for ax, (metric, label, title) in zip(axes.flat, metrics):
        for r in primary:
            x = r['liveMiB'] + (-5 if r['backend'] == BACKENDS[0] else 5) + (r['block'] - 2) * 1.8
            dot(ax, x, metric(r), r, COLORS[r['backend']])
        ax.set_xticks([0, 104, 208]); ax.set(xlabel='Common application ballast (MiB)', ylabel=label, title=title)
        ax.set_ylim(bottom=0)
    axes[0,0].legend(handles=[Line2D([], [], color=COLORS[b], marker='o', ls='', label=n) for b, n in zip(BACKENDS, ('Caffeine', 'Chronicle'))], fontsize=8)
    save(fig, 'fig04_resources', 'Lower retained Java heap does not imply lower process memory',
         'Fresh primary cohort. GC exposure is pause overlap with the measurement envelope divided by measured duration. Worker B/op excludes the independently offered common churn; heap occupancy is a post-collection summary, not an exact live-object census. RSS is coarse measured-window process residency, not PSS, native allocation or an equal-total-memory comparison. Allocation and GC are consistent mechanism evidence, not per-operation causal attribution.', primary)

    fig, axes = plt.subplots(1, 3, figsize=(9.4, 3.7))
    for ax, threshold in zip(axes, (100000, 1000000, 10000000)):
        for r in primary:
            rate = r['stallRates']['response']['rates'][str(threshold)]
            x = r['liveMiB'] + (-5 if r['backend'] == BACKENDS[0] else 5) + (r['block'] - 2) * 1.8
            ax.vlines(x, rate['lowerProbability'] * 100, rate['upperProbability'] * 100, color=COLORS[r['backend']], lw=2)
            dot(ax, x, rate['lowerProbability'] * 100, r, COLORS[r['backend']])
        ax.set_xticks([0, 104, 208]); ax.set(xlabel='Common ballast (MiB)', ylabel='Response exceedance probability (%)',
                                          title=f'Strictly > {threshold / 1e6:g} ms')
        ax.set_ylim(bottom=-.003, top=.18 if threshold == 100000 else .13 if threshold == 1000000 else .02)
        if threshold == 100000: ax.axhline(.1, color='#555555', lw=.8, ls=':')
        if threshold == 10000000: ax.text(.5, .65, 'Zero observed in all 18 forks\nN = 1,500,000 per fork\nZero observed ≠ zero risk', transform=ax.transAxes, ha='center', fontsize=8)
    save(fig, 'fig05_stall_probabilities', 'A percentile transition can reflect a small change in stall frequency',
         'Fresh primary response histograms. Points and vertical segments show definite–possible strict exceedance probabilities from HDR bin resolution; these are not statistical intervals. At 104 MiB Caffeine >100 µs rates straddle the 0.1% boundary that defines p99.9. The >10 ms panel reports zero observations with the denominator visible. Rates count responses, not independent pause episodes. Exact counts and all seed cohorts are in fresh-stall-rates.csv.', primary)

    fig, axes = plt.subplots(1, 3, figsize=(10, 3.8))
    for ax, cohort, title in zip(axes, ('primary', 'seed24302', 'seed24303'), ('Primary: three pairs', 'Seed 24302: one pair', 'Seed 24303: one pair')):
        for i, (live, color) in enumerate(((0, '#30363d'), (104, '#a05a00'), (208, '#176b91'))):
            ratios(ax, [r for r in fresh if r['cohort']==cohort and r['liveMiB']==live], 'response', shift=(i-1)*.14, color=color)
        ax.set_title(title); ax.set_ylim(.15, 25)
    axes[0].legend(handles=[Line2D([], [], color=c, marker='o', ls='', label=f'{b} MiB') for b,c in ((0,'#30363d'),(104,'#a05a00'),(208,'#176b91'))], fontsize=7)
    save(fig, 'fig06_percentile_sensitivity', 'The extreme response advantage already exists at baseline',
         'All fresh seed cohorts shown separately. Paired Chronicle/Caffeine response ratios at p99 through p99.999, not an interpolated curve. At p99.99 and p99.999 every fresh pair favors Chronicle, including 0 MiB. A 30 s fork contains 1.5 million responses and only approximately 15 nominal upper-tail observations at p99.999; correlated queued responses do not establish independent stall counts.', fresh)

    selected = [r for r in rows if r['dataset']=='focused' and r['batch'] in ('focused-reuse-4k-20261108-001','focused-reuse-256-20261108-001') and r['regime']=='arrival']
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.8))
    for ax, payload, ballast in zip(axes, (4096,256), (352,480)):
        use = [r for r in selected if r['payload']==payload]
        require(len(use) == 6 and len({r['runtimeGroup'] for r in use}) == 1, "Evidence check failed: len(use) == 6 and len({r['runtimeGroup'] for r in use}) == 1")
        for a,b in pair_rows(use,reuse=True):
            warning=dict(b,warnings=a['warnings']+b['warnings'])
            for i,p in enumerate(PERCENTILES):
                dot(ax,i+(a['block']-2)*.04,b['latency']['response']['percentilesNs'][p]/a['latency']['response']['percentilesNs'][p],warning,'#267147','s')
        ax.axhline(1,color='#555555',ls='--',lw=.8);ax.set_yscale('log')
        ax.set_xticks(range(4),['p'+p for p in PERCENTILES]);ax.set(ylabel='Chronicle getUsing / Caffeine response ratio',title=f'{payload} B; {ballast} MiB common ballast')
    axes[0].legend(handles=[Line2D([],[],color='#267147',marker='s',ls='',label='Borrowed-buffer getUsing')],fontsize=7)
    save(fig,'fig07_ownership_sensitivity','Buffer reuse is a separate contract, not an ordinary-get result',
         'Historical later-runtime sensitivity batches, 8 s scheduled response at 50,000/s, three paired blocks comparing Caffeine with Chronicle getUsing. There is no contemporaneous ordinary-Chronicle arm in these batches. The panels use different payloads AND different ballast, and therefore are not a payload-only causal comparison. Reuse permits a caller buffer to be overwritten by the next read. Extreme endpoints are post hoc. This figure is suitable for the appendix.',selected)
    write_json(out / 'figure-index.json', figures)
    captions=['# Paper figures and captions', '', 'Vector PDF and SVG plus 240 dpi PNG are supplied. Figures 1–6 are candidate main-text figures; Figure 7 is an appendix sensitivity. Final manuscript placement remains author review.', '']
    for i,f in enumerate(figures,1):
        captions.extend([f'## Figure {i}. {f["title"]}', '', f'![Figure {i}](figures/{f["id"]}.png)', '', f['caption'], '',
                         f'[PDF](figures/{f["id"]}.pdf) · [SVG](figures/{f["id"]}.svg)', ''])
    (out/'FIGURES.md').write_text('\n'.join(captions))
    return figures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'render'))
    parser.add_argument('--out', type=pathlib.Path, default=DEFAULT)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.out); return
    package = json.loads((args.out / 'paper-data.json').read_text())
    checks = verify(package)
    if args.action == 'verify':
        print(json.dumps(checks)); return
    export_tables(package, args.out)
    claims(package, args.out)
    figures = render(package, args.out)
    write_json(args.out / 'render-manifest.json', dict(
        inputSha256=sha(args.out / 'paper-data.json'), rendererSha256=sha(pathlib.Path(__file__)),
        figures=len(figures), outputs={str(p.relative_to(args.out)):sha(p)
        for p in sorted(args.out.glob('figures/*'))}, checks=checks))
    print(json.dumps(dict(figures=len(figures), directory=str(args.out))))


if __name__ == '__main__':
    main()
