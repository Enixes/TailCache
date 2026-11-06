"""Replay actual generated sampler provenance; legacy raw data stay version scoped."""
import hashlib
import re

VERSION = 'murmur-finalizer-lcg-v1'
PACKAGE = 'io.github.enixes.tailcache.benchmark.jmh_generated.'
OLD = 'boolean sample = (rnd & rndMask) == 0;'
NEW = 'boolean sample = io.github.enixes.tailcache.workload.JmhSampleSelector.select(rnd, rndMask);'
MARKER = '\n    public static final String TAILCACHE_SAMPLE_SELECTION_VERSION = "' + VERSION + '";'


def verify(directory, jvm_args, text, method):
    flags = [a for a in jvm_args if a.startswith('-Dtailcache12.sampleSelectionVersion=')]
    versions = set(re.findall(r'(?:^|\s)sampleSelectionVersion=([^\s,]+)', text, re.M))
    records = list(directory.glob('sample-selection-*.properties'))
    source = directory / 'sample-selection-source'
    if not flags and not versions and not records and not source.exists():
        return None  # Original unmodified generated sampler, never relabelled.
    if flags != ['-Dtailcache12.sampleSelectionVersion=' + VERSION] or versions != {VERSION} or len(records) != 1:
        raise ValueError('Missing, mixed or unknown generated sample selection declaration')
    path = records[0]
    match = re.fullmatch(r'sample-selection-(\d+)\.properties', path.name)
    if not match:
        raise ValueError('Invalid sample-selection worker identity')
    lines = [line.split('=', 1) for line in path.read_text().splitlines()]
    required = {'sampleSelectionVersion', 'harnessClass', 'harnessOrigin', 'harnessSha256', 'selectorSha256'}
    if any(len(row) != 2 for row in lines) or len(lines) != len(required) or {row[0] for row in lines} != required:
        raise ValueError('Incomplete or duplicate sample-selection evidence')
    props = dict(lines)
    expected_class = PACKAGE + 'CrossoverBenchmark_' + method + '_jmhTest'
    if (props['sampleSelectionVersion'] != VERSION or props['harnessClass'] != expected_class
            or not props['harnessOrigin'].startswith('file:')
            or not props['harnessOrigin'].endswith('/tailcache12-sampler/')):
        raise ValueError('Loaded harness was not the declared Task12-only overlay')
    for part, field in (('harness', 'harnessSha256'), ('selector', 'selectorSha256')):
        data = (directory / ('sample-' + part + '-' + match[1] + '.class')).read_bytes()
        if (not data.startswith(bytes.fromhex('cafebabe'))
                or hashlib.sha256(data).hexdigest() != props[field]):
            raise ValueError('Actual sampler class bytes/hash differ')
        token = b'JmhSampleSelector' if part == 'harness' else VERSION.encode()
        if token not in data:
            raise ValueError('Loaded class lacks the declared selector linkage/version')
    if ({m[1] for m in re.finditer(r'sampleHarnessSha256=([0-9a-f]{64})', text)} != {props['harnessSha256']}
            or {m[1] for m in re.finditer(r'sampleSelectorSha256=([0-9a-f]{64})', text)} != {props['selectorSha256']}):
        raise ValueError('Worker console and actual sampler class hashes disagree')
    expected_names = set()
    for name in ('mixedWorkload', 'freshSupplyFloor'):
        class_name = 'CrossoverBenchmark_' + name + '_jmhTest'
        original_name, overlay_name = ('original-' + class_name + '.java', 'overlay-' + class_name + '.java')
        expected_names.update((original_name, overlay_name))
        original = (source / original_name).read_text()
        declaration = 'public final class ' + class_name + ' {'
        if original.count(OLD) != 1 or original.count(declaration) != 1:
            raise ValueError('Unexpected original JMH generated source')
        expected = original.replace(OLD, NEW).replace(declaration, declaration + MARKER)
        if (source / overlay_name).read_text() != expected:
            raise ValueError('Overlay changed more than selector expression/version marker')
    if {p.name for p in source.iterdir()} != expected_names:
        raise ValueError('Unexpected or missing generated sampler source')
    return dict(props, stockJmhCoreVersion='1.37', modifiedGeneratedSampler=True,
                interpretation='Deterministic mixed LCG selection; not independent Bernoulli sampling')
