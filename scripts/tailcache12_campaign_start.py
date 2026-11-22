#!/usr/bin/env python3
"""Freshly prepare, freeze and run an already-qualified campaign or robustness stage."""
import argparse
import subprocess
import sys

import tailcache12 as evidence
import tailcache12_campaign as campaign
import tailcache12_observer as observer
import tailcache12_pilot as pilot
from tailcache12_calibration_start import prepare_file_cache
from tailcache12_quiet import run_preflight


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('attempt_id'); parser.add_argument('quiet_id')
    parser.add_argument('--pilot',required=True); parser.add_argument('--floors',required=True)
    parser.add_argument('--traces',required=True,type=evidence.pathlib.Path)
    parser.add_argument('--primary'); parser.add_argument('--order-seed',type=int,default=24301)
    args=parser.parse_args()
    if any(x and not evidence.re.fullmatch(r'[A-Za-z0-9._-]+',x)
           for x in (args.attempt_id,args.quiet_id,args.pilot,args.floors,args.primary)):
        parser.error('Invalid evidence identifier')
    attempt=evidence.REPORTS/args.attempt_id; quiet=evidence.REPORTS/args.quiet_id
    cache_path=evidence.REPORTS/(args.quiet_id+'-cache-preparation.json')
    if any(p.exists() for p in (attempt,quiet,cache_path)):
        raise ValueError('Retained campaign/preparation exists; refusing duplication or overwrite')
    source=evidence.source_hash()
    reviewed=observer.coherence(evidence.REPORTS/args.pilot,evidence.REPORTS/args.floors)
    result=pilot.replay(evidence.REPORTS/args.pilot)
    if not reviewed['observerQualified'] or not result['provisionalVariancePass']:
        raise ValueError('Complete raw-replayed pilot/coherence/variance required before preparation')
    if args.primary:
        primary=evidence.REPORTS/args.primary
        campaign.replay(primary)
    cache=prepare_file_cache(cache_path)
    if not run_preflight(quiet,120,300)['quietPass'] or source!=evidence.source_hash():
        raise ValueError('Campaign quiet failed or source changed; no freeze or run')
    evidence.save(quiet/'host-preparation.json',cache)
    command=[sys.executable,str(evidence.ROOT/'scripts/tailcache12_campaign.py')]
    freeze=[*command,'freeze',args.attempt_id,'--initial-quiet',args.quiet_id,
        '--pilot',args.pilot,'--floors',args.floors,'--traces',str(args.traces),
        '--order-seed',str(args.order_seed)]
    if args.primary: freeze.extend(('--primary',args.primary))
    result=subprocess.run(freeze,cwd=evidence.ROOT)
    if result.returncode: return result.returncode
    return subprocess.run([*command,'run',args.attempt_id],cwd=evidence.ROOT).returncode


if __name__=='__main__': raise SystemExit(main())
