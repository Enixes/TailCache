#!/usr/bin/env python3
"""Bounded, resumable ordinary-service experiment. Historical evidence is read-only."""
import argparse
import collections
import csv
import hashlib
import json
import math
import os
import pathlib
import random
import shutil
import statistics
import subprocess
import tarfile
import time

import tailcache12_focused as focus

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = 'io.github.enixes.tailcache.workload.ServiceCrossoverRunner'
BACKENDS = ('CAFFEINE', 'CHRONICLE_IN_MEMORY')
PAYLOADS = (256, 512, 1024, 2048, 4096)
WARM, CONDITION, MEASURE = 12000, 2000, 30000
MAX_WORKLOAD_JVMS = 44
CHANNELS = ('service', 'read-service', 'update-service', 'gap', 'response')
PERCENTILES = ('50', '99', '99.9', '99.99', '99.999')


def check(condition, message):
    if not condition:
        raise ValueError(message)


def source_files():
    files = [ROOT / name for name in ('build.gradle.kts', 'settings.gradle.kts',
             'ops/tailcache12_final_raw_audit.py',
             'docs/TAILCACHE_SERVICE_CROSSOVER_FOLLOWUP_PLAN.md',
             'docs/TAILCACHE_SERVICE_IMPLEMENTATION_REVIEW.md',
             'docs/TAILCACHE_SERVICE_RQ_EXTENSION_PROTOCOL.md',
             'docs/TAILCACHE_SERVICE_PACED_PROTOCOL.md',
             'docs/TAILCACHE_SERVICE_OBSERVER_PROTOCOL.md',
             'docs/TAILCACHE_SERVICE_POLICY_PROTOCOL.md',
             'docs/TAILCACHE_SERVICE_TRACE_PROTOCOL.md',
             'docs/TAILCACHE_SERVICE_OBSERVER_IMPLEMENTATION_REVIEW.md',
             'docs/TAILCACHE_SERVICE_POLICY_TRACE_IMPLEMENTATION_REVIEW.md',
             'docs/TAILCACHE_SERVICE_LARGE_PAYLOAD_PROTOCOL.md',
             'docs/TAILCACHE_SERVICE_GEOMETRY_PROTOCOL.md',
             'docs/TAILCACHE_SERVICE_LARGE_PAYLOAD_IMPLEMENTATION_REVIEW.md',
             'docs/TAILCACHE_SERVICE_GEOMETRY_IMPLEMENTATION_REVIEW.md',
             'docs/TAILCACHE_SERVICE_CROSSOVER_PROTOCOL.md')]
    for directory, pattern in [('src', '*.java'), ('scripts', '*.py'), ('scripts/java', '*.java')]:
        files += sorted((ROOT / directory).rglob(pattern))
    return sorted(set(files))


def source_identity():
    hashes = {str(p.relative_to(ROOT)): focus.sha(p) for p in source_files()}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return digest, hashes


def immutable(path, value):
    if path.exists():
        check(focus.load(path) == value, 'Immutable declaration differs: ' + str(path))
    else:
        focus.save(path, value)


def validate_compilation(compilation, qualification, mode):
    """Bind fresh qualification and compiled classes to their actual sources/dependencies."""
    compiled=focus.load(compilation);qualified=focus.load(qualification)
    check(compiled.get('passed') is True and qualified.get('passed') is True and qualified.get('mode')==mode,
          'Source-matched functional qualification required')
    check(qualified['compilationSha256']==focus.sha(compilation),'Qualification/compiler identity differs')
    for name,digest in compiled['sourceSha256'].items():
        check(focus.sha(ROOT/name)==digest,'Compilation source changed: '+name)
    for name,digest in compiled['compiledRuntime'].items():
        check(focus.sha(compilation.parent/name)==digest,'Qualified compiled class changed: '+name)
    check(qualified['sourceSha256']==compiled['sourceSha256']['scripts/java/PolicyTraceSelfTest.java'],
          'Functional helper source differs')
    reference=ROOT/'evidence-archives/service-followup-20261117-001'
    check(focus.load(reference/'independent-audit-001/audit.json')['protocolSha256']==focus.sha(reference/'protocol.json'),
          'Prior shared-runtime declaration changed')
    for name,digest in focus.load(reference/'protocol.json')['runtimeSha256'].items():
        check(focus.sha(pathlib.Path(name))==digest,'Prior shared runtime changed: '+name)


def pair_specs(stage, payload, live, block=1, seed=24301, reverse=False):
    return [dict(label=f'{stage}-p{payload}-live{live}-b{block}-s{seed}-{backend}',
                 stage=stage, backend=backend, payload=payload, liveMiB=live, block=block,
                 seed=seed, regime='closed', qps=0, reuse=False)
            for backend in (BACKENDS[::-1] if reverse else BACKENDS)]


def screen_schedule():
    cells = [(p, live) for p in PAYLOADS for live in (0, 208)]
    random.Random(24301).shuffle(cells)
    return [r for i, (p, live) in enumerate(cells)
            for r in pair_specs('screen', p, live, reverse=bool(i % 2))]


def bins(path):
    values = [(int(r['upperEquivalentNs']), int(r['count'])) for r in focus.rows(path)]
    check(all(n > 0 for _, n in values), 'Nonpositive occupied-bin count')
    check(all(a[0] < b[0] for a, b in zip(values, values[1:])), 'Unordered bins')
    return dict(values)


def extend_result(directory, result):
    if result['status'] != 'OK' or not result.get('latencyVerified'):
        return result
    result = json.loads(json.dumps(result))
    measured = next(w for w in result['windows'] if w['phase'] == 'MEASUREMENT')
    for channel, count in [('read-service', int(measured['operations']) - int(measured['writes'])),
                           ('update-service', int(measured['writes']))]:
        path = directory / 'worker' / (channel + '-bins.csv')
        values = bins(path)
        check(sum(values.values()) == count, 'Read/update count conservation')
        short = focus.rows(path.with_name(channel + '-summary.csv'))[0]
        check(int(short['count']) == count, 'Read/update summary count')
        result['latency'][channel] = dict(count=count, maxNs=int(short['maxNs']),
                                         percentilesNs={p: focus.rank(path, float(p)) for p in PERCENTILES})
    combined = bins(directory / 'worker/service-bins.csv')
    union = collections.Counter(bins(directory / 'worker/read-service-bins.csv'))
    union.update(bins(directory / 'worker/update-service-bins.csv'))
    check(dict(union) == combined, 'Combined distribution differs from exact read/update union')
    config = focus.properties(directory / 'worker/configuration.txt')
    check(int(config['traceOperations']) == result.get('traceOperations',1000003) and int(config['traceWriteOperations']) == (2000 if result.get('traceOperations')==40001 else 50000),
          'Long trace declaration differs')
    if result.get('tracePattern'):
        check(config.get('tracePattern')==result['tracePattern'],'Actual trace-pattern selection differs')
    result['trace'] = {k: v for k, v in config.items() if k.startswith('trace')}
    result['measurement']['writes'] = int(measured['writes'])
    seconds = (int(measured['endNs']) - int(measured['startNs'])) / 1e9
    result['measurement']['operationsPerSecond'] = int(measured['operations']) / seconds
    result['measurement']['achievedChurnPayloadBytesPerSecond'] = int(measured['churnPayloadBytes']) / seconds
    check(int(measured['churnJvmAllocatedBytes']) >= int(measured['churnPayloadBytes']), 'Churn allocation counter')
    # Full GC and lost allocation demand remain pressure outcomes, not silent exclusions.
    return result


def usable(row):
    return row.get('status') == 'OK' and row.get('latencyVerified') and all(
        row.get('latency', {}).get(c, {}).get('count', 0) > 0 for c in CHANNELS[:-1])


def pairs(rows, stage=None):
    grouped = collections.defaultdict(dict)
    for row in rows:
        if stage is not None and row['stage'] != stage:
            continue
        key = (row['stage'], row['payload'], row['liveMiB'], row['seed'], row['block'])
        check(row['backend'] not in grouped[key], 'Duplicated backend in pair')
        grouped[key][row['backend']] = row
    result = []
    for key, arms in sorted(grouped.items()):
        valid = set(arms) == set(BACKENDS) and all(usable(r) for r in arms.values())
        r = dict(stage=key[0], payload=key[1], liveMiB=key[2], seed=key[3], block=key[4], valid=valid,
                 labels={b: v['label'] for b, v in arms.items()},
                 warnings={b: v.get('warnings', []) for b, v in arms.items()}, ratios={})
        if valid:
            for channel in CHANNELS[:-1]:
                c, h = [arms[b]['latency'][channel]['percentilesNs'] for b in BACKENDS]
                r['ratios'][channel] = {p: h[p] / c[p] for p in PERCENTILES if c[p]}
            check(len({v['trace']['traceSha256'] for v in arms.values()}) == 1, 'Paired traces differ')
            r['ratio'] = r['ratios']['service']['99.9']
        result.append(r)
    return result


def pressure_bracket(points):
    choices = [(b['liveMiB']-a['liveMiB'], a['liveMiB'], a, b) for a in points for b in points
               if a['valid'] and b['valid'] and a['liveMiB'] < b['liveMiB']
               and a['ratio'] >= 1.1 and b['ratio'] <= .9]
    return min(choices, key=lambda x: x[:2])[2:] if choices else None


def select_candidate(screen):
    choices = []
    for payload in PAYLOADS:
        p = {r['liveMiB']: r for r in screen if r['payload'] == payload and r['valid']}
        if set(p) == {0, 208} and p[0]['ratio'] >= 1:
            choices.append((0 if pressure_bracket(list(p.values())) else 1,
                            p[208]['ratio'], p[208]['ratio']/p[0]['ratio'], payload))
    return min(choices)[-1] if choices else None


def next_pressure(points, payload, probe_index):
    bracket = pressure_bracket(points)
    if bracket:
        live = 4 * ((bracket[0]['liveMiB'] + bracket[1]['liveMiB']) // 8)
        return live if live not in {r['liveMiB'] for r in points} else None
    # Select the next common ballast from observed Caffeine occupancy; never equalize the arms.
    valid = [r for r in points if r['valid']]
    if not valid or any(not r['valid'] for r in points):
        return None
    latest = max(valid, key=lambda r: r['liveMiB'])
    occupancy = latest.get('caffeineHeapFraction')
    if occupancy is None:
        return None
    target = (.80, .90, .95, .97)[probe_index]
    cap = 4 * math.floor((512 - 32768*payload/1024**2 - 9*1000003/1024**2 - 24) / 4)
    proposed = min(cap, 4 * math.floor((latest['liveMiB'] + (target-occupancy)*512) / 4))
    return proposed if proposed > latest['liveMiB'] else None


def select_confirmation(rows, candidate):
    discovery = pairs([r for r in rows if r['stage'] in ('screen', 'probe')])
    bracket = pressure_bracket([p for p in discovery if p['payload'] == candidate])
    if bracket:
        return dict(kind='pressure', endpoints=[dict(payload=p['payload'], liveMiB=p['liveMiB']) for p in bracket])
    # A payload boundary answers a different question; declare it before new confirmations.
    for live in (0, 208):
        p = {p['payload']: p for p in discovery if p['stage'] == 'screen' and p['liveMiB'] == live}
        for small, large in zip(PAYLOADS, PAYLOADS[1:]):
            a, b = p.get(small), p.get(large)
            if a and b and a['valid'] and b['valid'] and a['ratio'] <= .9 and b['ratio'] >= 1.1:
                return dict(kind='payload', endpoints=[dict(payload=r['payload'], liveMiB=live) for r in (a,b)])
    return dict(kind='none', endpoints=[])


class Campaign:
    def __init__(self, out, design=None, classpath_file=None):
        self.out = out
        self.cp = (classpath_file or ROOT / 'build/service-followup-20261116/classpath.txt').read_text().strip()
        self.source, hashes = source_identity()
        declaration = out / 'protocol.json'
        if declaration.exists():
            self.protocol = focus.load(declaration)
            check(self.protocol['sourceSha256'] == self.source and self.protocol['classpath'] == self.cp,
                  'Frozen source/runtime path changed; preserve this cohort')
            if design is not None:check(self.protocol.get('design')==design,'Changed extension design')
        else:
            out.mkdir(parents=True, exist_ok=False)
            (out / 'setup').mkdir()
            runtime = {}
            archived_cp = []
            for index, item in enumerate(self.cp.split(os.pathsep)):
                original = pathlib.Path(item)
                destination = out / 'runtime' / str(index)
                if original.is_file():
                    destination.mkdir(parents=True)
                    shutil.copyfile(original, destination / original.name)
                    archived_cp.append(str((destination / original.name).relative_to(out)))
                    runtime[str(original)] = focus.sha(original)
                else:
                    destination.mkdir(parents=True)
                    archived_cp.append(str(destination.relative_to(out)))
                    for file in sorted(original.rglob('*')):
                        if file.is_file():
                            target = destination / file.relative_to(original)
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(file, target)
                            runtime[str(file)] = focus.sha(file)
            self.protocol = dict(version='service-crossover-v1', declaredUtc=focus.now(),
                sourceSha256=self.source, sourceFiles=hashes, runtimeSha256=runtime, classpath=self.cp,
                archivedClasspath=archived_cp, primaryEndpoint=(design or {}).get('primaryEndpoint', 'ordinary 95/5 combined saturated-service p99.9'),
                warmupMs=(design or {}).get('warmupMs',WARM), conditioningMs=(design or {}).get('conditioningMs',CONDITION), measureMs=(design or {}).get('measureMs',MEASURE),
                traceOperations=(design or {}).get('traceOperations',1000003), screen=screen_schedule() if design is None else [],
                maxWorkloadJvms=MAX_WORKLOAD_JVMS if design is None else design['maxWorkloadJvms'],
                design=design,
                controls=(design or {}).get('controls',4), functionalValidationJvms=(design or {}).get('functionalValidationJvms',2),
                meaningfulRatioBounds=[.9,1.1], originalEvidenceUnchanged=True,
                preservedPaperInputs={str(p.relative_to(ROOT)):focus.sha(p) for p in
                    [ROOT/'docs/preprint/paper-data.json',ROOT/'docs/TAILCACHE_12_FINAL_ACCEPTANCE.json',
                     ROOT/'evidence-archives/focused-rq-p99999-20261108-001/study.json',
                     ROOT/'evidence-archives/midpoint-results-20261110-001/study.json']},
                selectionProtocol=(design or {}).get('protocol','docs/TAILCACHE_SERVICE_CROSSOVER_PROTOCOL.md'))
            immutable(declaration, self.protocol)
            with tarfile.open(out / 'source.tar.gz', 'x:gz') as archive:
                for file in source_files():
                    archive.add(file, arcname=str(file.relative_to(ROOT)))
            focus.save(out / 'setup/environment.json', focus.environment_metadata())
            shutil.copyfile(ROOT/(design or {}).get('functionalValidationReceipt','build/service-followup-20261116/functional-validation.json'),
                            out/'setup/functional-validation.json')
            focus.save(out / 'state.json', dict(complete=False, startedUtc=focus.now(), scheduled=[], decisions=[]))
        self.state = focus.load(out / 'state.json')
        self.ready = focus.evidence.host_snapshot()
        check(self.ready.get('nativeScopeQualified') == 1, 'Require exclusive native accounting scope')
        self.check_frozen()

    def check_frozen(self):
        check(source_identity()[0] == self.source, 'Frozen source changed')
        for file, digest in self.protocol['runtimeSha256'].items():
            check(focus.sha(pathlib.Path(file)) == digest, 'Compiled runtime changed: ' + file)
        for file, digest in self.protocol['preservedPaperInputs'].items():
            check(focus.sha(ROOT/file)==digest, 'Prior paper evidence changed: '+file)
        for file,digest in (self.protocol.get('design') or {}).get('discoveryInputs',{}).items():
            check(focus.sha(ROOT/file)==digest,'Discovery input changed: '+file)

    def checkpoint(self):
        focus.save(self.out / 'state.json', self.state)

    def observations(self):
        return [focus.load(self.out / 'slots' / s['label'] / 'service-result.json')
                for s in self.state['scheduled'] if (self.out / 'slots' / s['label'] / 'service-result.json').exists()]

    def execute(self, specs, control=False):
        results = []
        root = self.out / ('controls' if control else 'slots')
        root.mkdir(exist_ok=True)
        for spec in specs:
            path = root / spec['label']
            saved = path / 'service-result.json'
            if saved.exists():
                result = focus.load(saved)
                focus.verify_retained(path, result)
                results.append(result)
                continue
            self.check_frozen()
            ready = focus.evidence.host_snapshot()
            check(shutil.disk_usage(self.out).free >= 512*1024**2, 'Free disk below 512 MiB; resume completed slots')
            check(ready['memAvailableKiB'] >= 1024**2, 'Available memory below 1 GiB')
            check('=0' not in ready.get('externalPower',''), 'External power disconnected')
            check(ready['swapOutPages'] == self.ready['swapOutPages'] and
                  ready['swapInPages'] == self.ready['swapInPages'], 'Paging increased; preserve slots')
            if not control and spec not in self.state['scheduled']:
                check(len(self.state['scheduled']) < self.protocol['maxWorkloadJvms'], 'Workload JVM budget exhausted')
                self.state['scheduled'].append(spec)
                self.checkpoint()
            if path.exists():
                check((path / 'result.json').exists(), 'Interrupted slot retained; explicit adjudication needed: ' + str(path))
                result = focus.load(path / 'result.json')
                focus.verify_retained(path, result)
            else:
                time.sleep(3)
                result = focus.launch(root, spec, self.cp, warmup=self.protocol['warmupMs'], conditioning=self.protocol['conditioningMs'],
                    measure=4000 if control else self.protocol['measureMs'], floor=spec.get('floor',False),
                    inject=spec.get('inject',0), runner=MAIN,
                    extra_args=('--supply-floor',str(spec.get('supply',False)).lower(),
                                *(['--trace-operations',str(spec['traceOperations'])] if 'traceOperations' in spec else []),
                                *spec.get('extraArgs',[])),
                    timeout_seconds=(self.protocol.get('design') or {}).get('processTimeoutSeconds',100))
            result = extend_result(path, result)
            immutable(saved, result)
            if control:
                check(usable(result) if spec.get('supply') else result['status']=='OK' and result['latencyVerified'],
                      'Functional control failed')
                if spec.get('inject'):
                    check(result['latency']['service']['maxNs'] >= 10000000, 'Injected pause not visible')
            results.append(result)
            self.state.update(lastLabel=spec['label'], updatedUtc=focus.now(),
                              collectedWorkloadJvms=len(self.observations()))
            self.checkpoint()
            print('SERVICE_PROGRESS', self.state['collectedWorkloadJvms'], spec['label'], result['status'],
                  'warnings='+str(len(result['warnings'])), flush=True)
        return results

    def decision(self, name, value):
        immutable(self.out / (name + '.json'), value)
        if name not in self.state['decisions']:
            self.state['decisions'].append(name)
            self.checkpoint()

    def run_controls(self):
        controls = []
        for label, payload, floor, supply, inject in [('timer',256,True,False,0),
                ('injected-stall',256,True,False,20), ('supply256',256,False,True,0),
                ('supply4096',4096,False,True,0)]:
            s = pair_specs('control-'+label,payload,0,block=0)[0]
            s.update(residents=64,churnMiB=0,floor=floor,supply=supply,inject=inject)
            controls.append(s)
        self.execute(controls, control=True)

    def run(self):
        self.run_controls()
        self.execute(self.protocol['screen'])
        screen = pairs(self.observations(), 'screen')
        candidate = select_candidate(screen)
        self.decision('candidate', dict(payload=candidate, screenPairs=screen))
        if candidate is not None:
            for index in range(4):
                data = self.observations()
                points = [p for p in pairs(data) if p['stage'] in ('screen','probe') and p['payload']==candidate]
                by_label = {r['label']:r for r in data}
                for p in points:
                    p['caffeineHeapFraction'] = by_label[p['labels']['CAFFEINE']].get('gc',{}).get('postGcUsedHeapMedianFraction')
                before = pressure_bracket(points)
                path = self.out / f'probe-{index}.json'
                if path.exists():
                    decision = focus.load(path)
                else:
                    decision = dict(index=index, payload=candidate, liveMiB=next_pressure(points,candidate,index),
                                    refiningBracket=bool(before), priorPoints=points)
                self.decision(f'probe-{index}', decision)
                if decision['liveMiB'] is None:
                    break
                self.execute(pair_specs('probe', candidate, decision['liveMiB'], reverse=bool(index%2)))
                if decision['refiningBracket']:
                    break
        choice = select_confirmation(self.observations(), candidate)
        self.decision('confirmation-selection', choice)
        if choice['endpoints']:
            cells = [(block,e) for block in (1,2,3) for e in choice['endpoints']]
            random.Random(24302).shuffle(cells)
            for i,(block,e) in enumerate(cells):
                self.execute(pair_specs('confirmation',e['payload'],e['liveMiB'],block=block,reverse=bool(i%2)))
            for i,e in enumerate(choice['endpoints']):
                self.execute(pair_specs('holdout',e['payload'],e['liveMiB'],seed=24302,reverse=bool(i%2)))
        self.check_frozen()
        report(self.out, self.observations(), choice)
        self.state.update(complete=True, collectionComplete=True, researchComplete=False,
                          completedUtc=focus.now(), newWorkloadJvms=len(self.observations()),
                          confirmationKind=choice['kind'], sourceUnchanged=True)
        self.checkpoint()
        print('SERVICE_COLLECTION_COMPLETE', self.out, len(self.observations()), flush=True)


def report(out, rows, choice):
    comparison = pairs(rows)
    result = dict(kind='bounded-service-crossover-followup', collectionComplete=True, confirmationSelection=choice,
                  observations=rows, pairs=comparison, workloadJvms=len(rows), primary='combined service p99.9',
                  limits=['Adaptive discovery and fresh confirmation are separate.',
                          'Additional-seed pairs remain separate; no pooled histograms or significance claim.',
                          'Longer trace and extra recorder channels form a new runtime cohort.',
                          'No crossover and a baseline advantage are valid outcomes.'])
    immutable(out / 'study.json', result)
    with (out / 'pairs.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['stage','payload','ballastMiB','seed','block','valid','serviceP999Ratio',
                         'readP999Ratio','updateP999Ratio','warnings'])
        for p in comparison:
            writer.writerow([p['stage'],p['payload'],p['liveMiB'],p['seed'],p['block'],p['valid'],
                *[p['ratios'].get(c,{}).get('99.9') for c in CHANNELS[:3]],json.dumps(p['warnings'])])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('attempt')
    args = parser.parse_args()
    check(focus.evidence.re.fullmatch('[A-Za-z0-9._-]+',args.attempt), 'Invalid attempt name')
    Campaign(ROOT / 'evidence-archives' / args.attempt).run()
