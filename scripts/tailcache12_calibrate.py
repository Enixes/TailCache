#!/usr/bin/env python3
"""Task 12C/12D calibration and replay. Exploratory runs cannot launch the campaign.

The calibration grid uses identical inputs in both backends. Quality gates describe
measured occupancy; they never add ballast to force Chronicle to match Caffeine.
"""
import argparse
import csv
import hashlib
import json
import pathlib
import re
import statistics
import subprocess
import tarfile

import tailcache12 as evidence
from tailcache12_analysis import VERSION, every_operation_summary


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def verify_invocation(attempt, invocation):
    raw = evidence.raw_directory(attempt, invocation)
    if invocation["exitCode"] or not invocation["sourceUnchanged"] or not invocation["rawSha256"]:
        raise ValueError("Unsuccessful invocation or missing source/artifact integrity")
    for name, digest in invocation["rawSha256"].items():
        if sha(raw / name) != digest:
            raise ValueError(f"Changed raw artifact: {raw / name}")
    for name, digest in invocation["controlSha256"].items():
        if sha(attempt / invocation["label"] / name) != digest:
            raise ValueError(f"Changed control artifact: {name}")
    return raw


def replay(attempt):
    manifest = json.loads((attempt / "manifest.json").read_text())
    if manifest.get("analysisVersion") != VERSION:
        raise ValueError("Analysis version mismatch")
    if sha(attempt / "source.tar.gz") != manifest["sourceArchiveSha256"]:
        raise ValueError("Changed source snapshot")
    expected = manifest["expectedBlocks"]
    rows, fingerprints = [], {}
    for invocation in manifest["invocations"]:
        raw = verify_invocation(attempt, invocation)
        props = invocation["properties"]
        summary = every_operation_summary(raw / "every-operation", props["ChurnBytesPerSecond"])
        with (attempt / invocation["label"] / "host.csv").open(newline="") as stream:
            host = [{k: (v if k in ("governor", "externalPower") else float(v)) for k, v in row.items()}
                    for row in csv.DictReader(stream)]
        host_reasons, fraction = evidence.host_gate(host)
        host_reasons.extend(invocation.get("hostMonitorErrors", []))
        configuration = (raw / "every-operation/worker/configuration.txt").read_text()
        config = dict(line.split("=", 1) for line in configuration.splitlines() if "=" in line)
        if config["backend"] != props["Backend"]:
            raise ValueError("Backend identity mismatch")
        for name, field in (("Residents", "residentEntries"), ("Payload", "payloadBytes"),
                            ("LiveBytes", "applicationLiveBytes"), ("Seed", "seed")):
            if not re.search(r"\b" + field + "=" + str(props[name]) + r"(?:,|\])", config["config"]):
                raise ValueError(f"Workload input mismatch: {field}")
        if f"-Xms{props['HeapMiB']}m" not in config["jvmArgs"] or f"-Xmx{props['HeapMiB']}m" not in config["jvmArgs"]:
            raise ValueError("Fixed heap evidence missing")
        trace_key = (props["Residents"], props["Seed"])
        identity = (config["traceSha256"], config["valueGenerator"])
        if trace_key in fingerprints and fingerprints[trace_key] != identity:
            raise ValueError("Paired workload fingerprints differ")
        fingerprints[trace_key] = identity
        summary.update(label=invocation["label"], inputs=props,
                       hostPass=not host_reasons, hostRejectionReasons=host_reasons,
                       memoryFullStallFraction=fraction)
        rows.append(summary)
    bands, calibration_errors = [], []
    for backend in evidence.BACKENDS:
        for payload in manifest["inputs"]["payloads"]:
            previous = None
            for live in manifest["inputs"]["liveBytes"]:
                observations = [r for r in rows if r["inputs"]["Backend"] == backend
                                and r["inputs"]["Payload"] == payload and r["inputs"]["LiveBytes"] == live]
                key = f"{backend}/{payload}/{live}"
                if len(observations) != manifest["inputs"]["repeats"]:
                    calibration_errors.append(key + ": missing independent replicas")
                    continue
                fractions = [r["postGcUsedHeapMedianFraction"] for r in observations]
                if any(x is None for x in fractions):
                    calibration_errors.append(key + ": missing measured occupancy")
                    continue
                center = statistics.median(fractions)
                if any(abs(x - center) > 0.05 for x in fractions):
                    calibration_errors.append(key + ": occupancy replicas drift by more than ±5 percentage points")
                if previous is not None and center - previous < 0.05:
                    calibration_errors.append(key + ": adjacent pressure levels separated by less than 5 percentage points")
                previous = center
                bands.append({"backend": backend, "payloadBytes": payload, "applicationLiveBytes": live,
                              "postGcMedianFraction": center, "toleranceFraction": 0.05,
                              "replicaFractions": fractions})
    anchors = sorted((b for b in bands if b["backend"] == "CAFFEINE" and b["payloadBytes"] == 4096),
                     key=lambda b: b["applicationLiveBytes"])
    if manifest["stage"] == "calibrate" and len(anchors) == 4:
        if anchors[0]["postGcMedianFraction"] > 0.4 or not 0.8 <= anchors[-1]["postGcMedianFraction"] < 0.95:
            calibration_errors.append("4-KiB Caffeine anchor does not span low (≤40%) to severe sustainable (80–95%) used heap")
    row_errors = [r["label"] + ": " + reason for r in rows
                  for reason in r["rejectionReasons"] + r["hostRejectionReasons"]]
    errors = row_errors + calibration_errors
    if len(rows) != len(expected) or {r["label"] for r in rows} != set(expected):
        errors.append("calibration grid incomplete")
    result = {"schemaVersion": VERSION, "stage": manifest["stage"], "reportable": False,
              "calibrationReady": not errors and manifest["stage"] == "calibrate",
              "campaignReady": False, "observations": rows, "calibrationBands": bands,
              "rejectionReasons": errors, "completedBlocks": len(rows), "expectedBlocks": len(expected),
              "missingBlocks": [label for label in expected if label not in {r["label"] for r in rows}],
              "limits": ["Exploratory calibration is not primary crossover evidence.",
                         "JIT, observer coherence and the pilot must pass before a campaign.",
                         "Post-GC used heap and old-region capacity are not an exact live-set census."]}
    evidence.save(attempt / "calibration.json", result)
    columns = ["label", "backend", "payloadBytes", "applicationLiveBytes", "postGcMedianFraction",
               "oldRegionsMedianHeapFraction", "pauseCount", "pauseOverlapMs", "pausesPerSecond",
               "serviceP99Ns", "serviceP999Ns", "hostPass", "acceptedForCalibration"]
    with (attempt / "calibration.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, columns)
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(zip(columns, [r["label"], r["inputs"]["Backend"], r["inputs"]["Payload"],
                r["inputs"]["LiveBytes"], r["postGcUsedHeapMedianFraction"], r["oldRegionsMedianHeapFraction"],
                r["pauseCount"], r["pauseOverlapMs"], r["pausesPerSecond"], r["servicePercentilesNs"]["99"],
                r["servicePercentilesNs"]["99.9"], r["hostPass"], not r["rejectionReasons"] and r["hostPass"]])))
    print(f"calibration={attempt / 'calibration.json'} ready={result['calibrationReady']} "
          f"blocks={len(rows)}/{len(expected)}", flush=True)
    return result


def prepare(attempt, args, grid):
    if attempt.exists():
        if not args.resume:
            raise ValueError("Attempt exists; use --resume for an interrupted immutable attempt")
        manifest = json.loads((attempt / "manifest.json").read_text())
        if manifest["sourceSha256"] != evidence.source_hash() or manifest["inputs"] != vars_inputs(args):
            raise ValueError("Cannot resume after source or input changes; use a new attempt ID")
        for invocation in manifest["invocations"]:
            verify_invocation(attempt, invocation)
        return manifest
    attempt.mkdir(parents=True)
    manifest = {"schemaVersion": "tailcache12-calibration-v1", "stage": args.stage, "reportable": False,
                "analysisVersion": VERSION, "sourceSha256": evidence.source_hash(), "inputs": vars_inputs(args),
                "expectedBlocks": [label for label, _ in grid], "invocations": [],
                "gitHead": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=evidence.ROOT, text=True).strip(),
                "gitStatus": subprocess.check_output(["git", "status", "--short"], cwd=evidence.ROOT, text=True)}
    with tarfile.open(attempt / "source.tar.gz", "w:gz") as archive:
        for path in evidence.sources():
            archive.add(path, arcname=str(path.relative_to(evidence.ROOT)))
    manifest["sourceArchiveSha256"] = sha(attempt / "source.tar.gz")
    evidence.save(attempt / "manifest.json", manifest)
    environment = {"initialHost": evidence.host_snapshot(), "commands": {}}
    for label, command in (("cpu", ["lscpu"]), ("java", ["java", "-version"]), ("os", ["uname", "-a"])):
        result = subprocess.run(command, capture_output=True, text=True)
        environment["commands"][label] = {"exitCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    evidence.save(attempt / "environment.json", environment)
    return manifest


def vars_inputs(args):
    return {"heapMiB": args.heap_mib, "residents": args.residents, "churnBytesPerSecond": args.churn_mib * 1024 ** 2,
            "liveBytes": [x * 1024 ** 2 for x in args.live_mib], "payloads": args.payloads, "seed": args.seed,
            "warmups": args.warmups, "measurements": args.measurements, "repeats": args.repeats}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["probe", "calibrate", "audit"])
    parser.add_argument("attempt_id")
    parser.add_argument("--heap-mib", type=int, default=512)
    parser.add_argument("--residents", type=int, default=32768)
    parser.add_argument("--churn-mib", type=int, default=32)
    parser.add_argument("--live-mib", type=int, nargs="+", default=[0, 96, 208, 288])
    parser.add_argument("--payloads", type=int, nargs="+", default=[256, 4096])
    parser.add_argument("--seed", type=int, default=24301)
    parser.add_argument("--warmups", type=int, default=12)
    parser.add_argument("--measurements", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.attempt_id):
        parser.error("Invalid attempt ID")
    attempt = evidence.REPORTS / args.attempt_id
    if args.stage == "audit":
        return 0 if replay(attempt)["calibrationReady"] else 1
    if args.heap_mib < 64 or not 16 <= args.residents <= 32768 or args.churn_mib <= 0:
        parser.error("Invalid heap/resident/churn settings")
    if sorted(set(args.live_mib)) != args.live_mib or min(args.live_mib) < 0 or max(args.live_mib) >= args.heap_mib:
        parser.error("Application live-set levels must be unique, increasing and below the heap")
    if len(set(args.payloads)) != len(args.payloads) or any(p not in (256, 4096) for p in args.payloads):
        parser.error("Payloads must be unique 256/4096 values")
    if args.warmups < 0 or args.measurements < 1 or args.repeats < 1:
        parser.error("Invalid timing/replication")
    if args.stage == "calibrate" and (len(args.live_mib) != 4 or set(args.payloads) != {256, 4096}
                                      or args.warmups < 12 or args.measurements < 8 or args.repeats < 2):
        parser.error("Full calibration requires four levels, both payloads, ≥12/8 iterations and ≥2 repeats")
    grid = []
    for repeat in range(1, args.repeats + 1):
        backends = evidence.BACKENDS if repeat % 2 else tuple(reversed(evidence.BACKENDS))
        payloads = args.payloads if repeat % 2 else list(reversed(args.payloads))
        levels = args.live_mib if repeat % 2 else list(reversed(args.live_mib))
        for live in levels:
            for payload in payloads:
                for backend in backends:
                    label = f"r{repeat}-{backend}-p{payload}-live{live}"
                    grid.append((label, {"Backend": backend, "Payload": payload, "Residents": args.residents,
                        "LiveBytes": live * 1024 ** 2, "ChurnBytesPerSecond": args.churn_mib * 1024 ** 2,
                        "HeapMiB": args.heap_mib, "Warmups": args.warmups, "Measurements": args.measurements,
                        "Seed": args.seed}))
    manifest = prepare(attempt, args, grid)
    completed = {x["label"] for x in manifest["invocations"]}
    for label, props in grid:
        if label in completed:
            continue
        # A failed host gate suspends a calibration grid; a small functional probe explicitly
        # preserves both backend diagnostics and never receives calibration-ready status.
        if args.stage == "calibrate" and manifest["invocations"] and not manifest["invocations"][-1]["hostQualityPass"]:
            break
        raw = evidence.invoke(attempt, manifest, label, "tailCache12EveryOperation", props)
        summary = every_operation_summary(raw / "every-operation", props["ChurnBytesPerSecond"])
        evidence.save(attempt / label / "gc-analysis.json", summary)
    result = replay(attempt)
    if args.stage == "probe":
        return 0 if len(result["observations"]) == len(grid) else 1
    return 0 if result["calibrationReady"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
