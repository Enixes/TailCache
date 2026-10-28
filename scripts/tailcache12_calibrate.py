#!/usr/bin/env python3
"""Task 12C/12D calibration and replay. Exploratory runs cannot launch the campaign.

The calibration grid uses identical inputs in both backends. Quality gates describe
measured occupancy; they never add ballast to force Chronicle to match Caffeine.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import pathlib
import re
import statistics
import subprocess
import tarfile
import time

import tailcache12 as evidence
from tailcache12_analysis import VERSION, every_operation_summary
from tailcache12_study_analysis import every_operation_fork_summary, jmh_fork_summary
from tailcache12_calibration_retry import candidate_label, declare_policy, select as select_retry_slots
from tailcache12_quiet import replay_preflight, run_preflight
from tailcache12_provenance import archive_measurement_source_hash, measurement_source_hash

CHANNELS = ("every-operation", "sample-calibration")


def command_properties(props):
    result = dict(props)
    if props["Channel"] == "sample-calibration":
        result.update(Backends=props["Backend"], Payloads=props["Payload"], Forks=1)
    return result


def calibration_grid(inputs):
    grid = []
    for repeat in range(1, inputs["repeats"] + 1):
        backends = evidence.BACKENDS if repeat % 2 else tuple(reversed(evidence.BACKENDS))
        payloads = inputs["payloads"] if repeat % 2 else list(reversed(inputs["payloads"]))
        levels = inputs["liveBytes"] if repeat % 2 else list(reversed(inputs["liveBytes"]))
        for live in levels:
            for payload in payloads:
                for backend in backends:
                    for channel in (inputs["channels"] if repeat % 2 else list(reversed(inputs["channels"]))):
                        label = f"r{repeat}-{channel}-{backend}-p{payload}-live{live // 1024**2}"
                        grid.append((label, dict(Backend=backend, Payload=payload, Residents=inputs["residents"],
                            LiveBytes=live, ChurnBytesPerSecond=inputs["churnBytesPerSecond"],
                            HeapMiB=inputs["heapMiB"], Warmups=inputs["warmups"], Measurements=inputs["measurements"],
                            Seed=inputs["seed"], Channel=channel)))
    return grid


def verify_retry_declaration(attempt, manifest):
    policy = manifest.get("calibrationHostCpuRetryPolicy")
    if not policy:
        return None
    if manifest.get("schemaVersion") != "tailcache12-calibration-v2-hostcpu-retry":
        raise ValueError("Retry policy cannot be attached to a legacy attempt")
    path = attempt / "retry-policy.json"
    if sha(path) != manifest["retryPolicySha256"]:
        raise ValueError("Changed prospective retry declaration")
    declaration = json.loads(path.read_text())
    for name in ("calibrationHostCpuRetryPolicy", "logicalSlots", "sourceSha256", "measurementSourceSha256", "hostObservationDeclaration"):
        if declaration[name] != manifest[name]:
            raise ValueError("Retry declaration disagrees with manifest")
    canonical = [dict(label=label, properties=command_properties(props))
                 for label, props in calibration_grid(manifest["inputs"])]
    if manifest["logicalSlots"] != canonical or manifest["inputs"].get("calibrationHostCpuRetryPolicy") != policy:
        raise ValueError("Declared calibration schedule or retry inputs changed")
    host = manifest["hostObservationDeclaration"]
    if (host.get("monitorVersion") != policy["requiredNativeMonitorVersion"]
            or not pathlib.Path(host.get("historyFile", "")).is_absolute()
            or not host.get("historyFile", "").endswith(".jsonl")
            or any(not isinstance(host.get(key), str) or not host[key] or host[key] == "unspecified"
                   for key in ("powerScheme", "cpuCounter"))):
        raise ValueError("Invalid native observer declaration")
    select_retry_slots(manifest, [])  # Validate the bounded, calibration-only schema.
    return policy


def verify_retry_preflights(attempt, manifest, rows, selection):
    policy = manifest["calibrationHostCpuRetryPolicy"]
    table = manifest.get("retryPreflights", {})
    by_label = {r["label"]: r for r in rows}
    pending = selection["nextCandidate"]
    pending_label = pending["label"] if pending else None
    permitted = {candidate_label(s["label"], n) for s in manifest["logicalSlots"]
                 for n in range(2, policy["maxRetriesPerSlot"] + 2)}
    verified, errors = {}, []
    for label, record in table.items():
        if label not in permitted or (label not in by_label and label != pending_label):
            raise ValueError("Unexpected or out-of-order retry preflight")
        directory = attempt / "retry-preflights" / label
        if set(record["sha256"]) != {"quiet.json", "host.csv"}:
            raise ValueError("Incomplete retry preflight artifact list")
        for name, digest in record["sha256"].items():
            if sha(directory / name) != digest:
                raise ValueError("Changed retry preflight artifact")
        checked = replay_preflight(directory, manifest["sourceSha256"], policy["quietSeconds"],
                                   policy["quietTimeoutSeconds"], policy["requiredNativeMonitorVersion"])
        declared = manifest["hostObservationDeclaration"]
        if checked["powerSchemes"] != [declared["powerScheme"]] or checked["cpuCounters"] != [declared["cpuCounter"]]:
            raise ValueError("Retry preflight power/counter differs from declaration")
        verified[label] = checked
        if not checked["quietPass"]:
            errors.append(label + ": bounded retry quiet preflight rejected")
    for index, row in enumerate(rows):
        status = selection["attemptStatuses"][row["label"]]
        if status["ordinal"] == 1:
            continue
        check = verified.get(row["label"])
        if not check or not check["quietPass"]:
            raise ValueError("Retried JVM lacks a passing raw-replayed quiet preflight")
        if index == 0 or check["firstMonotonicNs"] < rows[index-1]["hostWindowEndNs"]:
            raise ValueError("Retry quiet preflight overlaps the preceding JVM block")
        gap = (row["hostWindowStartNs"] - check["lastMonotonicNs"]) / 1e9
        if not 0 <= gap <= policy["maxQuietToBlockSeconds"]:
            raise ValueError("Retry preflight overlaps or is too old for its JVM block")
    return verified, errors


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
    retry_policy = verify_retry_declaration(attempt, manifest)
    if retry_policy and archive_measurement_source_hash(attempt / "source.tar.gz") != manifest["measurementSourceSha256"]:
        raise ValueError("Calibration measurement-source identity changed or is incomplete")
    rows, fingerprints, runtime_identity = [], {}, None
    for invocation in manifest["invocations"]:
        raw = verify_invocation(attempt, invocation)
        props = invocation["properties"]
        channel = props.get("Channel", "every-operation")
        if channel == "every-operation":
            summary = (every_operation_fork_summary(raw / channel, props)
                       if manifest["stage"] == "calibrate" else
                       every_operation_summary(raw / channel, props["ChurnBytesPerSecond"]))
            configuration = (raw / channel / "worker/configuration.txt").read_text()
            config = dict(line.split("=", 1) for line in configuration.splitlines() if "=" in line)
            if config["backend"] != props["Backend"]:
                raise ValueError("Backend identity mismatch")
            for name, field in (("Residents", "residentEntries"), ("Payload", "payloadBytes"),
                                ("LiveBytes", "applicationLiveBytes"), ("Seed", "seed")):
                if not re.search(r"\b" + field + "=" + str(props[name]) + r"(?:,|\])", config["config"]):
                    raise ValueError(f"Workload input mismatch: {field}")
            if f"-Xms{props['HeapMiB']}m" not in config["jvmArgs"] or f"-Xmx{props['HeapMiB']}m" not in config["jvmArgs"]:
                raise ValueError("Fixed heap evidence missing")
            identity = (config["traceSha256"], config["valueGenerator"])
            summary["jdkVersion"] = config["jdkVersion"]
        elif channel == "sample-calibration":
            record = json.loads((raw / channel / "results.json").read_text())[0]
            current_runtime = {key: record[key] for key in ("jmhVersion", "jdkVersion", "vmName", "vmVersion")}
            if runtime_identity is None:
                runtime_identity = current_runtime
            text = (attempt / invocation["label"] / "gradle.log").read_text() + (raw / channel / "jmh.txt").read_text()
            traces = set(re.findall(r"traceSha256=([0-9a-f]{64})", text))
            if len(traces) != 1:
                raise ValueError("Missing or inconsistent JMH workload fingerprint")
            trace = next(iter(traces))
            summary = jmh_fork_summary(raw, channel,
                dict(props, ConsoleFile=str(attempt / invocation["label"] / "gradle.log")), trace, runtime_identity)
            summary.update(summary["gc"])
            identity = (trace, "xorshift-key-version-v1")
        else:
            raise ValueError("Unknown calibration channel")
        with (attempt / invocation["label"] / "host.csv").open(newline="") as stream:
            host = [evidence.decode_host_row(row) for row in csv.DictReader(stream)]
        if not host:
            raise ValueError("Missing calibration host samples")
        host_reasons, fraction = evidence.replay_host_gate(manifest, raw, host)
        host_reasons.extend(invocation.get("hostMonitorErrors", []))
        native_versions = sorted({s.get("windowsMonitorVersion", 0) for s in host})
        if retry_policy and native_versions != [retry_policy["requiredNativeMonitorVersion"]]:
            host_reasons.append("calibration retry policy requires native observer v5 throughout the block")
        if retry_policy:
            declared = manifest["hostObservationDeclaration"]
            if any(s.get("windowsHostRequired") != 1 or s.get("windowsPowerScheme") != declared["powerScheme"]
                   or s.get("windowsCpuCounter") != declared["cpuCounter"] for s in host):
                host_reasons.append("native observer power/counter differs from calibration declaration")
        trace_key = (props["Residents"], props["Seed"])
        if trace_key in fingerprints and fingerprints[trace_key] != identity:
            raise ValueError("Paired workload fingerprints differ")
        fingerprints[trace_key] = identity
        summary.update(label=invocation["label"], inputs=props, channel=channel,
                       hostPass=not host_reasons, hostRejectionReasons=host_reasons,
                       nativeHostVersions=native_versions, hostWindowStartNs=host[0]["monotonicNs"],
                       hostWindowEndNs=host[-1]["monotonicNs"],
                       memoryFullStallFraction=fraction)
        rows.append(summary)
    selection, retry_preflights, preflight_errors = None, {}, []
    selected_rows = rows
    if retry_policy:
        selection = select_retry_slots(manifest, rows)
        retry_preflights, preflight_errors = verify_retry_preflights(attempt, manifest, rows, selection)
        chosen = set(selection["selectedLabels"])
        selected_rows = [r for r in rows if r["label"] in chosen]
        for row in rows:
            row.update(selection["attemptStatuses"][row["label"]])
    bands, calibration_errors = [], []
    for channel in manifest["inputs"].get("channels", ["every-operation"]):
        for backend in evidence.BACKENDS:
            for payload in manifest["inputs"]["payloads"]:
                previous = None
                for live in manifest["inputs"]["liveBytes"]:
                    observations = [r for r in selected_rows if r["channel"] == channel and r["inputs"]["Backend"] == backend
                                    and r["inputs"]["Payload"] == payload and r["inputs"]["LiveBytes"] == live]
                    key = f"{channel}/{backend}/{payload}/{live}"
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
                    bands.append({"channel": channel, "backend": backend, "payloadBytes": payload, "applicationLiveBytes": live,
                                  "postGcMedianFraction": center, "toleranceFraction": 0.05,
                                  "replicaFractions": fractions})
    if manifest["stage"] == "calibrate":
        if set(manifest["inputs"].get("channels", [])) != set(CHANNELS):
            calibration_errors.append("missing independent calibration of both latency recorders")
        for channel in CHANNELS:
            anchors = sorted((b for b in bands if b["channel"] == channel
                              and b["backend"] == "CAFFEINE" and b["payloadBytes"] == 4096),
                             key=lambda b: b["applicationLiveBytes"])
            if len(anchors) == 4 and (anchors[0]["postGcMedianFraction"] > 0.4
                                     or not 0.8 <= anchors[-1]["postGcMedianFraction"] < 0.95):
                calibration_errors.append(channel + ": 4-KiB Caffeine anchor does not span low (≤40%) to severe sustainable (80–95%) used heap")
    row_errors = (selection["terminalRejectionReasons"] + preflight_errors if selection else
                  [r["label"] + ": " + reason for r in rows
                   for reason in r["rejectionReasons"] + r["hostRejectionReasons"]])
    if runtime_identity is not None and any(r["jdkVersion"] != runtime_identity["jdkVersion"] for r in rows):
        row_errors.append("latency recorders used different JDK versions")
    errors = row_errors + calibration_errors
    if manifest.get("terminalDriverFailure"):
        errors.append("terminal calibration driver failure: " + manifest["terminalDriverFailure"]["reason"])
    complete = selection["complete"] if selection else (len(rows) == len(expected) and {r["label"] for r in rows} == set(expected))
    if not complete:
        errors.append("calibration grid incomplete")
    result = {"schemaVersion": VERSION, "stage": manifest["stage"], "reportable": False,
              "calibrationReady": not errors and manifest["stage"] == "calibrate",
              "campaignReady": False, "observations": rows, "calibrationBands": bands,
              "runtimeIdentity": runtime_identity, "replaySourceSha256": evidence.source_hash(),
              "rejectionReasons": errors, "completedBlocks": len(selected_rows), "expectedBlocks": len(expected),
              "recordedJvmAttempts": len(rows),
              "missingBlocks": selection["missingSlots"] if selection else [label for label in expected if label not in {r["label"] for r in rows}],
              "limits": ["Exploratory calibration is not primary crossover evidence.",
                         "JIT, observer coherence and the pilot must pass before a campaign.",
                         "Post-GC used heap and old-region capacity are not an exact live-set census."]}
    if selection:
        result.update(hostCpuRetryState=selection, retryPreflightRejectionReasons=preflight_errors,
                      measurementSourceSha256=manifest["measurementSourceSha256"],
                      replayedRetryPreflights=retry_preflights,
                      rejectedCandidateAttempts=[dict(label=r["label"], reasons=r["rejectionReasons"] + r["hostRejectionReasons"])
                                                 for r in rows if r["label"] in selection["excludedLabels"]])
    evidence.save(attempt / "calibration.json", result)
    columns = ["label", "channel", "backend", "payloadBytes", "applicationLiveBytes", "postGcMedianFraction",
               "oldRegionsMedianHeapFraction", "pauseCount", "pauseOverlapMs", "pausesPerSecond",
               "serviceP99Ns", "serviceP999Ns", "hostPass", "acceptedForCalibration", "logicalSlot", "candidateOrdinal"]
    with (attempt / "calibration.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, columns)
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(zip(columns, [r["label"], r["channel"], r["inputs"]["Backend"], r["inputs"]["Payload"],
                r["inputs"]["LiveBytes"], r["postGcUsedHeapMedianFraction"], r["oldRegionsMedianHeapFraction"],
                r["pauseCount"], r["pauseOverlapMs"], r["pausesPerSecond"], r["servicePercentilesNs"]["99"],
                r["servicePercentilesNs"]["99.9"], r["hostPass"],
                r.get("selectedForCalibration", not r["rejectionReasons"] and r["hostPass"]),
                r.get("slotLabel", r["label"]), r.get("ordinal", 1)])))
    print(f"calibration={attempt / 'calibration.json'} ready={result['calibrationReady']} "
          f"blocks={len(selected_rows)}/{len(expected)} attempts={len(rows)}", flush=True)
    return result


def prepare(attempt, args, grid):
    retry_policy = declare_policy(getattr(args, "host_cpu_retries", 0),
                                  getattr(args, "host_cpu_retry_budget", 8))
    if retry_policy and args.stage != "calibrate":
        raise ValueError("Host-CPU retries apply only to exploratory calibration")
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
                "hostRuleVersion": evidence.HOST_RULE_VERSION,
                "analysisVersion": VERSION, "sourceSha256": evidence.source_hash(), "inputs": vars_inputs(args),
                "expectedBlocks": [label for label, _ in grid], "invocations": [],
                "gitHead": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=evidence.ROOT, text=True).strip(),
                "gitStatus": subprocess.check_output(["git", "status", "--short"], cwd=evidence.ROOT, text=True)}
    initial_host = evidence.host_snapshot()
    if retry_policy:
        history = os.environ.get("TAILCACHE_WINDOWS_HOST_FILE", "")
        if (os.environ.get("TAILCACHE_REQUIRE_WINDOWS_HOST") != "1" or not pathlib.Path(history).is_absolute()
                or not history.endswith(".jsonl") or initial_host.get("windowsMonitorVersion") != 5
                or initial_host.get("windowsHostRequired") != 1):
            raise ValueError("CPU-retry calibration requires the v5 append-only native observer")
        manifest.update(schemaVersion="tailcache12-calibration-v2-hostcpu-retry",
            calibrationHostCpuRetryPolicy=retry_policy,
            measurementSourceSha256=measurement_source_hash(evidence.ROOT),
            logicalSlots=[dict(label=label, properties=command_properties(props)) for label, props in grid],
            retryPreflights={}, hostObservationDeclaration=dict(historyFile=history, monitorVersion=5,
                powerScheme=initial_host["windowsPowerScheme"], cpuCounter=initial_host["windowsCpuCounter"]))
        declaration = {key: manifest[key] for key in
                       ("calibrationHostCpuRetryPolicy", "logicalSlots", "sourceSha256", "measurementSourceSha256", "hostObservationDeclaration")}
        declaration["declaredUtc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        evidence.save(attempt / "retry-policy.json", declaration)
        manifest["retryPolicySha256"] = sha(attempt / "retry-policy.json")
    with tarfile.open(attempt / "source.tar.gz", "w:gz") as archive:
        for path in evidence.sources():
            archive.add(path, arcname=str(path.relative_to(evidence.ROOT)))
    manifest["sourceArchiveSha256"] = sha(attempt / "source.tar.gz")
    evidence.save(attempt / "manifest.json", manifest)
    environment = {"initialHost": initial_host, "commands": {}}
    for label, command in (("cpu", ["lscpu"]), ("java", ["java", "-version"]), ("os", ["uname", "-a"])):
        result = subprocess.run(command, capture_output=True, text=True)
        environment["commands"][label] = {"exitCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    evidence.save(attempt / "environment.json", environment)
    return manifest


def vars_inputs(args):
    inputs = {"heapMiB": args.heap_mib, "residents": args.residents, "churnBytesPerSecond": args.churn_mib * 1024 ** 2,
            "liveBytes": [x * 1024 ** 2 for x in args.live_mib], "payloads": args.payloads, "seed": args.seed,
            "warmups": args.warmups, "measurements": args.measurements, "repeats": args.repeats,
            "channels": args.channels}
    policy = declare_policy(getattr(args, "host_cpu_retries", 0), getattr(args, "host_cpu_retry_budget", 8))
    if policy:
        inputs["calibrationHostCpuRetryPolicy"] = policy
    return inputs


def run_retry_grid(attempt, manifest):
    """Keep first passing logical slots; stop on anything except bounded CPU noise."""
    try:
        while True:
            result = replay(attempt)
            state = result["hostCpuRetryState"]
            candidate = state["nextCandidate"]
            if (not candidate or result["retryPreflightRejectionReasons"]
                    or manifest.get("terminalDriverFailure")):
                return result
            declared = manifest["hostObservationDeclaration"]
            current = evidence.host_snapshot()
            if (os.environ.get("TAILCACHE_REQUIRE_WINDOWS_HOST") != "1"
                    or os.environ.get("TAILCACHE_WINDOWS_HOST_FILE") != declared["historyFile"]
                    or current.get("windowsMonitorVersion") != declared["monitorVersion"]
                    or current.get("windowsPowerScheme") != declared["powerScheme"]
                    or current.get("windowsCpuCounter") != declared["cpuCounter"]):
                raise ValueError("Declared native observer environment changed")
            if candidate["requiresQuietPreflight"]:
                label = candidate["label"]
                directory = attempt / "retry-preflights" / label
                if label not in manifest["retryPreflights"]:
                    policy = manifest["calibrationHostCpuRetryPolicy"]
                    run_preflight(directory, policy["quietSeconds"], policy["quietTimeoutSeconds"])
                    manifest["retryPreflights"][label] = dict(sha256={name: sha(directory / name)
                                                                      for name in ("quiet.json", "host.csv")})
                    evidence.save(attempt / "manifest.json", manifest)
                result = replay(attempt)
                if result["retryPreflightRejectionReasons"]:
                    return result
                checked = result["replayedRetryPreflights"][label]
                gap = (time.monotonic_ns() - checked["lastMonotonicNs"]) / 1e9
                if not 0 <= gap <= manifest["calibrationHostCpuRetryPolicy"]["maxQuietToBlockSeconds"]:
                    raise ValueError("Retained retry preflight expired before launch")
            props = candidate["properties"]
            task = "tailCache12EveryOperation" if props["Channel"] == "every-operation" else "tailCache12SampleCalibration"
            evidence.invoke(attempt, manifest, candidate["label"], task, props)
    except Exception as error:
        manifest["terminalDriverFailure"] = dict(reason=f"{type(error).__name__}: {error}",
            utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        evidence.save(attempt / "manifest.json", manifest)
        raise


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
    parser.add_argument("--channels", choices=CHANNELS, nargs="+")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--host-cpu-retries", type=int, choices=(0, 1, 2), default=0,
                        help="Prospective calibration-only extra JVMs per host-CPU-rejected logical slot")
    parser.add_argument("--host-cpu-retry-budget", type=int, choices=range(1, 9), default=8)
    args = parser.parse_args()
    if args.channels is None:
        args.channels = list(CHANNELS) if args.stage == "calibrate" else ["every-operation"]
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.attempt_id):
        parser.error("Invalid attempt ID")
    attempt = evidence.REPORTS / args.attempt_id
    if args.host_cpu_retries and args.stage != "calibrate":
        parser.error("Host-CPU retries are available only for exploratory calibration")
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
                                      or args.warmups < 12 or args.measurements < 8 or args.repeats < 2
                                      or set(args.channels) != set(CHANNELS)):
        parser.error("Full calibration requires four levels, both payloads/channels, ≥12/8 iterations and ≥2 repeats")
    if len(set(args.channels)) != len(args.channels):
        parser.error("Duplicate channels")
    grid = calibration_grid(vars_inputs(args))
    manifest = prepare(attempt, args, grid)
    if manifest.get("calibrationHostCpuRetryPolicy"):
        return 0 if run_retry_grid(attempt, manifest)["calibrationReady"] else 1
    completed = {x["label"] for x in manifest["invocations"]}
    for label, props in grid:
        if label in completed:
            continue
        # A failed host gate suspends a calibration grid; a small functional probe explicitly
        # preserves both backend diagnostics and never receives calibration-ready status.
        if args.stage == "calibrate" and manifest["invocations"] and not manifest["invocations"][-1]["hostQualityPass"]:
            break
        command_props = command_properties(props)
        task = "tailCache12EveryOperation" if props["Channel"] == "every-operation" else "tailCache12SampleCalibration"
        evidence.invoke(attempt, manifest, label, task, command_props)
        if args.stage == "calibrate":
            latest = replay(attempt)["observations"][-1]
            if latest["rejectionReasons"] or latest["hostRejectionReasons"]:
                print("Quality gate failed; remaining calibration blocks suspended.", flush=True)
                break
    result = replay(attempt)
    if args.stage == "probe":
        return 0 if len(result["observations"]) == len(grid) else 1
    return 0 if result["calibrationReady"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
