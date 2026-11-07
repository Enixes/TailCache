#!/usr/bin/env python3
"""One bounded odd-period diagnostic; never qualifies or launches a campaign."""
import argparse
import json
import os
import re
import subprocess
import sys

import tailcache12 as evidence
from tailcache12_calibration_start import prepare_file_cache
from tailcache12_provenance import measurement_source_hash
from tailcache12_quiet import run_preflight

OPAQUE_OPTIONS = (
    '-XX:+UnlockDiagnosticVMOptions',
    '-XX:CompileCommand=dontinline,io.github.enixes.tailcache.workload.CrossoverWorkload::executeNext',
    '-XX:CompileCommand=dontinline,io.github.enixes.tailcache.workload.CrossoverWorkload::executeSupplyFloorNext',
    '-XX:CompileCommand=PrintInlining,io.github.enixes.tailcache.workload.CrossoverLatencyRunner::runWindow',
    '-XX:CompileCommand=PrintInlining,io.github.enixes.tailcache.benchmark.jmh_generated.CrossoverBenchmark_mixedWorkload_jmhTest::mixedWorkload_sample_jmhStub',
)
TLAB_OPTIONS = ('-Xlog:gc+tlab=debug:stdout:timenanos,pid,tid,level,tags',)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('attempt_id')
    parser.add_argument('quiet_id')
    parser.add_argument('--plan', choices=('odd-period', 'mixed-selector', 'opaque-operation', 'tlab-debug'), default='odd-period')
    args = parser.parse_args()
    if any(not re.fullmatch(r'[A-Za-z0-9._-]+', v) for v in (args.attempt_id, args.quiet_id)):
        parser.error('Invalid attempt IDs')
    attempt, quiet = (evidence.REPORTS / v for v in (args.attempt_id, args.quiet_id))
    preparation = evidence.REPORTS / (args.quiet_id + '-cache-preparation.json')
    declaration = evidence.REPORTS / (args.attempt_id + '-declaration.json')
    if any(p.exists() for p in (attempt, quiet, preparation, declaration)):
        raise ValueError('Retained attempt exists; inspect it rather than overwriting or duplicating')
    environment = None
    overrides = {}
    diagnostic_options = []
    if args.plan in ('opaque-operation', 'tlab-debug'):
        if os.environ.get('JAVA_TOOL_OPTIONS'):
            raise ValueError('Inherited JAVA_TOOL_OPTIONS must be absent; refusing an ambiguous diagnostic')
        diagnostic_options = list(OPAQUE_OPTIONS if args.plan == 'opaque-operation' else TLAB_OPTIONS)
        overrides = {'JAVA_TOOL_OPTIONS': ' '.join(diagnostic_options)}
        environment = dict(os.environ, **overrides)
    command = [sys.executable, str(evidence.ROOT / 'scripts/tailcache12_calibrate.py'),
        'probe', args.attempt_id, '--live-mib', '0', '--payloads', '256', '--residents', '32768',
        '--heap-mib', '512', '--churn-mib', '32', '--seed', '24301', '--repeats', '2',
        '--channels', 'sample-calibration', 'every-operation', '--warmups', '120',
        '--conditioning', '16', '--measurements', '8', '--transport-warmup', '--maintenance-warmup']
    source = evidence.source_hash()
    with declaration.open('x') as stream:
        json.dump(dict(command=command, sourceSha256=source,
            measurementSourceSha256=measurement_source_hash(evidence.ROOT),
            expectedJvmAttempts=8, replacements=0, reportable=False,
            primaryEndpointUseAllowed=False, quiet=args.quiet_id,
            environmentOverrides=overrides, diagnosticJvmOptions=diagnostic_options,
            plan={'odd-period':'docs/TAILCACHE_12_SAMPLING_DESIGN_PLAN.md',
                  'mixed-selector':'docs/TAILCACHE_12_SAMPLE_SELECTION_PLAN.md',
                  'opaque-operation':'docs/TAILCACHE_12_OPAQUE_OPERATION_PLAN.md',
                  'tlab-debug':'docs/TAILCACHE_12_TLAB_OBSERVATION_PLAN.md'}[args.plan]), stream, indent=2)
    cache = prepare_file_cache(preparation)
    result = run_preflight(quiet, 120, 300)
    evidence.save(quiet / 'host-preparation.json', cache)
    if not result['quietPass'] or source != evidence.source_hash():
        raise ValueError('Quiet preparation failed or source changed; no diagnostic JVM launched')
    # Probe mode retains every scheduled diagnostic, even a rejected one. It
    # never returns calibrationReady and no old/source-mismatched fork is reused.
    return subprocess.run(command, cwd=evidence.ROOT, env=environment).returncode


if __name__ == '__main__':
    raise SystemExit(main())
