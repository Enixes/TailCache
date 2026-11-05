#!/usr/bin/env python3
"""Prevalidate, prepare and immediately launch one immutable native pilot."""
import argparse
import subprocess
import sys

import tailcache12 as evidence
import tailcache12_pilot as pilot
from tailcache12_calibration_start import prepare_file_cache,qualification_bindings
from tailcache12_quiet import run_preflight


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('attempt_id')
    parser.add_argument('quiet_id')
    parser.add_argument('--qualification-prefix',required=True)
    parser.add_argument('--calibration',required=True)
    parser.add_argument('--everyop-reference')
    args=parser.parse_args()
    if any(x is not None and not evidence.re.fullmatch(r'[A-Za-z0-9._-]+',x) for x in vars(args).values()):
        parser.error('Invalid attempt identifier')
    attempt=evidence.REPORTS/args.attempt_id; quiet=evidence.REPORTS/args.quiet_id
    cache_path=evidence.REPORTS/(args.quiet_id+'-cache-preparation.json')
    if any(p.exists() for p in (attempt,quiet,cache_path)):
        raise ValueError('Retained pilot/preparation exists; inspect it instead of duplicating or overwriting')
    source=evidence.source_hash()
    qualification_bindings(args.qualification_prefix,args.everyop_reference)
    ids=[args.qualification_prefix+'-'+suffix for suffix in ('functional','jit')]
    ids.extend((args.calibration,args.everyop_reference or args.qualification_prefix+'-everyop'))
    pilot.qualification_refs(*(evidence.REPORTS/x for x in ids))
    cache=prepare_file_cache(cache_path)
    result=run_preflight(quiet,120,300)
    if not result['quietPass'] or evidence.source_hash()!=source:
        raise ValueError('Pilot preparation failed or source changed; no pilot launched')
    evidence.save(quiet/'host-preparation.json',cache)
    command=[sys.executable,str(evidence.ROOT/'scripts/tailcache12_pilot.py'),'pilot',args.attempt_id,
        '--initial-quiet',args.quiet_id,'--functional',ids[0],'--jit',ids[1],
        '--calibration',ids[2],'--everyop-jit',ids[3],
        '--native-host-retries','2','--native-host-retry-budget','8']
    return subprocess.run(command,cwd=evidence.ROOT).returncode


if __name__=='__main__': raise SystemExit(main())
