#!/usr/bin/env python3
"""Replayable G1/window analysis and replication summaries for Task 12.

Only timenanos-decorated logs are accepted: they share System.nanoTime's clock.
All reported occupancy is post-collection used space, not an exact live-object census.
"""
import csv
import json
import math
import pathlib
import random
import re
import statistics

VERSION = "tailcache12-analysis-v1"
SIZE = r"([0-9]+(?:\.[0-9]+)?)([BKMG])"
PAUSE = re.compile(r"^GC\((\d+)\) (Pause .+?)\s+([\d.]+)ms$")
HEAP = re.compile(SIZE + r"->" + SIZE + r"\(" + SIZE + r"\)")
REGIONS = re.compile(r"GC\((\d+)\) (Eden|Survivor|Old|Humongous) regions: (\d+)->(\d+)")


def size_bytes(number, unit):
    return round(float(number) * 1024 ** "BKMG".index(unit))


def read_csv(path):
    with pathlib.Path(path).open(newline="") as stream:
        return list(csv.DictReader(stream))


def parse_gc(path):
    pauses, safepoints, concurrent, pending = [], [], [], {}
    regions, errors = {}, []
    g1, region_bytes, max_heap = False, None, None
    for line in pathlib.Path(path).read_text().splitlines():
        stamp = re.search(r"\[(-?\d+)ns\]", line)
        if not stamp:
            raise ValueError(f"GC log lacks timenanos clock: {path}")
        timestamp = int(stamp[1])
        tags = re.search(r"\[(?:info|debug|trace|warning|error)\]\[([^]]+)\]\s+(.*)$", line)
        if not tags:
            raise ValueError(f"Malformed unified log line: {line}")
        tag, message = tags[1].strip(), tags[2]
        g1 |= message == "Using G1"
        if "Heap Region Size:" in message:
            match = re.search(SIZE, message)
            if match:
                region_bytes = size_bytes(*match.groups())
        if "Heap Max Capacity:" in message:
            match = re.search(SIZE, message)
            if match:
                max_heap = size_bytes(*match.groups())
        match = REGIONS.search(message)
        if match:
            regions.setdefault(match[1], {})[match[2].lower()] = int(match[4])
        start = re.match(r"GC\((\d+)\) (Pause .+)$", message)
        if tag == "gc,start" and start:
            key = (start[1], start[2])
            if key in pending:
                errors.append(f"Duplicate pause start: {key}")
            pending[key] = timestamp
        final = PAUSE.match(message) if tag == "gc" else None
        if final:
            gc_id, description, duration = final.groups()
            heap = HEAP.search(description)
            # Heap figures follow the pause label; strip them for matching gc,start.
            name = description[:heap.start()].rstrip() if heap else description
            key = (gc_id, name)
            # G1 can append this outcome only at pause end. Preserve the outcome,
            # but match the exact start label rather than inventing a second pause.
            evacuation_failure = name.endswith(" (Evacuation Failure)")
            if key not in pending and evacuation_failure:
                base_name = name.removesuffix(" (Evacuation Failure)")
                if (gc_id, base_name) in pending:
                    key = (gc_id, base_name)
            logged_ns = round(float(duration) * 1_000_000)
            start_ns = pending.pop(key, None)
            derived = start_ns is None
            start_ns = timestamp - logged_ns if derived else start_ns
            if start_ns > timestamp or logged_ns < 0:
                errors.append(f"Invalid pause duration: {message}")
            row = {"gcId": gc_id, "kind": name, "startNs": start_ns, "endNs": timestamp,
                   "loggedDurationNs": logged_ns, "startDerivedFromDuration": derived,
                   "startKind": None if derived else key[1], "evacuationFailure": evacuation_failure,
                   "regionsAfter": dict(regions.get(gc_id, {})) if heap else {}}
            if heap:
                values = heap.groups()
                row.update(heapBeforeBytes=size_bytes(*values[:2]), heapAfterBytes=size_bytes(*values[2:4]),
                           heapCapacityBytes=size_bytes(*values[4:6]))
                if row["heapAfterBytes"] > row["heapCapacityBytes"]:
                    errors.append(f"Heap used exceeds capacity: {message}")
            pauses.append(row)
        if tag == "gc" and re.match(r"GC\(\d+\) Concurrent .+ Cycle", message):
            match = re.match(r"GC\((\d+)\) (Concurrent .+ Cycle)(?: ([\d.]+)ms)?$", message)
            if match:
                concurrent.append({"gcId": match[1], "kind": match[2], "timestampNs": timestamp,
                                   "completed": match[3] is not None,
                                   "durationNs": None if match[3] is None else round(float(match[3]) * 1e6)})
        if tag == "safepoint" and message.startswith("Safepoint "):
            match = re.search(r'Total: (\d+) ns', message)
            if not match:
                errors.append("Safepoint lacks total duration")
            else:
                safepoints.append({"startNs": timestamp - int(match[1]), "endNs": timestamp,
                                   "kind": message.split('"')[1]})
    if pending:
        errors.append(f"Unfinished pauses: {list(pending)}")
    if not g1 or region_bytes is None or max_heap is None:
        errors.append("Missing G1/region-size/max-heap initialization evidence")
    if errors:
        raise ValueError("; ".join(errors))
    return {"pauses": pauses, "safepoints": safepoints, "concurrentCycles": concurrent,
            "regionBytes": region_bytes, "maxHeapBytes": max_heap}


def overlap_ns(start, end, windows):
    return sum(max(0, min(end, b) - max(start, a)) for a, b in windows)


def validate_windows(windows):
    if not windows or any(a >= b for a, b in windows):
        raise ValueError("Missing or nonpositive measurement windows")
    if any(windows[i][1] > windows[i + 1][0] for i in range(len(windows) - 1)):
        raise ValueError("Unsorted or overlapping measurement windows")


def compiler_rejection_reasons(total_ms, iteration_ms, expected_iterations=8):
    """The frozen 1% aggregate and per-iteration compiler-time screen."""
    if (len(iteration_ms) != expected_iterations or not math.isfinite(total_ms) or total_ms < 0
            or any(not math.isfinite(v) or v < 0 for v in iteration_ms)):
        return ["missing or invalid compiler-time evidence"]
    reasons = []
    if total_ms > 80:
        reasons.append("compiler total exceeds 80 ms")
    if max(iteration_ms, default=0) > 10:
        reasons.append("compiler iteration exceeds 10 ms")
    return reasons


def gc_summary(parsed, windows, operations):
    validate_windows(windows)
    if operations <= 0:
        raise ValueError("No completed operations")
    elapsed = sum(b - a for a, b in windows)
    paused = [dict(p, overlapNs=overlap_ns(p["startNs"], p["endNs"], windows))
              for p in parsed["pauses"] if overlap_ns(p["startNs"], p["endNs"], windows) > 0]
    occupancy = [p for p in parsed["pauses"] if "heapAfterBytes" in p
                 and any(a <= p["endNs"] < b for a, b in windows)]
    fractions = [p["heapAfterBytes"] / p["heapCapacityBytes"] for p in occupancy]
    old_fractions = [p["regionsAfter"]["old"] * parsed["regionBytes"] / p["heapCapacityBytes"]
                     for p in occupancy if "old" in p["regionsAfter"]]
    return {"measurementSeconds": elapsed / 1e9, "operations": operations,
            "pauseCount": len(paused), "pauseTotalWholeMs": sum(p["loggedDurationNs"] for p in paused) / 1e6,
            "evacuationFailureCount": sum(p.get("evacuationFailure", False) for p in paused),
            "pauseOverlapMs": sum(p["overlapNs"] for p in paused) / 1e6,
            "pauseMaxWholeMs": max((p["loggedDurationNs"] for p in paused), default=0) / 1e6,
            "pauseExposureFraction": sum(p["overlapNs"] for p in paused) / elapsed,
            "pausesPerSecond": len(paused) * 1e9 / elapsed, "pausesPerMillionOperations": len(paused) * 1e6 / operations,
            "safepointOverlapMs": sum(overlap_ns(s["startNs"], s["endNs"], windows)
                                       for s in parsed["safepoints"]) / 1e6,
            "completedConcurrentCycles": sum(c["completed"] and any(a <= c["timestampNs"] < b for a, b in windows)
                                             for c in parsed["concurrentCycles"]),
            "postGcUsedHeapMedianFraction": statistics.median(fractions) if fractions else None,
            "postGcUsedHeapMinFraction": min(fractions) if fractions else None,
            "postGcUsedHeapMaxFraction": max(fractions) if fractions else None,
            "oldRegionsMedianHeapFraction": statistics.median(old_fractions) if old_fractions else None,
            "maxHumongousRegionsAfter": max((p["regionsAfter"]["humongous"] for p in occupancy
                                             if "humongous" in p["regionsAfter"]), default=None),
            "occupancySamples": occupancy, "pauses": paused,
            "limits": "Post-collection used heap and old-region capacity are not an exact live-set census. Safepoint and GC totals overlap and must not be added."}


def histogram(path, expected_count):
    bins = [(int(r["upperEquivalentNs"]), int(r["count"])) for r in read_csv(path)]
    if any(v < 0 or n <= 0 for v, n in bins) or any(bins[i][0] >= bins[i + 1][0] for i in range(len(bins) - 1)):
        raise ValueError("Invalid histogram bins")
    if sum(n for _, n in bins) != expected_count or expected_count <= 0:
        raise ValueError("Histogram count does not match completed operations")
    return bins


def quantile(bins, percentile):
    total = sum(n for _, n in bins)
    if not total:
        raise ValueError("Empty histogram")
    target = max(1, math.ceil(percentile * total / 100))
    current = 0
    for value, count in bins:
        current += count
        if current >= target:
            return value
    raise AssertionError("Unreachable quantile")


def every_operation_summary(directory, target_churn, calibration_band=None):
    directory = pathlib.Path(directory)
    worker = directory / "worker"
    config = (worker / "configuration.txt").read_text()
    if "validation=none\n" not in config or "timerFloor=false\n" not in config:
        raise ValueError("Validation/floor run cannot qualify as workload evidence")
    rows = [r for r in read_csv(worker / "iterations.csv") if r["phase"] == "MEASUREMENT"]
    windows = [(int(r["startNs"]), int(r["endNs"])) for r in rows]
    validate_windows(windows)
    service, gaps = {}, {}
    for row in rows:
        count = int(row["operations"])
        for channel, merged in (("service", service), ("completion-gap", gaps)):
            for value, n in histogram(worker / f"iteration-{row['iteration']}-{channel}-bins.csv", count):
                merged[value] = merged.get(value, 0) + n
    logs = list(directory.glob("gc-*.log"))
    if len(logs) != 1:
        raise ValueError("Expected one raw G1 log per fresh worker")
    summary = gc_summary(parse_gc(logs[0]), windows, sum(int(r["operations"]) for r in rows))
    elapsed = sum(b - a for a, b in windows)
    rates = [float(r["churnPayloadBytesPerSecond"]) for r in rows]
    reasons = []
    if any(not math.isfinite(rate) or abs(rate - target_churn) > max(1, target_churn * 0.1) for rate in rates):
        reasons.append("non-cache churn missed ±10% target")
    if any(int(r["churnDroppedBytes"]) != 0 for r in rows):
        reasons.append("churn demand was dropped")
    if any(int(r["churnJvmAllocatedBytes"]) < int(r["churnPayloadBytes"]) for r in rows):
        reasons.append("JVM allocation does not corroborate churn")
    if summary["postGcUsedHeapMedianFraction"] is None:
        reasons.append("missing measured post-GC occupancy")
    if summary["oldRegionsMedianHeapFraction"] is None or summary["maxHumongousRegionsAfter"] is None:
        reasons.append("missing old/humongous-region evidence")
    if not (worker / "integrity.txt").is_file():
        reasons.append("missing workload integrity evidence")
    if calibration_band is not None:
        fraction = summary["postGcUsedHeapMedianFraction"]
        if fraction is None or abs(fraction - calibration_band) > 0.05:
            reasons.append("post-GC occupancy missed calibrated ±5 percentage-point band")
    summary.update(schemaVersion=VERSION, servicePercentilesNs={str(p): quantile(sorted(service.items()), p)
                                                              for p in (50, 95, 99, 99.9)},
                   gapPercentilesNs={str(p): quantile(sorted(gaps.items()), p) for p in (50, 95, 99, 99.9)},
                   serviceMaxNs=max(int(r["serviceMaxNs"]) for r in rows),
                   completionGapMaxNs=max(int(r["completionGapMaxNs"]) for r in rows),
                   serviceAbove1ms=sum(int(r["serviceAbove1ms"]) for r in rows),
                   gapAbove1ms=sum(int(r["gapAbove1ms"]) for r in rows),
                   measurementIterations=len(rows), minimumIterationOperations=min(int(r["operations"]) for r in rows),
                   workloadOperationsPerSecond=summary["operations"] * 1e9 / elapsed,
                   churnPayloadRates=rates, rejectionReasons=reasons,
                   compilerPerIterationMs=[int(r.get("compilerMs", -1)) for r in rows])
    summary["p999Adequate"] = summary["operations"] >= 100_000
    return summary


def paired_bootstrap(pairs, seed=24301, resamples=5000):
    """Each pair is an independent counterbalanced block of fork-median endpoints."""
    if len(pairs) < 2 or any(a <= 0 or b <= 0 or not math.isfinite(a + b) for a, b in pairs):
        raise ValueError("At least two positive, finite independent block pairs required")
    logs = [math.log(chronicle / caffeine) for caffeine, chronicle in pairs]
    rng = random.Random(seed)
    draws = sorted(math.exp(statistics.median(rng.choices(logs, k=len(logs)))) for _ in range(resamples))
    return {"ratio": math.exp(statistics.median(logs)), "lower95": draws[int(0.025 * resamples)],
            "upper95": draws[min(resamples - 1, int(0.975 * resamples))], "independentBlocks": len(pairs),
            "limits": "Descriptive block bootstrap; two blocks give coarse uncertainty. No operations treated as independent replicates."}
