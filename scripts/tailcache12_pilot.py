#!/usr/bin/env python3
"""Run and replay the eight-cell Task 12 pilot after qualification and calibration.

Pilot results never enter a confirmatory campaign. This driver deliberately cannot
launch one: observer/exposure/retry rules still need to be frozen from the pilot.
"""
import argparse
import csv
import json
import random
import re
import subprocess
import tarfile

import tailcache12 as evidence
import tailcache12_calibrate as calibration
import tailcache12_everyop_jit as everyop_jit
from tailcache12_study_analysis import (every_operation_fork_summary, hierarchical_ratio,
                                       jmh_fork_summary, variance_reasons)
from tailcache12_provenance import VERSION as SOURCE_VERSION, archive_measurement_source_hash, measurement_source_hash

TASKS = {"sample": "tailCache12Sample", "every-operation": "tailCache12EveryOperation",
         "throughput": "tailCache12Throughput", "allocation": "tailCache12Allocation",
         "sample-calibration": "tailCache12SampleCalibration", "compiler": "tailCache12Compiler"}
PRIMARY = ("sample", "every-operation")


def schedule(inputs, order_seed=24301):
    """Counterbalance paired backends, payload/pressure order and channel order."""
    if (len(inputs["liveBytes"]) != 4 or set(inputs["payloads"]) != {256, 4096}
            or inputs["warmups"] < 12 or inputs["measurements"] != 8):
        raise ValueError("Pilot requires a four-level calibration, both payloads and ≥12/8 timing")
    cells = [(p, live) for p in inputs["payloads"] for live in
             (min(inputs["liveBytes"]), max(inputs["liveBytes"]))]
    random.Random(order_seed).shuffle(cells)
    grid = []
    channels = list(TASKS)
    for block in (1, 2):
        for payload, live in (cells if block == 1 else list(reversed(cells))):
            for channel in (channels if block == 1 else list(reversed(channels))):
                forks = 3 if channel in PRIMARY else 1
                for fork in range(1, forks + 1):
                    backends = evidence.BACKENDS if (block + fork) % 2 == 0 else tuple(reversed(evidence.BACKENDS))
                    for backend in backends:
                        label = f"b{block}-{channel}-p{payload}-live{live}-f{fork}-{backend}"
                        props = dict(Backend=backend, Payload=payload, LiveBytes=live,
                                     Residents=inputs["residents"], HeapMiB=inputs["heapMiB"],
                                     ChurnBytesPerSecond=inputs["churnBytesPerSecond"], Seed=inputs["seed"],
                                     Warmups=inputs["warmups"], Measurements=inputs["measurements"],
                                     Channel=channel, Block=block, ForkOrdinal=fork)
                        if channel != "every-operation":
                            props.update(Backends=backend, Payloads=payload, Forks=1)
                        grid.append((label, props))
    return grid


def qualification_refs(functional, jit, calibrated, everyop):
    """Recompute gates and match workload/build/observer sources before the pilot."""
    manifests = []
    measurement_hash = measurement_source_hash(evidence.ROOT)
    for attempt, stage in ((functional, "validate"), (jit, "jit"), (calibrated, "calibrate"), (everyop, "everyop-jit")):
        manifest = json.loads((attempt / "manifest.json").read_text())
        if manifest["stage"] != stage:
            raise ValueError("Qualification attempt has the wrong stage")
        if archive_measurement_source_hash(attempt / "source.tar.gz") != measurement_hash:
            raise ValueError(f"Qualification measurement source differs from current checkout: {attempt.name}")
        if manifest.get("hostRuleVersion") != evidence.HOST_RULE_VERSION:
            raise ValueError("Qualification uses a different host rule")
        manifests.append(manifest)
    if evidence.replay(functional) or evidence.replay(jit):
        raise ValueError("Functional/pause and repeated JIT qualification must pass")
    jit_audit = json.loads((jit / "replayed-audit.json").read_text())
    if len(jit_audit.get("jit", [])) != 8:
        raise ValueError("Missing complete independent two-order JIT qualification")
    result = calibration.replay(calibrated)
    manifest = json.loads((calibrated / "manifest.json").read_text())
    warmups = {r["properties"]["Warmups"] for r in manifests[1]["invocations"]}
    if not result["calibrationReady"] or warmups != {manifest["inputs"]["warmups"]}:
        raise ValueError("Both-recorder calibration and JIT warmup duration must agree")
    everyop_result = everyop_jit.replay(everyop)
    conditions = [(p["properties"]["Backend"], p["properties"]["Payload"]) for p in manifests[3]["invocations"]]
    expected_conditions = {(backend,payload) for backend in evidence.BACKENDS for payload in (256,4096)}
    if (not everyop_result["qualityPass"] or len(conditions) != 8
            or set(conditions) != expected_conditions or any(conditions.count(c) != 2 for c in expected_conditions)
            or manifests[3]["inputs"]["warmups"] != manifest["inputs"]["warmups"]):
        raise ValueError("Complete repeated every-operation JIT qualification is required")
    for invocation in manifests[3]["invocations"]:
        props = invocation["properties"]
        if any(props[key] != manifest["inputs"][field] for key,field in
               (("Residents","residents"),("HeapMiB","heapMiB"),("ChurnBytesPerSecond","churnBytesPerSecond"))):
            raise ValueError("Every-operation qualification controls differ from calibration")
    refs = {}
    for name, attempt in (("functional", functional), ("jit", jit), ("calibration", calibrated), ("everyopJit",everyop)):
        refs[name] = {"attempt": attempt.name, "manifestSha256": calibration.sha(attempt / "manifest.json"),
                      "sourceArchiveSha256": calibration.sha(attempt / "source.tar.gz"),
                      "measurementSourceSha256": measurement_hash}
    return refs, manifest["inputs"], result


def analyze(attempt, manifest, invocation):
    raw = calibration.verify_invocation(attempt, invocation)
    props = invocation["properties"]
    channel = props["Channel"]
    trace = manifest["traceSha256"]
    bands = manifest["calibrationBands"]
    band_channel = "every-operation" if channel == "every-operation" else "sample-calibration"
    band = next(b["postGcMedianFraction"] for b in bands if b["channel"] == band_channel
                and b["backend"] == props["Backend"] and b["payloadBytes"] == props["Payload"]
                and b["applicationLiveBytes"] == props["LiveBytes"])
    if channel == "every-operation":
        result = every_operation_fork_summary(raw / channel, props, trace,
                                              manifest["runtimeIdentity"]["jdkVersion"], band)
    else:
        inputs = dict(props, ConsoleFile=str(attempt / invocation["label"] / "gradle.log"))
        result = jmh_fork_summary(raw, channel, inputs, trace, manifest["runtimeIdentity"],
                                  band if channel == "sample-calibration" else None)
    with (attempt / invocation["label"] / "host.csv").open(newline="") as stream:
        samples = [evidence.decode_host_row(row) for row in csv.DictReader(stream)]
    reasons, fraction = evidence.replay_host_gate(manifest, raw, samples)
    result["rejectionReasons"].extend(reasons + invocation.get("hostMonitorErrors", []))
    result.update(label=invocation["label"], inputs=props, hostPass=not reasons,
                  memoryFullStallFraction=fraction, accepted=not result["rejectionReasons"])
    return result


def replay(attempt):
    manifest = json.loads((attempt / "manifest.json").read_text())
    if calibration.sha(attempt / "source.tar.gz") != manifest["sourceArchiveSha256"]:
        raise ValueError("Changed pilot source archive")
    for ref in manifest["qualificationRefs"].values():
        dependency = attempt.parent / ref["attempt"]
        if (calibration.sha(dependency / "manifest.json") != ref["manifestSha256"]
                or calibration.sha(dependency / "source.tar.gz") != ref["sourceArchiveSha256"]
                or archive_measurement_source_hash(dependency / "source.tar.gz") != ref["measurementSourceSha256"]):
            raise ValueError("Changed qualification reference")
        dependency_manifest = json.loads((dependency / "manifest.json").read_text())
        for invocation in dependency_manifest["invocations"]:
            calibration.verify_invocation(dependency, invocation)
    rows = [analyze(attempt, manifest, item) for item in manifest["invocations"]]
    missing = [label for label in manifest["expectedBlocks"] if label not in {r["label"] for r in rows}]
    comparisons = []
    for channel in PRIMARY:
        for payload in manifest["inputs"]["payloads"]:
            for live in (min(manifest["inputs"]["liveBytes"]), max(manifest["inputs"]["liveBytes"])):
                selected = [r for r in rows if r["inputs"]["Channel"] == channel
                            and r["inputs"]["Payload"] == payload and r["inputs"]["LiveBytes"] == live]
                comparison = dict(channel=channel, payloadBytes=payload, applicationLiveBytes=live,
                                  complete=False, varianceRejectionReasons=[])
                if len(selected) == 12 and all(r["accepted"] for r in selected):
                    endpoints = {backend: [[next(r["servicePercentilesNs"] for r in selected
                                  if r["inputs"]["Backend"] == backend and r["inputs"]["Block"] == block
                                  and r["inputs"]["ForkOrdinal"] == fork) for fork in (1, 2, 3)]
                                  for block in (1, 2)] for backend in evidence.BACKENDS}
                    comparison["varianceRejectionReasons"] = variance_reasons(endpoints)
                    comparison["ratios"] = {p: hierarchical_ratio([
                        [(endpoints["CAFFEINE"][b][f][p], endpoints["CHRONICLE_IN_MEMORY"][b][f][p])
                         for f in range(3)] for b in range(2)]) for p in ("99", "99.9")}
                    comparison["complete"] = True
                comparisons.append(comparison)
    result = dict(schemaVersion="tailcache12-pilot-v1", reportable=False, campaignReady=False,
                  replaySourceSha256=evidence.source_hash(), observations=rows, comparisons=comparisons,
                  completedBlocks=len(rows), expectedBlocks=len(manifest["expectedBlocks"]), missingBlocks=missing,
                  dataCompleteAndQualityPass=not missing and len(rows) == len(manifest["expectedBlocks"])
                      and all(r["accepted"] for r in rows),
                  provisionalVariancePass=all(c["complete"] and not c["varianceRejectionReasons"] for c in comparisons),
                  requiresObserverExposureAndRetryRuleReview=True,
                  limits=["Pilot data cannot enter the confirmatory campaign.",
                          "Supporting diagnostic channels have one fresh fork per order; they are descriptive only.",
                          "Provisional p99/p99.9 variance limits are 1.25/1.5; pilot review must freeze final rules.",
                          "Unprofiled SampleTime pressure is supported by separate logged SampleTime calibration forks."])
    evidence.save(attempt / "pilot.json", result)
    print(f"pilot={attempt / 'pilot.json'} blocks={len(rows)}/{len(manifest['expectedBlocks'])} "
          f"quality={result['dataCompleteAndQualityPass']} campaignReady=False", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("pilot", "audit"))
    parser.add_argument("attempt_id")
    parser.add_argument("--functional")
    parser.add_argument("--jit")
    parser.add_argument("--calibration")
    parser.add_argument("--everyop-jit")
    parser.add_argument("--order-seed", type=int, default=24301)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.attempt_id):
        parser.error("Invalid attempt ID")
    attempt = evidence.REPORTS / args.attempt_id
    if args.stage == "audit":
        return 0 if replay(attempt)["dataCompleteAndQualityPass"] else 1
    if attempt.exists():
        if not args.resume:
            parser.error("Attempt exists; immutable attempts require --resume")
        manifest = json.loads((attempt / "manifest.json").read_text())
        if manifest["sourceSha256"] != evidence.source_hash():
            raise ValueError("Source changed; cannot resume this attempt")
        grid = [(r["label"], r["properties"]) for r in manifest["schedule"]]
        replay(attempt)
    else:
        if not all((args.functional, args.jit, args.calibration,args.everyop_jit)):
            parser.error("Pilot requires --functional, --jit, --everyop-jit and --calibration attempt IDs")
        refs, inputs, calibrated = qualification_refs(*(evidence.REPORTS / name for name in
            (args.functional, args.jit, args.calibration,args.everyop_jit)))
        grid = schedule(inputs, args.order_seed)
        traces = {row["traceSha256"] for row in calibrated["observations"] if "traceSha256" in row}
        if len(traces) != 1 or not calibrated["runtimeIdentity"]:
            raise ValueError("Missing paired trace or exact runtime identity")
        attempt.mkdir(parents=True)
        manifest = dict(schemaVersion="tailcache12-pilot-v1", stage="pilot", reportable=False,
                        hostRuleVersion=evidence.HOST_RULE_VERSION, sourceSha256=evidence.source_hash(),
                        measurementSourceVersion=SOURCE_VERSION, measurementSourceSha256=measurement_source_hash(evidence.ROOT),
                        gitHead=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=evidence.ROOT, text=True).strip(),
                        qualificationRefs=refs, inputs=inputs, orderSeed=args.order_seed, invocations=[],
                        runtimeIdentity=calibrated["runtimeIdentity"], traceSha256=next(iter(traces)),
                        calibrationBands=calibrated["calibrationBands"],
                        expectedBlocks=[label for label, _ in grid],
                        schedule=[dict(label=label, properties=props) for label, props in grid])
        with tarfile.open(attempt / "source.tar.gz", "w:gz") as archive:
            for path in evidence.sources():
                archive.add(path, arcname=str(path.relative_to(evidence.ROOT)))
        manifest["sourceArchiveSha256"] = calibration.sha(attempt / "source.tar.gz")
        evidence.save(attempt / "manifest.json", manifest)
        evidence.save(attempt / "environment.json", dict(initialHost=evidence.host_snapshot()))
    done = {row["label"] for row in manifest["invocations"]}
    for label, props in grid:
        if label in done:
            continue
        # Stop for any quality failure. Pilot review identifies a cause before a new attempt.
        if manifest["invocations"] and not analyze(attempt, manifest, manifest["invocations"][-1])["accepted"]:
            break
        evidence.invoke(attempt, manifest, label, TASKS[props["Channel"]], props)
    return 0 if replay(attempt)["dataCompleteAndQualityPass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
