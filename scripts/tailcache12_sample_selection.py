"""Replay actual generated sampler provenance; legacy raw data stay version scoped."""
import hashlib
import re

LEGACY_VERSION = 'murmur-finalizer-lcg-v1'
VERSION = 'fixed-mixed-lcg-mask15-v1'
DENSE_VERSION = 'fixed-mixed-lcg-mask15-dense-v1'
PACKAGE = 'io.github.enixes.tailcache.benchmark.jmh_generated.'
OLD = 'boolean sample = (rnd & rndMask) == 0;'
NEW = 'boolean sample = io.github.enixes.tailcache.workload.JmhSampleSelector.select(rnd, rndMask);'
MARKER = '\n    public static final String TAILCACHE_SAMPLE_SELECTION_VERSION = "' + VERSION + '";'
ADAPTIVE = ('                if (currentStride++ > targetSamples) {\n'
            '                    buffer.half();\n'
            '                    currentStride = 0;\n'
            '                    rndMask = (rndMask << 1) + 1;\n'
            '                }')
DENSE_PATCHES = (
    ('        int currentStride = 0;\n        do {',
     '        int currentStride = 0;\n        long densePreviousEnd = System.nanoTime();\n'
     '        l_pressurestate1_G.beginDenseWindow(densePreviousEnd);\n        do {'),
    ('            if (sample) {\n                time = System.nanoTime();\n            }',
     '            time = System.nanoTime();'),
    ('            if (sample) {\n                buffer.add((System.nanoTime() - time) / opsPerInv);\n'
     '                // Fixed sampling: retain every selected observation without decimation.\n            }',
     '            long denseEnd;\n            if (sample) {\n'
     '                denseEnd = System.nanoTime();\n'
     '                buffer.add((denseEnd - time) / opsPerInv);\n            } else {\n'
     '                denseEnd = System.nanoTime();\n            }\n'
     '            l_pressurestate1_G.recordDense(time, denseEnd, densePreviousEnd);\n'
     '            densePreviousEnd = denseEnd;'),
    ('        startRndMask = Math.max(startRndMask, rndMask);\n        result.realTime = realTime;\n'
     '        result.measuredOps = operations;',
     '        startRndMask = Math.max(startRndMask, rndMask);\n        result.realTime = realTime;\n'
     '        result.measuredOps = operations;\n'
     '        l_pressurestate1_G.finishDenseWindow(operations, densePreviousEnd);'),
)


def transform(original, declaration, version):
    if version not in (VERSION,LEGACY_VERSION,DENSE_VERSION):raise ValueError('Unknown sampler version')
    if original.count(OLD)!=1 or original.count(declaration)!=1:
        raise ValueError('Unexpected original JMH generated source')
    result=original.replace(OLD,NEW).replace(declaration,declaration+
        '\n    public static final String TAILCACHE_SAMPLE_SELECTION_VERSION = "'+version+'";')
    if version in (VERSION,DENSE_VERSION):
        if original.count('int rndMask = startRndMask;')!=1 or original.count(ADAPTIVE)!=1:
            raise ValueError('Unexpected original JMH adaptation')
        result=result.replace('int rndMask = startRndMask;','int rndMask = 15;').replace(ADAPTIVE,
            '                // Fixed sampling: retain every selected observation without decimation.')
    if version==DENSE_VERSION:
        for old,new in DENSE_PATCHES:
            if result.count(old)!=1:raise ValueError('Unexpected original dense-observer sample stub')
            result=result.replace(old,new)
    return result


def verify(directory, jvm_args, text, method):
    flags = [a for a in jvm_args if a.startswith('-Dtailcache12.sampleSelectionVersion=')]
    versions = set(re.findall(r'(?:^|\s)sampleSelectionVersion=([^\s,]+)', text, re.M))
    records = list(directory.glob('sample-selection-*.properties'))
    source = directory / 'sample-selection-source'
    if not flags and not versions and not records and not source.exists():
        return None  # Original unmodified generated sampler, never relabelled.
    if len(versions)!=1:raise ValueError('Missing or mixed sampler versions')
    version=next(iter(versions))
    if version not in (VERSION,LEGACY_VERSION,DENSE_VERSION) or flags != ['-Dtailcache12.sampleSelectionVersion=' + version] or len(records) != 1:
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
    if (props['sampleSelectionVersion'] != version or props['harnessClass'] != expected_class
            or not props['harnessOrigin'].startswith('file:')
            or not props['harnessOrigin'].endswith('/tailcache12-dense-sampler/' if version==DENSE_VERSION else '/tailcache12-sampler/')):
        raise ValueError('Loaded harness was not the declared Task12-only overlay')
    for part, field in (('harness', 'harnessSha256'), ('selector', 'selectorSha256')):
        data = (directory / ('sample-' + part + '-' + match[1] + '.class')).read_bytes()
        if (not data.startswith(bytes.fromhex('cafebabe'))
                or hashlib.sha256(data).hexdigest() != props[field]):
            raise ValueError('Actual sampler class bytes/hash differ')
        token = b'JmhSampleSelector' if part == 'harness' else version.encode()
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
        expected = transform(original,declaration,version)
        if (source / overlay_name).read_text() != expected:
            raise ValueError('Overlay differs from the exact versioned sampling transformation')
    if {p.name for p in source.iterdir()} != expected_names:
        raise ValueError('Unexpected or missing generated sampler source')
    return dict(props, stockJmhCoreVersion='1.37', modifiedGeneratedSampler=True,
                samplingMask='adaptive' if version==LEGACY_VERSION else 15,adaptiveDecimation=version==LEGACY_VERSION,
                denseObserverWork=version==DENSE_VERSION,
                interpretation='Deterministic mixed LCG selection; not independent Bernoulli sampling')
