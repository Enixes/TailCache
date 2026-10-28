"""Per-fork evidence and replication-level statistics for Task 12.

Percentiles are nearest-rank queries of retained histogram values. JMH 1.37
values are quantized lower bounds; every-operation HdrHistogram exports use
upper-equivalent bounds. JMH's interpolated percentiles remain separate.
Iterations and operations are never independent experimental replicas.
"""
import csv
import json
import math
import pathlib
import random
import re
import statistics

from tailcache12_analysis import (compiler_rejection_reasons, every_operation_summary,
                                 gc_summary, parse_gc, quantile, validate_windows)

VALUE_GENERATOR = "xorshift-key-version-v1"
JMH_SAMPLE_SECONDARIES = {"p0.00", "p0.50", "p0.90", "p0.95", "p0.99", "p0.999", "p0.9999", "p1.00"}


def every_operation_fork_summary(directory, inputs, expected_trace=None,
                                 jdk_version=None, occupancy_band=None, compiler_diagnostics=False):
    """Validate actual controls as well as the worker's measured quality evidence."""
    directory = pathlib.Path(directory)
    worker = directory / "worker"
    configuration = dict(line.split("=", 1) for line in
                         (worker / "configuration.txt").read_text().splitlines() if "=" in line)
    if configuration["backend"] != inputs["Backend"]:
        raise ValueError("Backend identity mismatch")
    for prop, field in (("Residents", "residentEntries"), ("Payload", "payloadBytes"),
                        ("LiveBytes", "applicationLiveBytes"), ("Seed", "seed"),
                        ("ChurnBytesPerSecond", "churnBytesPerSecond")):
        if not re.search(r"\b" + field + "=" + str(inputs[prop]) + r"(?:,|\])", configuration["config"]):
            raise ValueError(f"Workload input mismatch: {field}")
    for flag in (f"-Xms{inputs['HeapMiB']}m", f"-Xmx{inputs['HeapMiB']}m", "-XX:+UseG1GC"):
        if flag not in configuration["jvmArgs"]:
            raise ValueError("Missing fixed-heap/G1 evidence")
    expected_xml = "true" if compiler_diagnostics else "false"
    if configuration.get("compilerCounters") != "true" or configuration.get("compilerXml") != expected_xml:
        raise ValueError("Missing counters or profiled every-operation fork")
    if ("-XX:+LogCompilation" in configuration["jvmArgs"]) != compiler_diagnostics:
        raise ValueError("Compiler instrumentation differs from the channel")
    if configuration["valueGenerator"] != VALUE_GENERATOR:
        raise ValueError("Value generator mismatch")
    if expected_trace is not None and configuration["traceSha256"] != expected_trace:
        raise ValueError("Workload trace mismatch")
    if jdk_version is not None and configuration["jdkVersion"] != jdk_version:
        raise ValueError("Runtime identity differs from the frozen protocol")
    options = configuration["options"]
    for option, expected in (("--warmup", inputs["Warmups"]), ("--measure", inputs["Measurements"]),
                             ("--iteration-ms", 1000)):
        if not re.search(re.escape(option) + "=" + str(expected) + r"(?:,|\})", options):
            raise ValueError("Every-operation timing controls differ from the protocol")
    with (worker / "iterations.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if (len(rows) != inputs["Warmups"] + inputs["Measurements"]
            or sum(r["phase"] == "WARMUP" for r in rows) != inputs["Warmups"]):
        raise ValueError("Incomplete warmup/measurement iteration evidence")
    for phase, expected in (("WARMUP", inputs["Warmups"]), ("MEASUREMENT", inputs["Measurements"])):
        if [int(r["iteration"]) for r in rows if r["phase"] == phase] != list(range(1, expected + 1)):
            raise ValueError("Missing or repeated worker iteration")
    if any(int(r["endNs"]) - int(r["startNs"]) < 1_000_000_000 or int(r["operations"]) <= 0 for r in rows):
        raise ValueError("Incomplete one-second worker interval")
    integrity = dict(line.split("=", 1) for line in
                     (worker / "integrity.txt").read_text().splitlines() if "=" in line)
    for field in ("contentChecksum", "applicationChecksum", "consumed"):
        int(integrity[field])
    if (int(integrity["operations"]) != sum(int(r["operations"]) for r in rows)
            or int(integrity["writes"]) != sum(int(r["writes"]) for r in rows)):
        raise ValueError("Worker totals disagree with post-trial integrity evidence")
    result = every_operation_summary(directory, inputs["ChurnBytesPerSecond"], occupancy_band)
    reasons = result["rejectionReasons"]
    compiler = result["compilerPerIterationMs"]
    reasons.extend(compiler_rejection_reasons(sum(compiler), compiler, inputs["Measurements"]))
    if not result["p999Adequate"]:
        reasons.append("fewer than 100000 retained observations for p99.9")
    result.update(kind="every-operation", inputs=inputs, traceSha256=configuration["traceSha256"],
                  jdkVersion=configuration["jdkVersion"], accepted=not reasons)
    return result


def merged_histograms(iterations, operations):
    if not iterations or len(iterations) != len(operations):
        raise ValueError("Histogram/worker iteration counts differ")
    merged, counts = {}, []
    for bins, completed in zip(iterations, operations):
        previous, count = -1, 0
        for value, n in bins:
            if (not math.isfinite(value) or value < 0 or value != int(value)
                    or n != int(n) or n <= 0 or value <= previous):
                raise ValueError("Invalid or unsorted JMH histogram")
            previous = value
            count += int(n)
            merged[int(value)] = merged.get(int(value), 0) + int(n)
        if count <= 0 or completed <= 0 or count > completed:
            raise ValueError("JMH samples are missing or exceed completed operations")
        counts.append(count)
    bins = sorted(merged.items())
    # JMH 1.37 SampleBuffer stores sample >> bucket, then exports key << bucket.
    upper = {v: v + (1 << max(0, v.bit_length() - 10)) - 1 for v, _ in bins}
    if any(v % (upper[v] - v + 1) for v, _ in bins):
        raise ValueError("Histogram values do not match JMH 1.37 quantization")
    return {"sampleCount": sum(counts), "iterationSampleCounts": counts,
            "servicePercentilesNs": {str(p): quantile(bins, p) for p in (50, 95, 99, 99.9)},
            "serviceMaxQuantizedNs": bins[-1][0], "serviceMaxUpperBoundNs": upper[bins[-1][0]],
            "sampledStallCountBounds": {str(t): {
                "lower": sum(n for v, n in bins if v > t),
                "upper": sum(n for v, n in bins if upper[v] > t)} for t in (1_000_000, 10_000_000)},
            "histogramValueSemantics": "JMH 1.37 quantized lower bounds; stall counts bounded at straddling bins"}


def jmh_fork_summary(raw, kind, inputs, expected_trace, runtime_identity, occupancy_band=None):
    """One invocation must contain exactly one condition and one fresh worker JVM."""
    raw = pathlib.Path(raw)
    records = json.loads((raw / kind / "results.json").read_text())
    if len(records) != 1:
        raise ValueError("Expected exactly one JMH condition")
    record = records[0]
    if record.get("jmhVersion") != "1.37":
        raise ValueError("Histogram semantics require the qualified JMH 1.37 build")
    for field in ("jmhVersion", "jdkVersion", "vmName", "vmVersion"):
        if field not in runtime_identity or record.get(field) != runtime_identity[field]:
            raise ValueError("Runtime identity differs from the frozen protocol")
    secondaries = set(record.get("secondaryMetrics", {}))
    allowed_secondaries = JMH_SAMPLE_SECONDARIES if kind != "throughput" else set()
    if kind in ("sample", "sample-calibration", "throughput") and (secondaries - allowed_secondaries
            or "-XX:+LogCompilation" in record["jvmArgs"]):
        raise ValueError("A profiled fork cannot supply an unprofiled endpoint")
    if record["forks"] != 1 or record["threads"] != 1:
        raise ValueError("Per-fork analysis requires one fresh single-worker JVM")
    fields = {"backend": "Backend", "payloadBytes": "Payload", "residentEntries": "Residents",
              "applicationLiveBytes": "LiveBytes", "churnBytesPerSecond": "ChurnBytesPerSecond", "seed": "Seed"}
    if any(str(record["params"][field]) != str(inputs[prop]) for field, prop in fields.items()):
        raise ValueError("JMH condition inputs differ from the protocol")
    if (record["warmupIterations"] != inputs["Warmups"]
            or record["measurementIterations"] != inputs["Measurements"]
            or record["measurementTime"] != "1 s" or record.get("warmupTime") != "1 s"):
        raise ValueError("JMH timing controls differ from the protocol")
    for flag in (f"-Xms{inputs['HeapMiB']}m", f"-Xmx{inputs['HeapMiB']}m", "-XX:+UseG1GC"):
        if flag not in record["jvmArgs"]:
            raise ValueError("Missing fixed-heap/G1 evidence")
    text = (raw / kind / "jmh.txt").read_text()
    # Fork stdout can be forwarded to the Gradle console rather than the JMH text sink.
    console = inputs.get("ConsoleFile")
    if console:
        text += pathlib.Path(console).read_text()
    if f"traceSha256={expected_trace}" not in text or f"valueGenerator={VALUE_GENERATOR}" not in text:
        raise ValueError("Missing or mismatched workload fingerprint")
    if "[TailCache12][integrity]" not in text:
        raise ValueError("Missing post-trial integrity verification")
    sidecars = list((raw / kind).glob("iterations-*.csv"))
    if len(sidecars) != 1:
        raise ValueError("Expected one worker sidecar")
    with sidecars[0].open(newline="") as stream:
        rows = [r for r in csv.DictReader(stream) if r["phase"] == "MEASUREMENT"]
    if len(rows) != inputs["Measurements"]:
        raise ValueError("Incomplete worker iteration evidence")
    windows = [(int(r["envelopeStartNs"]), int(r["envelopeEndNs"])) for r in rows]
    validate_windows(windows)
    operations = [int(r["operations"]) for r in rows]
    if any(n <= 0 for n in operations):
        raise ValueError("No completed operations in a measurement iteration")
    compiler = [int(r["workerEnvelopeCompilerMs"]) for r in rows]
    reasons = compiler_rejection_reasons(sum(compiler), compiler, inputs["Measurements"])
    if any(not math.isfinite(float(r["churnPayloadBytesPerSecond"]))
           or abs(float(r["churnPayloadBytesPerSecond"]) - inputs["ChurnBytesPerSecond"])
           > max(1, inputs["ChurnBytesPerSecond"] * 0.1) for r in rows):
        reasons.append("non-cache churn missed ±10% target")
    if any(int(r["churnDroppedBytes"]) != 0 for r in rows):
        reasons.append("churn demand was dropped")
    if any(int(r["churnJvmAllocatedBytes"]) < int(r["churnPayloadBytes"]) for r in rows):
        reasons.append("JVM allocation does not corroborate churn")
    result = {"kind": kind, "inputs": {k: v for k, v in inputs.items() if k != "ConsoleFile"},
              "jdkVersion": record["jdkVersion"], "traceSha256": expected_trace,
              "operations": sum(operations), "iterationOperations": operations,
              "compilerPerIterationMs": compiler, "rejectionReasons": reasons}
    if kind in ("sample", "sample-calibration", "compiler"):
        if record["mode"] != "sample" or record["primaryMetric"]["scoreUnit"] != "ns/op":
            raise ValueError("Wrong latency mode/units")
        forks = record["primaryMetric"].get("rawDataHistogram", [])
        if len(forks) != 1:
            raise ValueError("Missing per-fork JMH histograms")
        result.update(merged_histograms(forks[0], operations))
        result["reportedJmhPercentiles"] = record["primaryMetric"]["scorePercentiles"]
        result["p999Adequate"] = result["sampleCount"] >= 100_000
        if not result["p999Adequate"] and kind != "compiler":
            reasons.append("fewer than 100000 retained observations for p99.9")
    elif kind in ("allocation", "throughput"):
        if record["mode"] != "thrpt" or record["primaryMetric"]["scoreUnit"] != "ops/s":
            raise ValueError("Wrong throughput mode/units")
        result["operationsPerSecond"] = record["primaryMetric"]["score"]
        if kind == "allocation":
            metrics = record["secondaryMetrics"]
            required = ("gc.alloc.rate", "gc.alloc.rate.norm", "gc.count", "gc.time")
            if any(name not in metrics for name in required):
                raise ValueError("Missing allocation/GC profiler evidence")
            result["gcProfiler"] = {name: metrics[name] for name in required}
    else:
        raise ValueError("Unsupported JMH study channel")
    if kind in ("sample-calibration", "allocation", "compiler"):
        logs = list((raw / kind).glob("gc-*.log"))
        if len(logs) != 1:
            raise ValueError("Expected one raw G1 log")
        result["gc"] = gc_summary(parse_gc(logs[0]), windows, sum(operations))
        occupancy = result["gc"]["postGcUsedHeapMedianFraction"]
        if occupancy is None:
            reasons.append("missing measured post-GC occupancy")
        elif occupancy_band is not None and abs(occupancy - occupancy_band) > 0.05:
            reasons.append("post-GC occupancy missed calibrated band")
        if (result["gc"]["oldRegionsMedianHeapFraction"] is None
                or result["gc"]["maxHumongousRegionsAfter"] is None):
            reasons.append("missing old/humongous-region evidence")
    if kind == "compiler":
        if "-XX:+LogCompilation" not in record["jvmArgs"] or not list((raw / kind).glob("jit-*.xml")):
            raise ValueError("Missing method-level compiler diagnostic evidence")
        metric = record["secondaryMetrics"]["compiler.time.profiled"]
        result["compilerTotalMs"] = metric["score"]
        result["broadCompilerPerIterationMs"] = metric.get("rawData", [[]])[0]
        reasons.extend(compiler_rejection_reasons(metric["score"], result["broadCompilerPerIterationMs"],
                                                  inputs["Measurements"]))
    result["accepted"] = not reasons
    return result


def hierarchical_ratio(blocks, seed=24301, resamples=5000):
    """Paired fork ordinals within counterbalanced passes; two-level bootstrap."""
    if len(blocks) < 2 or any(len(block) < 3 for block in blocks):
        raise ValueError("Require two independent passes and three paired forks per pass")
    if any(a <= 0 or b <= 0 or not math.isfinite(a + b) for block in blocks for a, b in block):
        raise ValueError("Endpoints must be positive and finite")
    if resamples < 1000:
        raise ValueError("At least 1000 bootstrap replicates required")
    def ratio(block):
        return statistics.median(b for _, b in block) / statistics.median(a for a, _ in block)
    estimates = [ratio(block) for block in blocks]
    rng = random.Random(seed)
    draws = []
    for _ in range(resamples):
        selected = rng.choices(blocks, k=len(blocks))
        ratios = [ratio(rng.choices(block, k=len(block))) for block in selected]
        draws.append(math.exp(statistics.median(math.log(r) for r in ratios)))
    draws.sort()
    return {"ratio": math.exp(statistics.median(math.log(r) for r in estimates)),
            "lower95": draws[math.ceil(0.025 * resamples) - 1],
            "upper95": draws[math.ceil(0.975 * resamples) - 1],
            "blockRatios": estimates, "independentPasses": len(blocks),
            "pairedForksPerPass": [len(block) for block in blocks], "resamples": resamples,
            "method": "paired-fork hierarchical bootstrap, outer counterbalanced passes",
            "limits": "Two outer passes give coarse uncertainty. No operations/iterations are independent replicas."}


def variance_reasons(backend_blocks, p99_limit=1.25, p999_limit=1.5):
    reasons = []
    for backend, blocks in backend_blocks.items():
        for endpoint, limit in (("99", p99_limit), ("99.9", p999_limit)):
            if any(not math.isfinite(fork[endpoint]) or fork[endpoint] <= 0 for block in blocks for fork in block):
                reasons.append(f"{backend}: invalid endpoint evidence")
                continue
            medians = [statistics.median(fork[endpoint] for fork in block) for block in blocks]
            if len(medians) < 2 or min(medians) <= 0:
                reasons.append(f"{backend}: missing independent positive endpoint blocks")
            elif max(medians) / min(medians) > limit:
                reasons.append(f"{backend}: p{endpoint} between-order ratio exceeds {limit}")
    return reasons
