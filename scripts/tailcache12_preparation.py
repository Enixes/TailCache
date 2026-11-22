#!/usr/bin/env python3
"""The prospectively bounded 120-warmup preparation experiment; no calibration launch."""
import argparse
import csv
import json
import subprocess
import sys

import tailcache12 as evidence
import tailcache12_everyop_jit as everyop
import tailcache12_observer as observer
import tailcache12_native_retry as retry


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix")
    args=parser.parse_args()
    if not evidence.re.fullmatch(r"[A-Za-z0-9._-]+",args.prefix): parser.error("Invalid prefix")
    steps=[("quiet","tailcache12_quiet.py",[args.prefix+"-quiet","--quiet-seconds","120","--timeout-seconds","300"]),
        ("jit","tailcache12.py",["jit",args.prefix+"-jit","--warmups","120","--residents","32768"]),
        ("everyop","tailcache12_everyop_jit.py",["run",args.prefix+"-everyop","--warmups","120","--unprofiled"]),
        ("pressure96","tailcache12_everyop_jit.py",["run",args.prefix+"-pressure96","--warmups","120",
            "--backends","CAFFEINE","--payloads","4096","--live-mib","96"]),
        ("floors","tailcache12_observer.py",["floors",args.prefix+"-floors","--warmups","120",
            "--native-host-retries","2","--native-host-retry-budget","8"])]
    checkpoint=evidence.REPORTS/(args.prefix+"-preparation.json")
    if checkpoint.exists() or any((evidence.REPORTS/(args.prefix+"-"+name)).exists() for name,_,_ in steps):
        raise ValueError("Preparation attempt exists; inspect its retained state instead of duplicating it")
    source=evidence.source_hash()
    state=dict(sourceSha256=source,complete=False,warmups=120,measurements=8,completed=[])
    evidence.save(checkpoint,state)
    try:
        for name,script,options in steps:
            if evidence.source_hash()!=source: raise ValueError("Preparation sources changed")
            print("Starting preparation120 "+name,flush=True)
            if subprocess.run([sys.executable,str(evidence.ROOT/"scripts"/script),*options],cwd=evidence.ROOT).returncode:
                raise ValueError(name+" preparation stage rejected; later stages suspended")
            path=evidence.REPORTS/(args.prefix+"-"+name)
            if name=="quiet":
                with (path/"host.csv").open(newline="") as stream:
                    rows=[evidence.decode_host_row(r) for r in csv.DictReader(stream)]
                checked=retry.verify_quiet(path,dict(sourceSha256=source,nativeHostRetryPolicy=retry.declare_policy(2),
                    nativeEnvironmentDeclaration=evidence.native_host.environment_declaration(rows[-1])))
                if not checked["quietPass"]: raise ValueError("Raw quiet replay rejected")
            if name=="jit" and evidence.replay(path): raise ValueError("Raw JMH replay rejected")
            if name in ("everyop","pressure96") and not everyop.replay(path)["qualityPass"]:
                raise ValueError("Raw recorder replay rejected")
            if name=="floors" and not observer.replay_floors(path)["floorDataPass"]:
                raise ValueError("Raw floor replay rejected")
            state["completed"].append(name)
            evidence.save(checkpoint,state)
        state["complete"]=True
        evidence.save(checkpoint,state)
        print("Preparation120 collected and replayed; researcher review and calibration remain.",flush=True)
    except Exception as error:
        state["failure"]=f"{type(error).__name__}: {error}"
        evidence.save(checkpoint,state)
        raise


if __name__=="__main__":
    main()
