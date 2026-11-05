#!/usr/bin/env python3
"""Independent floor evidence, followed by coherence review using the pilot's replicas."""
import argparse
import csv
import json
import math
import re
import statistics
from types import SimpleNamespace

import tailcache12 as evidence
import tailcache12_calibrate as calibration
import tailcache12_native_retry as native_retry
from tailcache12_analysis import compiler_rejection_reasons, histogram, quantile
from tailcache12_provenance import archive_measurement_source_hash, measurement_source_hash
from tailcache12_study_analysis import between_operation_fraction, jmh_fork_summary

RULES = dict(version="tailcache12-observer-v1", timerMedianToEveryopMedianCeiling=1/3,
             supplyMedianToSampleMedianCeiling=1/2, nativeReadMedianCeilingMs=10,
             floorReplicas=2, primaryPilotForksPerConditionChannel=6,
             coherence="No opposite backend directions when both channel confidence intervals exclude one",
             betweenCallTime="Descriptive only; includes genuine pauses, no subtraction or pressure gate")


def floor_grid(warmups,conditioning=0):
    grid = []
    for order in (1, 2):
        for backend in (evidence.BACKENDS if order == 1 else tuple(reversed(evidence.BACKENDS))):
            for payload in ((256, 4096) if order == 1 else (4096, 256)):
                grid.append((f"b{order}-floor-{backend}-p{payload}", dict(Backend=backend, Payload=payload,
                    Backends=backend, Payloads=payload, Residents=32768, HeapMiB=512, LiveBytes=0,
                    ChurnBytesPerSecond=32*1024**2, Seed=24301, Warmups=warmups, Measurements=8,
                    Forks=1, Channel="floor", Block=order)))
        grid.append((f"b{order}-timer", dict(Backend="CAFFEINE", Payload=256, Residents=512,
                    HeapMiB=512, LiveBytes=0, ChurnBytesPerSecond=0, Seed=24301,
                    Warmups=warmups, Measurements=8, TimerFloor="true", Channel="timer", Block=order)))
    return [(label,dict(props,Conditioning=conditioning)) for label,props in grid] if conditioning else grid


def replay_floors(attempt):
    manifest = json.loads((attempt / "manifest.json").read_text())
    if (manifest["stage"] != "observer-floor" or manifest["observerRules"] != RULES
            or calibration.sha(attempt / "source.tar.gz") != manifest["sourceArchiveSha256"]):
        raise ValueError("Changed observer protocol or source archive")
    expected = floor_grid(manifest["inputs"]["warmups"],manifest["inputs"].get("conditioning",0))
    policy = native_retry.verify_declaration(attempt, manifest, expected)
    if manifest["expectedBlocks"] != [label for label, _ in expected]:
        raise ValueError("Changed floor schedule")
    rows, runtime, trace = [], None, None
    for index, invocation in enumerate(manifest["invocations"]):
        if not policy and (index >= len(expected) or invocation["label"] != expected[index][0] or invocation["properties"] != expected[index][1]):
            raise ValueError("Changed observer inputs or block order")
        raw = calibration.verify_invocation(attempt, invocation)
        props = invocation["properties"]
        if props["Channel"] == "floor":
            record = json.loads((raw / "floor/results.json").read_text())[0]
            this_runtime = {key: record[key] for key in ("jmhVersion", "jdkVersion", "vmName", "vmVersion")}
            if runtime is None:
                runtime = this_runtime
            text = (attempt / invocation["label"] / "gradle.log").read_text() + (raw / "floor/jmh.txt").read_text()
            fingerprints = set(re.findall(r"traceSha256=([0-9a-f]{64})", text))
            if len(fingerprints) != 1:
                raise ValueError("Missing or inconsistent floor trace")
            if trace is None:
                trace = next(iter(fingerprints))
            result = jmh_fork_summary(raw, "floor", dict(props,
                ConsoleFile=str(attempt / invocation["label"] / "gradle.log")), trace, runtime)
        else:
            evidence.pause_audit(raw, "none")
            worker = raw / "every-operation/worker"
            configuration = (worker / "configuration.txt").read_text()
            config = dict(line.split("=", 1) for line in configuration.splitlines() if "=" in line)
            if (config.get("timerFloor") != "true" or config.get("validation") != "none"
                    or config.get("compilerXml") != "false" or config.get("compilerCounters") != "true"
                    or runtime is None or any(config.get(k) != runtime[k] for k in
                                             ("jdkVersion", "vmName", "vmVersion"))):
                raise ValueError("Observer timer run has wrong controls")
            for flag in ("-Xms512m", "-Xmx512m", "-XX:+UseG1GC"):
                if flag not in config["jvmArgs"]:
                    raise ValueError("Timer floor lacks fixed-heap/G1 controls")
            for option, value in (("--warmup", props["Warmups"]), ("--measure", 8), ("--iteration-ms",1000)):
                if not re.search(re.escape(option) + "=" + str(value) + r"(?:,|\})", config["options"]):
                    raise ValueError("Timer floor timing controls differ")
            with (worker / "iterations.csv").open(newline="") as stream:
                iterations = list(csv.DictReader(stream))
            measured = [r for r in iterations if r["phase"] == "MEASUREMENT"]
            conditioning=props.get("Conditioning",0)
            conditioned=[r for r in iterations if r["phase"]=="CONDITIONING"]
            if len(iterations) != props["Warmups"] + conditioning + 8 or len(measured) != 8 or len(conditioned)!=conditioning:
                raise ValueError("Incomplete timer preparation/measurement")
            if conditioning:
                if (config.get("conditioningIterations")!=str(conditioning) or not re.search(
                        r"--conditioning="+str(conditioning)+r"(?:,|\})",config["options"])
                        or [r["phase"] for r in iterations]!=["WARMUP"]*props["Warmups"]+["CONDITIONING"]*conditioning+["MEASUREMENT"]*8):
                    raise ValueError("Shifted or undeclared timer conditioning")
                for row in conditioned:
                    for channel in ("service","completion-gap"):
                        histogram(worker/"conditioning"/f"iteration-{row['iteration']}-{channel}-bins.csv",int(row["operations"]))
            bins = {}
            for r in measured:
                if int(r["endNs"]) - int(r["startNs"]) < 10**9:
                    raise ValueError("Incomplete timer interval")
                for value, count in histogram(worker / f"iteration-{r['iteration']}-service-bins.csv", int(r["operations"])):
                    bins[value] = bins.get(value, 0) + count
            compiler = [int(r["compilerMs"]) for r in measured]
            result = dict(servicePercentilesNs={"50": quantile(sorted(bins.items()), 50)},
                          rejectionReasons=compiler_rejection_reasons(sum(compiler), compiler))
        with (attempt / invocation["label"] / "host.csv").open(newline="") as stream:
            samples = [evidence.decode_host_row(r) for r in csv.DictReader(stream)]
        host_reasons, _ = evidence.replay_host_gate(manifest, raw, samples)
        host_reasons.extend(invocation.get("hostMonitorErrors", []))
        result["rejectionReasons"].extend(host_reasons)
        durations = [r["nativeObserverReadDurationNs"] / 10**6 for r in samples
                     if "nativeObserverReadDurationNs" in r]
        if durations and statistics.median(durations) > RULES["nativeReadMedianCeilingMs"]:
            result["rejectionReasons"].append("Native observer median read duration exceeded 10 ms")
        rows.append(dict(result, label=invocation["label"], inputs=props, hostPass=not host_reasons,
                         hostRejectionReasons=host_reasons,
                         nativeObserverVersions=sorted({r.get("nativeObserverVersion", 0) for r in samples}),
                         hostWindowStartNs=samples[0]["monotonicNs"], hostWindowEndNs=samples[-1]["monotonicNs"],
                         accepted=not result["rejectionReasons"]))
    state, checks, errors = None, {}, []
    selected = rows
    if policy:
        state = native_retry.select(manifest, rows)
        checks, errors = native_retry.verify_preflights(attempt, manifest, rows, state)
        selected = [r for r in rows if r["label"] in state["selectedLabels"]]
        for row in rows:
            row.update(state["attemptStatuses"][row["label"]])
        errors += state["terminalRejectionReasons"]
    if manifest.get("terminalDriverFailure"):
        errors.append("Terminal floor driver failure: " + manifest["terminalDriverFailure"]["reason"])
    result = dict(reportable=False, rules=RULES, observations=rows,
                  runtimeIdentity=runtime, traceSha256=trace,
                  completedBlocks=len(selected), recordedJvmAttempts=len(rows), expectedBlocks=len(expected),
                  missingBlocks=state["missingSlots"] if state else [k for k,v in expected if k not in {r["label"] for r in rows}],
                  floorDataPass=len(selected) == len(expected) and not errors and all(r["accepted"] for r in selected),
                  rejectionReasons=errors,
                  observerQualified=False, requiresIndependentPilotCoherence=True)
    if state:
        result.update(nativeHostRetryState=state, replayedRetryPreflights=checks,
                      nativeRetryPreflightRejectionReasons=errors)
    evidence.save(attempt / "floors.json", result)
    print(f"floors={attempt / 'floors.json'} pass={result['floorDataPass']} "
          f"slots={len(selected)}/{len(expected)} attempts={len(rows)}", flush=True)
    return result


def coherence(pilot, floors):
    # Replay both datasets; derived flags alone never authorize the campaign.
    import tailcache12_pilot as pilot_driver
    p = pilot_driver.replay(pilot)
    f = replay_floors(floors)
    pm = json.loads((pilot / "manifest.json").read_text())
    fm = json.loads((floors / "manifest.json").read_text())
    if (archive_measurement_source_hash(pilot / "source.tar.gz")
            != archive_measurement_source_hash(floors / "source.tar.gz")
            or pm["inputs"]["warmups"] != fm["inputs"]["warmups"]):
        raise ValueError("Observer evidence differs from the pilot measurement source or preparation")
    if pm["inputs"].get("conditioning",0)!=fm["inputs"].get("conditioning",0):
        raise ValueError("Observer floors and pilot use different conditioning")
    pilot_driver.verify_native_environments([pm, fm])
    if f["runtimeIdentity"] != pm["runtimeIdentity"]:
        raise ValueError("Observer floors and pilot used different VM builds")
    reasons, ratios, overhead = [], [], []
    if not p["dataCompleteAndQualityPass"] or not p["provisionalVariancePass"] or not f["floorDataPass"]:
        reasons.append("Pilot or independent floor prerequisites failed")
    floor_rows = [r for r in f["observations"] if r.get("selectedForAnalysis", r["accepted"])]
    timers = [r["servicePercentilesNs"]["50"] for r in floor_rows if r["inputs"]["Channel"] == "timer"]
    if len(timers) != 2:
        reasons.append("Missing independent timer replicas")
    selected = [r for r in p["observations"] if r.get("selectedForAnalysis", r["accepted"])]
    for row in selected:
        props = row["inputs"]
        if props["Channel"] == "every-operation":
            invocation = next(i for i in pm["invocations"] if i["label"] == row["label"])
            raw = evidence.raw_directory(pilot, invocation)
            overhead.append(dict(label=row["label"], **between_operation_fraction(raw / "every-operation")))
        if props["LiveBytes"] != min(pm["inputs"]["liveBytes"]) or props["Channel"] not in ("sample", "every-operation"):
            continue
        if props["Channel"] == "every-operation":
            ratio = max(timers) / row["servicePercentilesNs"]["50"] if len(timers) == 2 else math.inf
            limit = RULES["timerMedianToEveryopMedianCeiling"]
        else:
            supply = [r["servicePercentilesNs"]["50"] for r in floor_rows
                      if r["inputs"].get("Backend") == props["Backend"]
                      and r["inputs"].get("Payload") == props["Payload"]
                      and r["inputs"]["Channel"] == "floor"]
            if len(supply) != 2:
                raise ValueError("Missing matched supply-floor replicas")
            ratio = max(supply) / row["servicePercentilesNs"]["50"]
            limit = RULES["supplyMedianToSampleMedianCeiling"]
        ratios.append(dict(label=row["label"], ratio=ratio, ceiling=limit))
        if not math.isfinite(ratio) or ratio > limit:
            reasons.append(row["label"] + ": observer/floor median ratio exceeded its prospective ceiling")
    directions = []
    for payload in pm["inputs"]["payloads"]:
        for live in (min(pm["inputs"]["liveBytes"]), max(pm["inputs"]["liveBytes"])):
            selected = [c for c in p["comparisons"] if c["payloadBytes"] == payload and c["applicationLiveBytes"] == live]
            for endpoint in ("99", "99.9"):
                signs = []
                for c in selected:
                    if not c["complete"]:
                        reasons.append("Missing independent channel comparison")
                        continue
                    interval = c["ratios"][endpoint]
                    signs.append(-1 if interval["upper95"] < 1 else 1 if interval["lower95"] > 1 else 0)
                directions.append(dict(payloadBytes=payload, liveBytes=live, endpoint=endpoint, channelDirections=signs))
                if -1 in signs and 1 in signs:
                    reasons.append(f"Opposite resolved channel directions at payload={payload},live={live},p{endpoint}")
    result = dict(reportable=False, observerQualified=not reasons, rejectionReasons=reasons,
                  rules=RULES, floorRatios=ratios, channelDirections=directions,
                  betweenOperationFractions=overhead,
                  limits=["Between-call time includes real GC/OS pauses and is not pure recorder overhead.",
                          "No floor was subtracted from any percentile.",
                          "Unresolved channel intervals do not prove numerical equivalence."])
    evidence.save(pilot / "observer-review.json", result)
    print(f"observer={pilot / 'observer-review.json'} qualified={result['observerQualified']}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("floors", "audit", "coherence"))
    parser.add_argument("attempt_id")
    parser.add_argument("--warmups", type=int, default=96)
    parser.add_argument("--conditioning",type=int,choices=range(65),default=0)
    parser.add_argument("--pilot")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--native-host-retries",type=int,choices=(0,1,2),default=0)
    parser.add_argument("--native-host-retry-budget",type=int,choices=range(1,9),default=8)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.attempt_id):
        parser.error("Invalid attempt ID")
    attempt = evidence.REPORTS / args.attempt_id
    if args.stage == "coherence":
        if not args.pilot:
            parser.error("Coherence requires --pilot")
        return 0 if coherence(evidence.REPORTS / args.pilot, attempt)["observerQualified"] else 1
    if args.stage == "audit":
        return 0 if replay_floors(attempt)["floorDataPass"] else 1
    if args.warmups < 12:
        parser.error("At least twelve warmups required")
    grid = floor_grid(args.warmups,args.conditioning)
    inputs = SimpleNamespace(stage="observer-floor", warmups=args.warmups, measurements=8,
        residents=32768, heap_mib=512, churn_mib=32, live_mib=[0], payloads=[256,4096],
        seed=24301, repeats=2, channels=["floor","timer"], resume=args.resume,
        native_host_retries=args.native_host_retries,native_host_retry_budget=args.native_host_retry_budget)
    inputs.conditioning=args.conditioning
    manifest = calibration.prepare(attempt, inputs, grid)
    manifest["observerRules"] = RULES
    evidence.save(attempt / "manifest.json", manifest)
    if manifest.get("nativeHostRetryPolicy"):
        result = native_retry.run_grid(attempt, manifest, replay_floors,
            lambda p: "tailCache12SupplyFloor" if p["Channel"] == "floor" else "tailCache12EveryOperation")
        return 0 if result["floorDataPass"] else 1
    completed = {r["label"] for r in manifest["invocations"]}
    for label, props in grid:
        if label in completed:
            continue
        if manifest["invocations"] and replay_floors(attempt)["observations"][-1]["rejectionReasons"]:
            break
        evidence.invoke(attempt, manifest, label,
                        "tailCache12SupplyFloor" if props["Channel"] == "floor" else "tailCache12EveryOperation", props)
        if replay_floors(attempt)["observations"][-1]["rejectionReasons"]:
            break
    return 0 if replay_floors(attempt)["floorDataPass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
