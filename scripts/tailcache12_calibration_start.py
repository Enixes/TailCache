#!/usr/bin/env python3
"""Collect fresh quiet evidence and immediately launch the declared calibration.

The controller runs across model/usage interruptions. The calibration itself
freezes and replays the quiet reference and enforces its 360-second deadline.
"""
import argparse
import json
import subprocess
import sys

import tailcache12 as evidence
from tailcache12_quiet import run_preflight
from tailcache12_provenance import archive_measurement_source_hash,measurement_source_hash


def qualification_bindings(prefix):
    """Bind the reviewed qualification to this checkout and current native boot."""
    import tailcache12_calibrate as calibration
    import tailcache12_pilot as pilot
    expected=measurement_source_hash(evidence.ROOT)
    manifests=[]
    refs={}
    for name,report,flag in (("functional","replayed-audit.json","functionalPass"),
            ("pause","replayed-audit.json","functionalPass"),("jit","replayed-audit.json","functionalPass"),
            ("everyop","everyop-jit.json","qualityPass"),("pressure96","everyop-jit.json","qualityPass"),
            ("floors","floors.json","floorDataPass")):
        path=evidence.REPORTS/(prefix+"-"+name)
        manifest=json.loads((path/"manifest.json").read_text())
        result=json.loads((path/report).read_text())
        if (not result[flag] or calibration.sha(path/"source.tar.gz")!=manifest["sourceArchiveSha256"]
                or archive_measurement_source_hash(path/"source.tar.gz")!=expected):
            raise ValueError("Reviewed qualification source or acceptance changed: "+name)
        if name in ("jit","everyop") and len(manifest["invocations"])!=8:
            raise ValueError("Incomplete compiler qualification reference")
        if name=="everyop" and result.get("compilerXml") is not False:
            raise ValueError("Qualification did not exercise the actual unprofiled recorder")
        if name in ("jit","everyop","pressure96","floors") and any(
                v["properties"].get("Warmups")!=120 or v["properties"].get("Conditioning")!=8
                or v["properties"].get("TransportWarmupVersion")!=evidence.TRANSPORT_WARMUP_VERSION
                for v in manifest["invocations"]):
            raise ValueError("Qualification preparation controls differ from the declared grid")
        manifests.append(manifest)
        refs[name]=dict(attempt=path.name,manifestSha256=calibration.sha(path/"manifest.json"),
            sourceArchiveSha256=manifest["sourceArchiveSha256"],measurementSourceSha256=expected)
    pilot.verify_native_environments(manifests,evidence.host_snapshot())
    return refs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt_id")
    parser.add_argument("quiet_id")
    parser.add_argument("--qualification-prefix",required=True)
    args=parser.parse_args()
    if any(not evidence.re.fullmatch(r"[A-Za-z0-9._-]+",v) for v in (args.attempt_id,args.quiet_id,args.qualification_prefix)):
        parser.error("Invalid attempt IDs")
    attempt,quiet=(evidence.REPORTS/v for v in (args.attempt_id,args.quiet_id))
    if attempt.exists() or quiet.exists():
        raise ValueError("Retained attempt exists; inspect it rather than duplicating or overwriting it")
    bindings=qualification_bindings(args.qualification_prefix)
    source=evidence.source_hash()
    result=run_preflight(quiet,120,300)
    if not result["quietPass"] or source!=evidence.source_hash():
        raise ValueError("Quiet preparation failed or source changed; no calibration launched")
    evidence.save(quiet/"qualification-bindings.json",dict(prefix=args.qualification_prefix,
        sourceSha256=source,qualificationRefs=bindings))
    command=[sys.executable,str(evidence.ROOT/"scripts/tailcache12_calibrate.py"),"calibrate",args.attempt_id,
        "--initial-quiet",args.quiet_id,"--heap-mib","512","--residents","32768","--churn-mib","32",
        "--qualification-prefix",args.qualification_prefix,
        "--live-mib","0","96","208","288","--payloads","4096","256","--high-first","--seed","24301",
        "--warmups","120","--conditioning","8","--transport-warmup","--measurements","8","--repeats","2",
        "--native-host-retries","2","--native-host-retry-budget","8"]
    return subprocess.run(command,cwd=evidence.ROOT).returncode


if __name__=="__main__": raise SystemExit(main())
