#!/usr/bin/env python3
"""Separate compiler/XML diagnostics for the every-operation worker, never primary data."""
import argparse
import csv
import json
import re

import tailcache12 as evidence
import tailcache12_calibrate as calibration
from tailcache12_analysis import compiler_rejection_reasons
from tailcache12_jit_diagnose import classify_tasks
from tailcache12_study_analysis import every_operation_fork_summary


def replay(attempt):
    manifest = json.loads((attempt / "manifest.json").read_text())
    if manifest["stage"] != "everyop-jit" or calibration.sha(attempt / "source.tar.gz") != manifest["sourceArchiveSha256"]:
        raise ValueError("Wrong diagnostic stage or changed source archive")
    observations = []
    for invocation in manifest["invocations"]:
        raw = calibration.verify_invocation(attempt, invocation)
        worker = raw / "every-operation/worker"
        config = dict(line.split("=", 1) for line in (worker / "configuration.txt").read_text().splitlines() if "=" in line)
        if config.get("compilerXml") != "true" or config.get("compilerCounters") != "true":
            raise ValueError("Missing separate compiler instrumentation")
        with (worker / "iterations.csv").open(newline="") as stream:
            all_rows = list(csv.DictReader(stream))
        rows = [r for r in all_rows if r["phase"] == "MEASUREMENT"]
        windows = [(int(r["startNs"]), int(r["endNs"])) for r in rows]
        summary = every_operation_fork_summary(raw / "every-operation", invocation["properties"],
                                               compiler_diagnostics=True)
        values = summary["compilerPerIterationMs"]
        reasons = summary["rejectionReasons"]
        xml, gc = list((raw / "every-operation").glob("jit-*.xml")), list((raw / "every-operation").glob("gc-*.log"))
        if len(xml) != 1 or len(gc) != 1:
            raise ValueError("Expected one compiler XML and one GC log")
        details = classify_tasks(xml[0], gc[0], windows)
        with (attempt / invocation["label"] / "host.csv").open(newline="") as stream:
            samples = [evidence.decode_host_row(r) for r in csv.DictReader(stream)]
        host_reasons, _ = evidence.replay_host_gate(manifest, raw, samples)
        host_reasons.extend(invocation.get("hostMonitorErrors", []))
        observations.append(dict(label=invocation["label"], compilerPerIterationMs=values,
            compilerTotalMs=sum(values), jitPass=not reasons, hostPass=not host_reasons,
            rejectionReasons=reasons + host_reasons,
            lastWarmupCompilerMs=[int(r["compilerMs"]) for r in all_rows if r["phase"] == "WARMUP"][-5:],
            topPossibleWorkerTasks=sorted((t for t in details["tasks"] if t["location"] == "possible-worker-overlap"),
                                           key=lambda t:t["taskWallMs"], reverse=True)[:20],
            deoptimizationEvents=details["deoptimizationEvents"],
            workerWindowsSeconds=details["workerWindowsSeconds"],
            alignmentUncertaintyMs=details["alignmentUncertaintyMs"]))
    result = dict(schemaVersion="tailcache12-everyop-jit-v1", reportable=False,
        completedBlocks=len(observations), expectedBlocks=len(manifest["expectedBlocks"]),
        qualityPass=len(observations)==len(manifest["expectedBlocks"]) and all(not r["rejectionReasons"] for r in observations),
        observations=observations,
        limits=["Compiler diagnostic forks cannot supply primary latency endpoints.",
                "XML task wall time is not compiler CPU time or JVM pause duration."])
    evidence.save(attempt / "everyop-jit.json", result)
    print(f"everyop-jit={attempt / 'everyop-jit.json'} pass={result['qualityPass']} blocks={len(observations)}/{len(manifest['expectedBlocks'])}",flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=("run","audit"))
    parser.add_argument("attempt_id")
    parser.add_argument("--backends",nargs="+",choices=evidence.BACKENDS,default=list(evidence.BACKENDS))
    parser.add_argument("--payloads",nargs="+",type=int,choices=(256,4096),default=[256,4096])
    parser.add_argument("--repeats",type=int,default=2)
    parser.add_argument("--warmups",type=int,default=60)
    parser.add_argument("--residents",type=int,default=32768)
    parser.add_argument("--heap-mib",type=int,default=512)
    parser.add_argument("--live-mib",type=int,default=0)
    parser.add_argument("--churn-mib",type=int,default=32)
    args=parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._-]+",args.attempt_id): parser.error("Invalid attempt ID")
    attempt=evidence.REPORTS/args.attempt_id
    if args.stage=="audit": return 0 if replay(attempt)["qualityPass"] else 1
    if args.repeats<1 or args.warmups<12: parser.error("Require positive repeats and at least twelve warmups")
    grid=[]
    for repeat in range(1,args.repeats+1):
        for backend in (args.backends if repeat%2 else list(reversed(args.backends))):
            for payload in (args.payloads if repeat%2 else list(reversed(args.payloads))):
                grid.append((f"r{repeat}-{backend}-p{payload}",dict(Backend=backend,Payload=payload,
                    Residents=args.residents,HeapMiB=args.heap_mib,LiveBytes=args.live_mib*1024**2,
                    ChurnBytesPerSecond=args.churn_mib*1024**2,Warmups=args.warmups,Measurements=8,
                    Seed=24301,CompilerDiagnostics="true")))
    args.stage="everyop-jit"
    args.live_mib=[args.live_mib]
    args.measurements=8
    args.channels=["every-operation"]
    args.seed=24301
    args.resume=False
    manifest=calibration.prepare(attempt,args,grid)
    for label,props in grid:
        evidence.invoke(attempt,manifest,label,"tailCache12EveryOperation",props)
        if replay(attempt)["observations"][-1]["rejectionReasons"]: break
    return 0 if replay(attempt)["qualityPass"] else 1


if __name__=="__main__":
    raise SystemExit(main())
