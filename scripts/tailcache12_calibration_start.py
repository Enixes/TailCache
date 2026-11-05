#!/usr/bin/env python3
"""Collect fresh quiet evidence and immediately launch the declared calibration.

The controller runs across model/usage interruptions. The calibration itself
freezes and replays the quiet reference and enforces its 360-second deadline.
"""
import argparse
import subprocess
import sys

import tailcache12 as evidence
from tailcache12_quiet import run_preflight


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt_id")
    parser.add_argument("quiet_id")
    args=parser.parse_args()
    if any(not evidence.re.fullmatch(r"[A-Za-z0-9._-]+",v) for v in (args.attempt_id,args.quiet_id)):
        parser.error("Invalid attempt IDs")
    attempt,quiet=(evidence.REPORTS/v for v in (args.attempt_id,args.quiet_id))
    if attempt.exists() or quiet.exists():
        raise ValueError("Retained attempt exists; inspect it rather than duplicating or overwriting it")
    source=evidence.source_hash()
    result=run_preflight(quiet,120,300)
    if not result["quietPass"] or source!=evidence.source_hash():
        raise ValueError("Quiet preparation failed or source changed; no calibration launched")
    command=[sys.executable,str(evidence.ROOT/"scripts/tailcache12_calibrate.py"),"calibrate",args.attempt_id,
        "--initial-quiet",args.quiet_id,"--heap-mib","512","--residents","32768","--churn-mib","32",
        "--live-mib","0","96","208","288","--payloads","256","4096","--seed","24301",
        "--warmups","120","--measurements","8","--repeats","2",
        "--native-host-retries","2","--native-host-retry-budget","8"]
    return subprocess.run(command,cwd=evidence.ROOT).returncode


if __name__=="__main__": raise SystemExit(main())
