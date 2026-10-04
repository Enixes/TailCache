#!/usr/bin/env python3
"""Counterbalanced TailCache 08 matrix with preserved raw files and conservative audit."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODES = ["CAFFEINE", "CHRONICLE_IN_MEMORY", "CHRONICLE_PERSISTED"]
PAYLOADS = ["BYTES_256", "KIB_4"]
TASKS = {"latency": "tailCache08Latency", "throughput": "tailCache08Throughput",
         "diagnostics": "tailCache08Diagnostics", "jfr": "tailCache08Jfr"}
SOURCE_PATHS = ["build.gradle.kts", "settings.gradle.kts", "gradlew", "gradle/wrapper",
                "src/main", "src/jmh", "scripts/tailcache08.py", "docs/TAILCACHE_08_10_PLAN.md"]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def capture(command):
    try:
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                                timeout=20, check=False)
        return {"code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"error": str(error)}


def environment():
    files = {}
    for name in ["/proc/meminfo", "/proc/pressure/memory", "/proc/pressure/io",
                 "/proc/cpuinfo", "/proc/mounts", "/proc/swaps"]:
        try:
            files[name] = pathlib.Path(name).read_text()
        except OSError as error:
            files[name] = str(error)
    return {"atUtc": dt.datetime.now(dt.timezone.utc).isoformat(), "files": files,
            "sourceSha256": source_digest(),
            "uname": capture(["uname", "-a"]), "java": capture(["java", "-version"]),
            "gitHead": capture(["git", "rev-parse", "HEAD"]),
            "gitStatus": capture(["git", "status", "--short"]),
            "findmnt": capture(["findmnt", "-J", "-T", str(ROOT / "build")]),
            "lsblk": capture(["lsblk", "-J", "-o", "NAME,TYPE,SIZE,ROTA,TRAN,FSTYPE,MOUNTPOINTS,MODEL"]),
            "cpuGovernor": capture(["cat", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"])}


def source_files():
    for name in SOURCE_PATHS:
        path = ROOT / name
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from sorted(p for p in path.rglob("*") if p.is_file())


def source_digest():
    digest = hashlib.sha256()
    for path in source_files():
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def run_block(run_id, block, kind, modes, payload, warmup, measure, forks, run_dir):
    command = [str(ROOT / "gradlew"), "--offline", TASKS[kind],
               f"-Ptailcache08RunId={run_id}", f"-Ptailcache08Block={block}",
               f"-Ptailcache08Modes={','.join(modes)}", f"-Ptailcache08Payload={payload}",
               f"-Ptailcache08WarmupIterations={warmup}",
               f"-Ptailcache08MeasurementIterations={measure}", f"-Ptailcache08Forks={forks}"]
    raw = run_dir / block / kind
    control = run_dir / "orchestration" / block / kind
    control.mkdir(parents=True, exist_ok=False)
    save(control / "before.json", environment())
    with (control / "gradle.log").open("w") as log:
        code = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
    save(control / "after.json", environment())
    item = {"block": block, "kind": kind, "modes": modes, "payload": payload,
            "warmup": warmup, "measure": measure, "forks": forks, "command": command,
            "exitCode": code, "rawDirectory": str(raw), "files": []}
    if raw.exists():
        item["files"] = [{"path": str(p.relative_to(raw)), "bytes": p.stat().st_size,
                          "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                         for p in sorted(raw.rglob("*")) if p.is_file()]
    save(control / "invocation.json", item)
    print(f"{block}/{kind}: exit {code}", flush=True)
    return item


def audit(run_dir, manifest):
    rows, errors, host_observations, diagnostic_observations = [], [], [], []
    if "sourceSha256" in manifest:
        if not (run_dir / "source-snapshot.tar.gz").exists():
            errors.append("source snapshot missing")
        for item in manifest["invocations"]:
            for phase in ("before", "after"):
                path = run_dir / "orchestration" / item["block"] / item["kind"] / f"{phase}.json"
                try:
                    observed = json.loads(path.read_text())["sourceSha256"]
                except (OSError, ValueError, KeyError):
                    observed = None
                if observed != manifest["sourceSha256"]:
                    errors.append(f"{item['block']}/{item['kind']}: source changed at {phase}")
    for item in manifest["invocations"]:
        raw = pathlib.Path(item["rawDirectory"])
        control = run_dir / "orchestration" / item["block"] / item["kind"]
        try:
            before = json.loads((control / "before.json").read_text())
            after = json.loads((control / "after.json").read_text())
            def mem_kib(snapshot, label):
                match = re.search(r"^" + label + r":\s*(\d+)",
                                  snapshot["files"]["/proc/meminfo"], re.MULTILINE)
                return int(match.group(1)) if match else None
            def full_psi(snapshot):
                match = re.search(r"^full avg10=([0-9.]+)",
                                  snapshot["files"]["/proc/pressure/memory"], re.MULTILINE)
                return float(match.group(1)) if match else None
            swap_before = mem_kib(before, "SwapTotal") - mem_kib(before, "SwapFree")
            swap_after = mem_kib(after, "SwapTotal") - mem_kib(after, "SwapFree")
            observation = {"block": item["block"], "kind": item["kind"],
                           "swapUsedBeforeMiB": round(swap_before / 1024, 1),
                           "swapUsedAfterMiB": round(swap_after / 1024, 1),
                           "swapUsedIncreaseMiB": round((swap_after - swap_before) / 1024, 1),
                           "memoryFullPsiAvg10Before": full_psi(before),
                           "memoryFullPsiAvg10After": full_psi(after)}
            host_observations.append(observation)
            if swap_after - swap_before > 256 * 1024:
                errors.append(f"{item['block']}/{item['kind']}: swap use rose by more than 256 MiB")
            if max(full_psi(before), full_psi(after)) > 1.0:
                errors.append(f"{item['block']}/{item['kind']}: memory full PSI exceeded 1% at block boundary")
        except (OSError, ValueError, KeyError, TypeError) as error:
            errors.append(f"{item['block']}/{item['kind']}: host snapshot unreadable: {error}")
        for entry in item["files"]:
            path = raw / entry["path"]
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                errors.append(f"{path}: raw artifact changed or missing")
        source = raw / "results.json"
        if item["exitCode"] or not source.exists():
            errors.append(f"{item['block']}/{item['kind']}: missing or failed raw result")
            continue
        try:
            records = json.loads(source.read_text())
        except (OSError, ValueError) as error:
            errors.append(f"{source}: {error}")
            continue
        expected = {(mode, item["payload"]) for mode in item["modes"]}
        actual = [(r["params"]["mode"], r["params"]["payloadSize"]) for r in records]
        if set(actual) != expected or len(actual) != len(expected):
            errors.append(f"{item['block']}/{item['kind']}: condition set mismatch")
        log_path = run_dir / "orchestration" / item["block"] / item["kind"] / "gradle.log"
        output = log_path.read_text(errors="replace") if log_path.exists() else ""
        if output.count("analyticsDisabled=true") < len(records):
            errors.append(f"{item['block']}/{item['kind']}: analytics control missing")
        if output.count("allowSegmentTiering=true") < sum(m.startswith("CHRONICLE") for m, _ in actual):
            errors.append(f"{item['block']}/{item['kind']}: tiering policy missing")
        fingerprints = set(re.findall(r"traceSha256=([0-9a-f]{64})", output))
        if len(fingerprints) != 1:
            errors.append(f"{item['block']}/{item['kind']}: trace fingerprint missing or varied")
        if item["kind"] == "jfr":
            recordings = list(raw.rglob("*.jfr"))
            if len(recordings) != len(item["modes"]) * item["forks"]:
                errors.append(f"{item['block']}: expected one JFR recording per condition and fork")
        if item["kind"] == "diagnostics":
            sidecars = sorted(raw.glob("*.os.csv"))
            if len(sidecars) != len(item["modes"]) * item["forks"]:
                errors.append(f"{item['block']}: expected one OS sidecar per condition and fork")
            for sidecar in sidecars:
                with sidecar.open(newline="") as stream:
                    measured = [line for line in csv.DictReader(stream)
                                if line["phase"] == "MEASUREMENT"]
                observation = {"sidecar": sidecar.name, "measurementIterations": len(measured),
                               "majorFaults": sum(int(line["majorFaults"]) for line in measured),
                               "readBytes": sum(int(line["readBytes"]) for line in measured),
                               "writeBytes": sum(int(line["writeBytes"]) for line in measured)}
                diagnostic_observations.append(observation)
                if observation["majorFaults"] > 0:
                    errors.append(f"{item['block']}: diagnostic fork had major faults ({sidecar.name})")
        for record in records:
            metric = record["primaryMetric"]
            hist = metric.get("rawDataHistogram", [])
            samples = sum(int(pair[1]) for fork in hist for iteration in fork for pair in iteration)
            percentiles = metric.get("scorePercentiles", {}) if record["mode"] == "sample" else {}
            row = {"block": item["block"], "kind": item["kind"],
                   "mode": record["params"]["mode"], "payload": record["params"]["payloadSize"],
                   "threads": record["threads"], "forks": record["forks"],
                   "score": metric["score"], "unit": metric["scoreUnit"],
                   "samples": samples if record["mode"] == "sample" else "",
                   "p50Ns": percentiles.get("50.0", ""), "p95Ns": percentiles.get("95.0", ""),
                   "p99Ns": percentiles.get("99.0", ""), "p999Ns": percentiles.get("99.9", "")}
            rows.append(row)
            if item["kind"] == "latency":
                if record["mode"] != "sample" or metric["scoreUnit"] != "ns/op" or not samples:
                    errors.append(f"{item['block']}/{row['mode']}: bad SampleTime record")
                if any("compiler" in name or "gc." in name for name in record.get("secondaryMetrics", {})):
                    errors.append(f"{item['block']}/{row['mode']}: profiler contaminated primary")
            if item["kind"] == "throughput" and (record["mode"] != "thrpt" or metric["scoreUnit"] != "ops/s"):
                errors.append(f"{item['block']}/{row['mode']}: bad throughput record")
            if item["kind"] == "diagnostics":
                compiler_ms = record.get("secondaryMetrics", {}).get("compiler.time.profiled", {}).get("score")
                diagnostic_observations.append({"block": item["block"], "mode": row["mode"],
                                                "payload": row["payload"],
                                                "compilerTimeProfiledMs": compiler_ms})
                if compiler_ms is None or compiler_ms > item["measure"] * 10:
                    errors.append(f"{item['block']}/{row['mode']}: compiler time exceeds 1% of measured interval or is absent")
    for payload in PAYLOADS:
        for mode in MODES:
            points = [r for r in rows if r["kind"] == "latency" and r["payload"] == payload
                      and r["mode"] == mode]
            if len(points) != 2:
                errors.append(f"{mode}/{payload}: need two counterbalanced latency blocks")
            elif max(r["p99Ns"] for r in points) / min(r["p99Ns"] for r in points) > 1.25:
                errors.append(f"{mode}/{payload}: p99 block ratio exceeds 1.25")
    for item in manifest["invocations"]:
        if item["kind"] in ("latency", "throughput") and (
                item["warmup"] < 12 or item["measure"] < 8 or item["forks"] < 3):
            errors.append(f"{item['block']}/{item['kind']}: validation duration/forks below planned candidate minimum")
    fields = ["block", "kind", "mode", "payload", "threads", "forks", "score", "unit",
              "samples", "p50Ns", "p95Ns", "p99Ns", "p999Ns"]
    with (run_dir / "summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)
    save(run_dir / "quality.json", {"machineChecksPass": not errors,
         "researchStatus": "requires_manual_review" if not errors else "rejected",
         "errors": errors, "hostObservations": host_observations,
         "diagnosticObservations": diagnostic_observations,
         "screeningThresholds": {"swapRiseMiBPerBlock": 256,
                                 "memoryFullPsiAvg10PercentAtBoundary": 1.0,
                                 "compilerTimeFractionOfMeasurement": 0.01,
                                 "diagnosticMajorFaults": 0},
         "limits": ["Process counters include setup and the whole JVM.",
                    "JFR/diagnostic latency is separate from unprofiled primary latency.",
                    "A machine-check pass does not establish a quiet host or GC crossover."]})
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--warmup", type=int, default=12)
    parser.add_argument("--measurement", type=int, default=8)
    parser.add_argument("--forks", type=int, default=3)
    parser.add_argument("--profile-forks", type=int, default=1)
    parser.add_argument("--skip-profile", action="store_true")
    parser.add_argument("--audit-only", action="store_true",
                        help="recalculate summary and quality from an existing immutable raw run")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.run_id):
        parser.error("run id has invalid characters")
    run_dir = ROOT / "build" / "reports" / "tailcache08" / args.run_id
    if args.audit_only:
        if not (run_dir / "manifest.json").exists():
            parser.error(f"manifest does not exist: {run_dir}")
        return bool(audit(run_dir, json.loads((run_dir / "manifest.json").read_text())))
    if run_dir.exists():
        parser.error(f"run directory exists: {run_dir}")
    run_dir.mkdir(parents=True)
    manifest = {"schemaVersion": "tailcache08-v1", "runId": args.run_id,
                "startedUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "plan": "docs/TAILCACHE_08_10_PLAN.md", "invocations": [],
                "sourceSha256": source_digest()}
    with tarfile.open(run_dir / "source-snapshot.tar.gz", "w:gz") as archive:
        for path in source_files():
            archive.add(path, arcname=str(path.relative_to(ROOT)))
    save(run_dir / "environment-start.json", environment())
    for index, modes in enumerate([MODES, list(reversed(MODES))], 1):
        for payload in PAYLOADS:
            block = f"pass{index}-{payload.lower()}"
            for kind in ["latency", "throughput"]:
                manifest["invocations"].append(run_block(args.run_id, block, kind, modes, payload,
                    args.warmup, args.measurement, args.forks, run_dir))
                save(run_dir / "manifest.json", manifest)
    if not args.skip_profile:
        for payload in PAYLOADS:
            block = f"profile-{payload.lower()}"
            for kind in ["diagnostics", "jfr"]:
                manifest["invocations"].append(run_block(args.run_id, block, kind, MODES, payload,
                    args.warmup, args.measurement, args.profile_forks, run_dir))
                save(run_dir / "manifest.json", manifest)
    manifest["finishedUtc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    save(run_dir / "manifest.json", manifest)
    save(run_dir / "environment-end.json", environment())
    errors = audit(run_dir, manifest)
    print(f"raw={run_dir} machine-check-errors={len(errors)}", flush=True)
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
