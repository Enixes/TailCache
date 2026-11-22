#!/usr/bin/env python3
"""Native metadata/cold-readiness and unchanged inside/outside CPU control; no cache."""
import argparse
import json
import sys
import tailcache12 as evidence
import tailcache12_native_probe as cpu


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('attempt_id');args=parser.parse_args()
    if not evidence.re.fullmatch('[A-Za-z0-9._-]+',args.attempt_id):parser.error('Invalid ID')
    path=evidence.REPORTS/(args.attempt_id+'-cold-readiness.json')
    if path.exists():raise ValueError('Retained cold control exists')
    source=evidence.source_hash();record=evidence.prepare_cold_launch(path,source)
    evidence.replay_cold_launch(path,source,evidence.host_snapshot())
    counts,times=evidence.thermal_values(record['samples'][-1])
    print(json.dumps(dict(coldReadinessPass=True,countFields=len(counts),durationFields=len(times))))
    sys.argv=[__file__,args.attempt_id]
    return cpu.main()


if __name__=='__main__':raise SystemExit(main())
