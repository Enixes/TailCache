#!/usr/bin/env python3
"""Task 12A/12B evidence driver. This does not launch a crossover campaign."""
import argparse
import csv
import hashlib
import json
import pathlib
import re
import subprocess
import tarfile
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORTS = ROOT / "build/reports/tailcache12"
BACKENDS = ("CAFFEINE", "CHRONICLE_IN_MEMORY")


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sources():
    for name in ("build.gradle.kts", "settings.gradle.kts", "gradle.properties", "gradlew", "gradle/wrapper", "src", "scripts", "docs"):
        path = ROOT / name
        files = [path] if path.is_file() else sorted(path.rglob("*"))
        for file in files:
            if file.is_file() and "__pycache__" not in file.parts:
                yield file


def source_hash():
    digest = hashlib.sha256()
    for path in sources():
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def raw_directory(attempt, invocation):
    """Resolve the manifest's sibling run after copying an evidence bundle to another host."""
    sibling = attempt.parent / (attempt.name + "-" + invocation["label"])
    return sibling if sibling.is_dir() else pathlib.Path(invocation["rawDirectory"])


def host_snapshot():
    mem = pathlib.Path("/proc/meminfo").read_text()
    vm = pathlib.Path("/proc/vmstat").read_text()
    def field(text, label):
        return int(re.search(r"^" + label + r":?\s+(\d+)", text, re.M).group(1))
    row = {"monotonicNs": time.monotonic_ns(), "memAvailableKiB": field(mem, "MemAvailable"),
           "swapUsedKiB": field(mem, "SwapTotal") - field(mem, "SwapFree"),
           "swapInPages": field(vm, "pswpin"), "swapOutPages": field(vm, "pswpout")}
    for label in ("zswpin", "zswpout", "oom_kill"):
        match = re.search(r"^" + label + r"\s+(\d+)", vm, re.M)
        row[label] = int(match[1]) if match else -1
    try:
        row["governor"] = pathlib.Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor").read_text().strip()
    except OSError:
        row["governor"] = "unavailable"
    supplies = []
    for path in sorted(pathlib.Path("/sys/class/power_supply").glob("*/online")):
        supplies.append(path.parent.name + "=" + path.read_text().strip())
    row["externalPower"] = ";".join(supplies) or "unavailable"
    for resource in ("memory", "io"):
        pressure = pathlib.Path(f"/proc/pressure/{resource}").read_text()
        row[resource + "FullTotalUs"] = int(re.search(r"^full .* total=(\d+)", pressure, re.M).group(1))
        row[resource + "FullAvg10"] = float(re.search(r"^full avg10=([\d.]+)", pressure, re.M).group(1))
    return row


def host_gate(snapshots):
    if len(snapshots) < 2:
        return ["missing host interval samples"], None
    before, after = snapshots[0], snapshots[-1]
    elapsed_us = (after["monotonicNs"] - before["monotonicNs"]) / 1000
    reasons = []
    if elapsed_us <= 0:
        return ["nonpositive host monitoring interval"], None
    if max(before["memoryFullAvg10"], after["memoryFullAvg10"]) != 0:
        reasons.append("nonzero boundary memory-full PSI")
    fraction = (after["memoryFullTotalUs"] - before["memoryFullTotalUs"]) / elapsed_us
    if fraction > 0.001:
        reasons.append("interval memory-full PSI exceeds 0.1%")
    if after["swapInPages"] != before["swapInPages"] or after["swapOutPages"] != before["swapOutPages"]:
        reasons.append("swap-in/out counters increased")
    for name in ("zswpin", "zswpout", "oom_kill"):
        if name in before and name in after and before[name] != after[name]:
            reasons.append(f"{name} counter changed")
    for name in ("governor", "externalPower"):
        values = {s.get(name, "unavailable") for s in snapshots}
        if len(values) != 1:
            reasons.append(f"{name} changed during block")
    if any("=0" in s.get("externalPower", "") for s in snapshots):
        reasons.append("external power is disconnected")
    return reasons, fraction


def invoke(attempt, manifest, label, task, properties):
    run_id = attempt.name + "-" + label
    control = attempt / label
    control.mkdir()
    command = [str(ROOT / "gradlew"), "--offline", task,
               f"-Ptailcache12RunId={run_id}"]
    command += [f"-Ptailcache12{key}={value}" for key, value in properties.items()]
    snapshots = [host_snapshot()]
    monitor_errors = []
    finished = threading.Event()
    def monitor():
        try:
            while not finished.wait(1):
                snapshots.append(host_snapshot())
        except Exception as error:
            monitor_errors.append(str(error))
    sampler = threading.Thread(target=monitor, daemon=True)
    sampler.start()
    started_source = source_hash()
    try:
        with (control / "gradle.log").open("w") as stream:
            code = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT).returncode
    finally:
        finished.set()
        sampler.join()
        snapshots.append(host_snapshot())
    with (control / "host.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(snapshots[0]))
        writer.writeheader()
        writer.writerows(snapshots)
    host_reasons, fraction = host_gate(snapshots)
    if monitor_errors:
        host_reasons.append("host monitor failed: " + "; ".join(monitor_errors))
    raw = REPORTS / run_id
    artifact_hashes = {str(p.relative_to(raw)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(raw.rglob("*")) if p.is_file()} if raw.exists() else {}
    record = {"label": label, "command": command, "exitCode": code, "rawDirectory": str(raw),
              "rawSha256": artifact_hashes, "sourceUnchanged": started_source == source_hash() == manifest["sourceSha256"],
              "properties": properties,
              "controlSha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in control.iterdir() if p.is_file()},
              "hostQualityPass": not host_reasons, "hostRejectionReasons": host_reasons,
              "hostMonitorErrors": monitor_errors,
              "memoryFullStallFraction": fraction}
    manifest["invocations"].append(record)
    save(attempt / "manifest.json", manifest)
    print(f"{label}: exit={code} host={'pass' if not host_reasons else 'reject'}", flush=True)
    if code or not record["sourceUnchanged"]:
        raise RuntimeError(f"Task failed or source changed: {label}; raw evidence retained")
    return raw


def retention_audit(paths):
    rows = []
    for backend, residents, directory in paths:
        populated = next(directory.glob("retention-*/populated.txt"))
        text = populated.read_text()
        match = re.search(r"^\s*\d+:\s+(\d+)\s+(\d+)\s+\[B(?:\s|$)", text, re.M)
        if not match:
            raise ValueError(f"byte-array histogram missing: {populated}")
        rows.append({"backend": backend, "residents": residents, "byteArrayCount": int(match[1]),
                     "byteArrayBytes": int(match[2])})
    slopes = {}
    for backend in BACKENDS:
        points = sorted((r for r in rows if r["backend"] == backend), key=lambda r: r["residents"])
        slopes[backend] = (points[1]["byteArrayBytes"] - points[0]["byteArrayBytes"]) / (points[1]["residents"] - points[0]["residents"])
    return {"rows": rows, "byteArrayBytesPerAdditionalEntry": slopes,
            "pass": slopes["CAFFEINE"] >= 0.9 * 4096 and abs(slopes["CHRONICLE_IN_MEMORY"]) < 0.1 * 4096,
            "limit": "Differential class histogram at 512/8192 residents; not a complete heap dominator census."}


def pause_audit(directory, validation):
    worker = directory / "every-operation/worker"
    with (worker / "iterations.csv").open(newline="") as stream:
        measurements = [x for x in csv.DictReader(stream) if x["phase"] == "MEASUREMENT"]
    if not measurements:
        raise ValueError("No measurement rows")
    for measured in measurements:
        for channel in ("service", "completion-gap"):
            with (worker / f"iteration-{measured['iteration']}-{channel}-bins.csv").open(newline="") as stream:
                count = sum(int(x["count"]) for x in csv.DictReader(stream))
            if count != int(measured["operations"]):
                raise ValueError(f"{channel} histogram count mismatch in iteration {measured['iteration']}")
    row = measurements[0]
    operations = int(row["operations"])
    observation = {"validation": validation, "operations": operations,
                   "serviceP50Ns": int(row["serviceP50Ns"]), "serviceP99Ns": int(row["serviceP99Ns"]),
                   "serviceMaxNs": int(row["serviceMaxNs"]), "completionGapMaxNs": int(row["completionGapMaxNs"])}
    if validation == "none":
        return {**observation, "pass": True}
    if validation == "long-operation":
        observation["pass"] = int(row["serviceMaxNs"]) >= 40_000_000 and int(row["serviceAbove10ms"]) >= 1
        return observation
    text = "\n".join(p.read_text() for p in directory.glob("every-operation/gc-*.log"))
    pauses = re.findall(r"\[(\d+)ms\].*GC\((\d+)\) Pause Full \(System.gc\(\)\).* ([\d.]+)ms", text)
    if len(pauses) != 1:
        return {**observation, "pass": False, "reason": "Expected exactly one logged System.gc pause"}
    uptime_end, gc_id, duration_ms = pauses[0]
    anchor_before = int(row.get("uptimeAnchorBeforeNs", row["startNs"]))
    anchor_after = int(row.get("uptimeAnchorAfterNs", row["startNs"]))
    alignment_error = 1_000_000 + anchor_after - anchor_before
    pause_end = (anchor_before + anchor_after) // 2 + (int(uptime_end) - int(row["uptimeStartMs"])) * 1_000_000
    pause_start = pause_end - float(duration_ms) * 1_000_000
    with (worker / "iteration-1-stall-events.csv").open(newline="") as stream:
        events = list(csv.DictReader(stream))
    overlapping = [x for x in events if int(x["previousCompletionNs"]) <= pause_end + 2_000_000
                   and int(x["endNs"]) >= pause_start - 2_000_000]
    observed_gap = max((int(x["completionGapNs"]) for x in overlapping), default=0)
    observation.update({"gcId": gc_id, "gcPauseMs": float(duration_ms), "overlappingEventCount": len(overlapping),
                        "overlappingGapNs": observed_gap, "clockAlignmentUncertaintyNs": alignment_error,
                        "pass": bool(overlapping) and observed_gap >= float(duration_ms) * 750_000
                        and alignment_error <= 2_000_000
                        and int(row["injectionStartNs"]) > int(row["startNs"])
                        and int(row["injectionEndNs"]) < int(row["endNs"])})
    return observation


def replay(attempt):
    manifest = json.loads((attempt / "manifest.json").read_text())
    paths = {}
    for invocation in manifest["invocations"]:
        raw = raw_directory(attempt, invocation)
        for name, digest in invocation["rawSha256"].items():
            if hashlib.sha256((raw / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Changed raw artifact: {raw / name}")
        for name, digest in invocation.get("controlSha256", {}).items():
            if hashlib.sha256((attempt / invocation["label"] / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Changed control artifact: {name}")
        if invocation["exitCode"] or not invocation["sourceUnchanged"]:
            raise ValueError("Failed invocation or changed source")
        paths[invocation["label"]] = raw
    if "sourceArchiveSha256" in manifest and hashlib.sha256((attempt / "source.tar.gz").read_bytes()).hexdigest() != manifest["sourceArchiveSha256"]:
        raise ValueError("Changed source snapshot")
    audit = {"reportable": False, "reconstructedFromRaw": True}
    if manifest["stage"] == "validate":
        audit["retention"] = retention_audit([(b, n, paths[f"retention-{b}-{n}"])
                                              for b in BACKENDS for n in (512, 8192)])
        audit["pauseValidation"] = [dict(pause_audit(paths[f"{v}-{b}"], v), backend=b)
                                    for b in BACKENDS for v in ("long-operation", "gc")]
        audit["timerFloor"] = pause_audit(paths["timer-floor"], "none")
        audit["observerQualified"] = False
        audit["functionalPass"] = audit["retention"]["pass"] and all(x["pass"] for x in audit["pauseValidation"])
    elif manifest["stage"] == "pause":
        audit["pauseValidation"] = [dict(pause_audit(paths[f"gc-{b}"], "gc"), backend=b) for b in BACKENDS]
        audit["functionalPass"] = all(x["pass"] for x in audit["pauseValidation"])
    else:
        observations = []
        for invocation in manifest["invocations"]:
            record = json.loads((raw_directory(attempt, invocation) / "compiler/results.json").read_text())[0]
            metric = record["secondaryMetrics"]["compiler.time.profiled"]
            values = metric.get("rawData", [[]])[0]
            with (attempt / invocation["label"] / "host.csv").open(newline="") as stream:
                snapshots = [{k: (v if k in ("governor", "externalPower") else float(v)) for k, v in r.items()}
                             for r in csv.DictReader(stream)]
            reasons, _ = host_gate(snapshots)
            reasons.extend(invocation.get("hostMonitorErrors", []))
            observations.append({"label": invocation["label"], "compilerTotalMs": metric["score"],
                                 "compilerPerIterationMs": values,
                                 "jitPass": metric["score"] <= 80 and len(values) == 8 and max(values) <= 10,
                                 "hostPass": not reasons})
        audit["jit"] = observations
        audit["functionalPass"] = len(observations) == 8 and all(x["jitPass"] and x["hostPass"] for x in observations)
    save(attempt / "replayed-audit.json", audit)
    print(f"replay={attempt / 'replayed-audit.json'} pass={audit['functionalPass']}")
    return 0 if audit["functionalPass"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["validate", "pause", "jit", "audit"])
    parser.add_argument("attempt_id")
    parser.add_argument("--warmups", type=int, default=12)
    parser.add_argument("--residents", type=int, default=8192)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.attempt_id):
        parser.error("Invalid attempt id")
    attempt = REPORTS / args.attempt_id
    if args.stage == "audit":
        return replay(attempt)
    if attempt.exists():
        parser.error(f"Attempt exists: {attempt}")
    attempt.mkdir(parents=True)
    manifest = {"schemaVersion": "tailcache12-development-v1", "stage": args.stage,
                "reportable": False, "sourceSha256": source_hash(), "invocations": [],
                "gitHead": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                          capture_output=True, text=True, check=True).stdout.strip(),
                "gitStatus": subprocess.run(["git", "status", "--short"], cwd=ROOT,
                                            capture_output=True, text=True, check=True).stdout}
    with tarfile.open(attempt / "source.tar.gz", "w:gz") as archive:
        for path in sources():
            archive.add(path, arcname=str(path.relative_to(ROOT)))
    manifest["sourceArchiveSha256"] = hashlib.sha256((attempt / "source.tar.gz").read_bytes()).hexdigest()
    environment = {}
    for label, command in (("uname", ["uname", "-a"]), ("cpu", ["lscpu"]),
                           ("java", ["java", "-version"]),
                           ("mount", ["findmnt", "-J", "-T", str(ROOT)])):
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        environment[label] = {"exitCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    for path in ("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "/sys/firmware/acpi/platform_profile"):
        try:
            environment[path] = pathlib.Path(path).read_text()
        except OSError as error:
            environment[path] = {"unavailable": str(error)}
    save(attempt / "environment.json", environment)
    audits = {"reportable": False}
    save(attempt / "manifest.json", manifest)
    if args.stage == "validate":
        invoke(attempt, manifest, "smoke", "tailCache12Smoke",
               {"Residents": 512, "LiveBytes": 8388608, "ChurnBytesPerSecond": 8388608})
        retention = []
        for backend in BACKENDS:
            for residents in (512, 8192):
                raw = invoke(attempt, manifest, f"retention-{backend}-{residents}", "tailCache12Retention",
                             {"Backend": backend, "Residents": residents, "Payload": 4096})
                retention.append((backend, residents, raw))
        audits["retention"] = retention_audit(retention)
        audits["pauseValidation"] = []
        for backend in BACKENDS:
            for validation in ("long-operation", "gc"):
                raw = invoke(attempt, manifest, f"{validation}-{backend}", "tailCache12EveryOperation",
                             {"Backend": backend, "Residents": 512, "Payload": 256,
                              "LiveBytes": 67108864 if validation == "gc" else 0,
                              "ChurnBytesPerSecond": 0, "Warmups": 3, "Measurements": 1,
                              "Validation": validation})
                audits["pauseValidation"].append(dict(pause_audit(raw, validation), backend=backend))
        sample = invoke(attempt, manifest, "observer-sample", "tailCache12Sample",
                        {"Residents": 512, "Payloads": 256, "ChurnBytesPerSecond": 0,
                         "Warmups": 3, "Measurements": 1, "Forks": 1})
        sample_records = json.loads((sample / "sample/results.json").read_text())
        audits["observerCharacterization"] = []
        for backend in BACKENDS:
            raw = invoke(attempt, manifest, "observer-every-" + backend, "tailCache12EveryOperation",
                         {"Backend": backend, "Residents": 512, "Payload": 256,
                          "ChurnBytesPerSecond": 0, "Warmups": 3, "Measurements": 1})
            observed = pause_audit(raw, "none")
            sampled = next(r for r in sample_records if r["params"]["backend"] == backend)
            audits["observerCharacterization"].append({"backend": backend, "everyOperation": observed,
                "sampleP50Ns": sampled["primaryMetric"]["scorePercentiles"]["50.0"],
                "sampleP99Ns": sampled["primaryMetric"]["scorePercentiles"]["99.0"],
                "qualified": False, "reason": "Short characterization, no frozen coherence rule or independent repeats"})
        invoke(attempt, manifest, "supply-floor", "tailCache12SupplyFloor",
               {"Residents": 512, "Backends": "CAFFEINE", "ChurnBytesPerSecond": 0,
                "Warmups": 3, "Measurements": 1, "Forks": 1})
        floor = invoke(attempt, manifest, "timer-floor", "tailCache12EveryOperation",
                       {"Residents": 512, "ChurnBytesPerSecond": 0, "Warmups": 3, "Measurements": 1,
                        "TimerFloor": "true"})
        audits["timerFloorDirectory"] = str(floor)
        audits["timerFloor"] = pause_audit(floor, "none")
        audits["functionalPass"] = audits["retention"]["pass"] and all(x["pass"] for x in audits["pauseValidation"])
    elif args.stage == "pause":
        audits["pauseValidation"] = []
        for backend in BACKENDS:
            raw = invoke(attempt, manifest, "gc-" + backend, "tailCache12EveryOperation",
                         {"Backend": backend, "Residents": 512, "Payload": 256, "LiveBytes": 67108864,
                          "ChurnBytesPerSecond": 0, "Warmups": 3, "Measurements": 2, "Validation": "gc"})
            audits["pauseValidation"].append(dict(pause_audit(raw, "gc"), backend=backend))
        audits["functionalPass"] = all(x["pass"] for x in audits["pauseValidation"])
    else:
        observations = []
        suspended = False
        for repeat in (1, 2):
            for backend in (BACKENDS if repeat == 1 else tuple(reversed(BACKENDS))):
                for payload in (256, 4096):
                    if suspended:
                        continue
                    raw = invoke(attempt, manifest, f"jit-{repeat}-{backend}-{payload}", "tailCache12Compiler",
                                 {"Backends": backend, "Payloads": payload, "Residents": args.residents,
                                  "LiveBytes": 8388608, "ChurnBytesPerSecond": 16777216,
                                  "Warmups": args.warmups, "Measurements": 8, "Forks": 1})
                    record = json.loads((raw / "compiler/results.json").read_text())[0]
                    metric = record["secondaryMetrics"]["compiler.time.profiled"]
                    values = metric.get("rawData", [[]])[0]
                    total = metric["score"]
                    passed = total <= 80 and len(values) == 8 and max(values) <= 10
                    worker_values = [int(x) for x in re.findall(r"phase=MEASUREMENT .*workerEnvelopeCompilerMs=(\d+)",
                                                               (attempt / f"jit-{repeat}-{backend}-{payload}" / "gradle.log").read_text())]
                    sidecars = list((raw / "compiler").glob("iterations-*.csv"))
                    if len(sidecars) != 1:
                        raise ValueError("Expected one compiler-worker sidecar")
                    with sidecars[0].open(newline="") as stream:
                        worker_values = [int(r["workerEnvelopeCompilerMs"]) for r in csv.DictReader(stream)
                                         if r["phase"] == "MEASUREMENT"]
                    if len(worker_values) != 8:
                        raise ValueError("Incomplete compiler-worker measurement rows")
                    observations.append({"repeat": repeat, "backend": backend, "payload": payload,
                                         "compilerTotalMs": total, "compilerPerIterationMs": values,
                                         "workerEnvelopeCompilerMs": worker_values,
                                         "jitPass": passed, "hostPass": manifest["invocations"][-1]["hostQualityPass"]})
                    if not observations[-1]["hostPass"]:
                        suspended = True
                        print("Host gate failed; remaining compiler blocks suspended.", flush=True)
        audits["jit"] = observations
        audits["jitRule"] = {"aggregateMsAtEightSeconds": 80, "perIterationMs": 10,
                             "repeats": 2, "warmups": args.warmups}
        audits["missingCompilerBlocks"] = 8 - len(observations)
        audits["functionalPass"] = len(observations) == 8 and all(x["jitPass"] and x["hostPass"] for x in observations)
    save(attempt / "audit.json", audits)
    print(f"audit={attempt / 'audit.json'} functionalPass={audits['functionalPass']}", flush=True)
    return 0 if audits["functionalPass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
