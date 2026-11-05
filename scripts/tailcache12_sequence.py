#!/usr/bin/env python3
"""One guarded source-frozen native qualification sequence, stopping at any failure."""
import argparse
import json
import re
import subprocess
import sys

import tailcache12 as evidence
import tailcache12_calibrate as calibration
import tailcache12_everyop_jit as everyop_jit
import tailcache12_native_retry as retry
import tailcache12_observer as observer
from tailcache12_provenance import archive_measurement_source_hash, measurement_source_hash


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix")
    parser.add_argument("--warmups",type=int,default=96)
    parser.add_argument("--conditioning",type=int,choices=range(65),default=0)
    args=parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._-]+",args.prefix): parser.error("Invalid prefix")
    names=["observer","quiet","functional","pause","jit","everyop","pressure96","floors"]
    paths={name:evidence.REPORTS/(args.prefix+"-"+name) for name in names}
    if any(path.exists() for path in paths.values()):
        raise ValueError("Sequence directory exists; inspect retained manifests rather than relaunching")
    source=evidence.source_hash()
    source_measurement=measurement_source_hash(evidence.ROOT)
    checkpoint=evidence.REPORTS/(args.prefix+"-sequence.json")
    if checkpoint.exists(): raise ValueError("Sequence checkpoint already exists")
    state=dict(sourceSha256=source,measurementSourceSha256=source_measurement,complete=False,
               warmups=args.warmups,conditioning=args.conditioning,
               planned={k:p.name for k,p in paths.items()},completed=[])
    evidence.save(checkpoint,state)
    commands=[("observer","tailcache12_native_probe.py",[paths["observer"].name]),
        ("quiet","tailcache12_quiet.py",[paths["quiet"].name,"--quiet-seconds","120","--timeout-seconds","300"]),
        ("functional","tailcache12.py",["validate",paths["functional"].name]),
        ("pause","tailcache12.py",["pause",paths["pause"].name]),
        ("jit","tailcache12.py",["jit",paths["jit"].name,"--warmups",str(args.warmups),"--conditioning",str(args.conditioning),"--residents","32768"]),
        ("everyop","tailcache12_everyop_jit.py",["run",paths["everyop"].name,"--warmups",str(args.warmups),"--conditioning",str(args.conditioning),"--unprofiled"]),
        ("pressure96","tailcache12_everyop_jit.py",["run",paths["pressure96"].name,"--warmups",str(args.warmups),"--conditioning",str(args.conditioning),
             "--backends","CAFFEINE","--payloads","4096","--live-mib","96"]),
        ("floors","tailcache12_observer.py",["floors",paths["floors"].name,"--warmups",str(args.warmups),"--conditioning",str(args.conditioning),
            "--native-host-retries","2","--native-host-retry-budget","8"])]
    try:
        for name,script,options in commands:
            if evidence.source_hash()!=source: raise ValueError("Source changed during qualification sequence")
            print("Starting "+name,flush=True)
            code=subprocess.run([sys.executable,str(evidence.ROOT/"scripts"/script),*options],cwd=evidence.ROOT).returncode
            if code: raise ValueError(f"{name} failed (exit {code}); evidence retained; later stages suspended")
            path=paths[name]
            if name=="observer":
                result=json.loads((path/"result.json").read_text())
                if not result["passed"] or result["measurementSourceSha256"]!=source_measurement:
                    raise ValueError("Controlled observer proof failed")
            elif name=="quiet":
                declaration=evidence.native_host.environment_declaration(evidence.host_snapshot())
                checked=retry.verify_quiet(path,dict(sourceSha256=source,
                    nativeHostRetryPolicy=retry.declare_policy(2),nativeEnvironmentDeclaration=declaration))
                if not checked["quietPass"]: raise ValueError("Raw quiet replay failed")
            else:
                if archive_measurement_source_hash(path/"source.tar.gz")!=source_measurement:
                    raise ValueError("Qualification sources differ")
                if name in ("functional","pause","jit"):
                    if evidence.replay(path): raise ValueError("Raw functional/compiler replay rejected")
                elif name in ("everyop","pressure96"):
                    if not everyop_jit.replay(path)["qualityPass"]: raise ValueError("Raw every-operation replay rejected")
                elif not observer.replay_floors(path)["floorDataPass"]:
                    raise ValueError("Independent floors failed")
            state["completed"].append(name)
            evidence.save(checkpoint,state)
        state["complete"]=True
        evidence.save(checkpoint,state)
        print("Source-matched qualification and independent floors complete; calibration/pilot/campaign remain.",flush=True)
    except Exception as error:
        state["failure"]=f"{type(error).__name__}: {error}"
        evidence.save(checkpoint,state)
        raise


if __name__=="__main__":
    main()
