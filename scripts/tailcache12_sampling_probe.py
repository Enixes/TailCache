#!/usr/bin/env python3
"""One bounded odd-period diagnostic; never qualifies or launches a campaign."""
import argparse
import json
import re
import subprocess
import sys

import tailcache12 as evidence
from tailcache12_calibration_start import prepare_file_cache
from tailcache12_provenance import measurement_source_hash
from tailcache12_quiet import run_preflight


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('attempt_id')
    parser.add_argument('quiet_id')
    args = parser.parse_args()
    if any(not re.fullmatch(r'[A-Za-z0-9._-]+', v) for v in (args.attempt_id, args.quiet_id)):
        parser.error('Invalid attempt IDs')
    attempt, quiet = (evidence.REPORTS / v for v in (args.attempt_id, args.quiet_id))
    preparation = evidence.REPORTS / (args.quiet_id + '-cache-preparation.json')
    declaration = evidence.REPORTS / (args.attempt_id + '-declaration.json')
    if any(p.exists() for p in (attempt, quiet, preparation, declaration)):
        raise ValueError('Retained attempt exists; inspect it rather than overwriting or duplicating')
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
            plan='docs/TAILCACHE_12_SAMPLING_DESIGN_PLAN.md'), stream, indent=2)
    cache = prepare_file_cache(preparation)
    result = run_preflight(quiet, 120, 300)
    evidence.save(quiet / 'host-preparation.json', cache)
    if not result['quietPass'] or source != evidence.source_hash():
        raise ValueError('Quiet preparation failed or source changed; no diagnostic JVM launched')
    # Probe mode retains every scheduled diagnostic, even a rejected one. It
    # never returns calibrationReady and no old/source-mismatched fork is reused.
    return subprocess.run(command, cwd=evidence.ROOT).returncode


if __name__ == '__main__':
    raise SystemExit(main())
