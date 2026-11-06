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


def validate_lifecycle_preparation(inputs,text,jvm_args):
    version=inputs.get('LifecycleWarmupVersion','none')
    observed=set(re.findall(r'(?:^|\s)lifecycleWarmupVersion=([^\s,]+)',text,re.M))
    if version=='none':
        if observed-{'none'}: raise ValueError('Undeclared lifecycle maintenance preparation')
        return
    if version!='lifecycle-maintenance-v1' or f'-Dtailcache12.lifecycleWarmupVersion={version}' not in jvm_args:
        raise ValueError('Missing or unknown lifecycle preparation JVM control')
    expected=dict(lifecycleWarmupVersion=version,lifecycleWarmupTrials='3',
        lifecycleMaintenanceBatches='20000',lifecycleMaintenanceBatchOperations='128',
        lifecycleWarmupOperations='7680000',lifecycleWarmupWrites='384000')
    for key,value in expected.items():
        values=set(re.findall(r'(?:^|\s)'+key+r'=([^\s,]+)',text,re.M))
        if values!={value}: raise ValueError('Missing or mismatched lifecycle preparation evidence: '+key)


def allocation_profiler_vectors(metrics,count,text,jmh_version):
    """Align pinned GCProfiler's optional gc.time from indexed original output."""
    required=('gc.alloc.rate','gc.alloc.rate.norm','gc.count','gc.time')
    vectors={}
    for name in required:
        data=metrics[name].get('rawData',[])
        if len(data)!=1 or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in data[0]):
            raise ValueError('Invalid allocation profiler raw vector: '+name)
        if name!='gc.time' and len(data[0])!=count:
            raise ValueError('Incomplete allocation profiler conditioning evidence: '+name)
        vectors[name]=list(data[0])
    if any(v!=int(v) for v in vectors['gc.count']):
        raise ValueError('Nonintegral GC profiler collection count')
    times=vectors['gc.time']
    if len(times)==count: return vectors,[]
    if jmh_version!='1.37' or not 0<=len(times)<count:
        raise ValueError('Unsupported sparse GC profiler vector')
    lines=text.splitlines(); blocks=[]
    for i,line in enumerate(lines):
        match=re.fullmatch(r'Iteration\s+(\d+):.*',line)
        if match:
            block=[]
            for following in lines[i+1:]:
                if not following.strip(): break
                block.append(following)
            blocks.append((int(match[1]),block))
    if [i for i,_ in blocks]!=list(range(1,count+1)):
        raise ValueError('Missing, shifted or duplicate indexed GC profiler iterations')
    def displayed(block,name,unit):
        rows=[line for line in block if re.match(r'\s+'+re.escape(name)+':',line)]
        if not rows: return None
        if len(rows)!=1: raise ValueError('Duplicate indexed GC profiler metric')
        match=re.fullmatch(r'\s+'+re.escape(name)+r':\s+(≈\s+)?([-+\d.]+)\s+'+unit+r'\s*',rows[0])
        if not match: raise ValueError('Invalid indexed GC profiler value')
        value=float(match[2])
        if not math.isfinite(value) or value<0 or (match[1] and value!=0):
            raise ValueError('Invalid rounded GC profiler value')
        return value
    aligned=[]; zeros=[]; cursor=0
    for i,block in blocks:
        collections=displayed(block,'gc.count','counts')
        if collections!=vectors['gc.count'][i-1]:
            raise ValueError('Indexed GC count differs from JSON order')
        value=displayed(block,'gc.time','ms')
        if value is None:
            if collections!=0: raise ValueError('Missing GC time despite a recorded collection')
            aligned.append(0); zeros.append(i)
        else:
            if cursor>=len(times) or abs(value-times[cursor])>.00051:
                raise ValueError('Indexed GC time differs from sparse JSON order')
            aligned.append(times[cursor]); cursor+=1
    if cursor!=len(times): raise ValueError('Unmatched sparse GC profiler values')
    vectors['gc.time']=aligned
    return vectors,zeros


def every_operation_fork_summary(directory, inputs, expected_trace=None,
                                 jdk_version=None, occupancy_band=None, compiler_diagnostics=False,
                                 runtime_identity=None):
    """Validate actual controls as well as the worker's measured quality evidence."""
    directory = pathlib.Path(directory)
    worker = directory / "worker"
    configuration = dict(line.split("=", 1) for line in
                         (worker / "configuration.txt").read_text().splitlines() if "=" in line)
    validate_lifecycle_preparation(inputs,(worker/'configuration.txt').read_text(),configuration['jvmArgs'])
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
    if runtime_identity is not None and any(configuration.get(k) != runtime_identity[k]
                                            for k in ("jdkVersion", "vmName", "vmVersion")):
        raise ValueError("Exact every-operation VM build differs from the frozen protocol")
    options = configuration["options"]
    conditioning=inputs.get("Conditioning",0)
    if type(conditioning) is not int or not 0<=conditioning<=64:
        raise ValueError("Invalid conditioning controls")
    if conditioning and (configuration.get("conditioningIterations") != str(conditioning)
                         or not re.search(r"--conditioning="+str(conditioning)+r"(?:,|\})",options)):
        raise ValueError("Missing explicit every-operation conditioning controls")
    for option, expected in (("--warmup", inputs["Warmups"]), ("--measure", inputs["Measurements"]),
                             ("--iteration-ms", 1000)):
        if not re.search(re.escape(option) + "=" + str(expected) + r"(?:,|\})", options):
            raise ValueError("Every-operation timing controls differ from the protocol")
    with (worker / "iterations.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if (len(rows) != inputs["Warmups"] + conditioning + inputs["Measurements"]
            or sum(r["phase"] == "WARMUP" for r in rows) != inputs["Warmups"]):
        raise ValueError("Incomplete warmup/measurement iteration evidence")
    for phase, expected in (("WARMUP", inputs["Warmups"]),("CONDITIONING",conditioning), ("MEASUREMENT", inputs["Measurements"])):
        if [int(r["iteration"]) for r in rows if r["phase"] == phase] != list(range(1, expected + 1)):
            raise ValueError("Missing or repeated worker iteration")
    if any(int(r["endNs"]) - int(r["startNs"]) < 1_000_000_000 or int(r["operations"]) <= 0 for r in rows):
        raise ValueError("Incomplete one-second worker interval")
    if conditioning:
        from tailcache12_analysis import histogram
        phases=[r["phase"] for r in rows]
        if phases != ["WARMUP"]*inputs["Warmups"]+["CONDITIONING"]*conditioning+["MEASUREMENT"]*inputs["Measurements"]:
            raise ValueError("Shifted conditioning/analysis phases")
        for row in rows:
            if row["phase"]=="CONDITIONING":
                for channel in ("service","completion-gap"):
                    histogram(worker/"conditioning"/f"iteration-{row['iteration']}-{channel}-bins.csv",int(row["operations"]))
                if (int(row["churnDroppedBytes"]) != 0 or int(row["churnJvmAllocatedBytes"])<int(row["churnPayloadBytes"])
                        or not math.isfinite(float(row["churnPayloadBytesPerSecond"]))
                        or abs(float(row["churnPayloadBytesPerSecond"])-inputs["ChurnBytesPerSecond"])>
                           max(1,inputs["ChurnBytesPerSecond"]*.1)):
                    raise ValueError("Invalid conditioning churn demand")
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
                  jdkVersion=configuration["jdkVersion"], vmName=configuration.get("vmName"),
                  vmVersion=configuration.get("vmVersion"), javaRuntimeVersion=configuration.get("javaRuntimeVersion"),
                  accepted=not reasons)
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


def jmh_fork_summary(raw, kind, inputs, expected_trace, runtime_identity, occupancy_band=None,
                     diagnostic_compiler_xml=False):
    """One invocation must contain exactly one condition and one fresh worker JVM."""
    raw = pathlib.Path(raw)
    records = json.loads((raw / kind / "results.json").read_text())
    if len(records) != 1:
        raise ValueError("Expected exactly one JMH condition")
    record = records[0]
    if diagnostic_compiler_xml and (kind not in ("sample-calibration","floor") or "-XX:+LogCompilation" not in record["jvmArgs"]):
        raise ValueError("XML attribution is restricted to explicitly instrumented logged SampleTime diagnostics")
    method = "freshSupplyFloor" if kind == "floor" else "mixedWorkload"
    if record.get("benchmark") != "io.github.enixes.tailcache.benchmark.CrossoverBenchmark." + method:
        raise ValueError("JMH method differs from the declared channel")
    if record.get("jmhVersion") != "1.37":
        raise ValueError("Histogram semantics require the qualified JMH 1.37 build")
    for field in ("jmhVersion", "jdkVersion", "vmName", "vmVersion"):
        if field not in runtime_identity or record.get(field) != runtime_identity[field]:
            raise ValueError("Runtime identity differs from the frozen protocol")
    secondaries = set(record.get("secondaryMetrics", {}))
    allowed_secondaries = JMH_SAMPLE_SECONDARIES if kind != "throughput" else set()
    if kind in ("sample", "sample-calibration", "throughput", "floor") and (secondaries - allowed_secondaries
            or ("-XX:+LogCompilation" in record["jvmArgs"] and not diagnostic_compiler_xml)):
        raise ValueError("A profiled fork cannot supply an unprofiled endpoint")
    if record["forks"] != 1 or record["threads"] != 1:
        raise ValueError("Per-fork analysis requires one fresh single-worker JVM")
    fields = {"backend": "Backend", "payloadBytes": "Payload", "residentEntries": "Residents",
              "applicationLiveBytes": "LiveBytes", "churnBytesPerSecond": "ChurnBytesPerSecond", "seed": "Seed"}
    if any(str(record["params"][field]) != str(inputs[prop]) for field, prop in fields.items()):
        raise ValueError("JMH condition inputs differ from the protocol")
    conditioning=inputs.get("Conditioning",0)
    if type(conditioning) is not int or not 0<=conditioning<=64:
        raise ValueError("Invalid conditioning controls")
    if conditioning and f"-Dtailcache12.conditioningIterations={conditioning}" not in record["jvmArgs"]:
        raise ValueError("Missing explicit JMH conditioning control")
    if (record["warmupIterations"] != inputs["Warmups"]
            or record["measurementIterations"] != inputs["Measurements"]+conditioning
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
    validate_lifecycle_preparation(inputs,text,record['jvmArgs'])
    if f"traceSha256={expected_trace}" not in text or f"valueGenerator={VALUE_GENERATOR}" not in text:
        raise ValueError("Missing or mismatched workload fingerprint")
    if inputs.get("TransportWarmupVersion") not in (None,"none"):
        version=inputs["TransportWarmupVersion"]
        frames={"jmh-result-transport-v1":256,"jmh-result-transport-v2":1024}.get(version)
        prepared=re.search(r"transportWarmupVersion="+re.escape(version)+r" transportWarmupFrames="+str(frames)+r" transportWarmupBytes=(\d+)",text)
        if (frames is None or not prepared or int(prepared[1])<=0
                or f"-Dtailcache12.transportWarmupVersion={version}" not in record["jvmArgs"]):
            raise ValueError("Missing or mismatched actual transport preparation evidence")
    if "[TailCache12][integrity]" not in text:
        raise ValueError("Missing post-trial integrity verification")
    sidecars = list((raw / kind).glob("iterations-*.csv"))
    if len(sidecars) != 1:
        raise ValueError("Expected one worker sidecar")
    with sidecars[0].open(newline="") as stream:
        all_rows=list(csv.DictReader(stream))
    rows = [r for r in all_rows if r["phase"] == "MEASUREMENT"]
    conditioned=[r for r in all_rows if r["phase"]=="CONDITIONING"]
    if len(conditioned)!=conditioning:
        raise ValueError("Missing or unexpected JMH conditioning rows")
    if conditioning:
        if ([r["phase"] for r in all_rows] != ["WARMUP"]*inputs["Warmups"]+
                ["CONDITIONING"]*conditioning+["MEASUREMENT"]*inputs["Measurements"]
                or f"conditioningIterations={conditioning}" not in text):
            raise ValueError("Shifted or undeclared JMH conditioning phases")
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
    if conditioned and any(int(r["operations"])<=0 or int(r["churnDroppedBytes"])!=0
            or int(r["churnJvmAllocatedBytes"])<int(r["churnPayloadBytes"])
            or not math.isfinite(float(r["churnPayloadBytesPerSecond"]))
            or abs(float(r["churnPayloadBytesPerSecond"])-inputs["ChurnBytesPerSecond"])>
                   max(1,inputs["ChurnBytesPerSecond"]*.1) for r in conditioned):
        reasons.append("invalid conditioning operations/churn demand")
    result = {"kind": kind, "inputs": {k: v for k, v in inputs.items() if k != "ConsoleFile"},
              "jdkVersion": record["jdkVersion"], "traceSha256": expected_trace,
              "operations": sum(operations), "iterationOperations": operations,
              "compilerPerIterationMs": compiler, "rejectionReasons": reasons}
    result["conditioningIterations"]=conditioning
    if diagnostic_compiler_xml:
        result.update(diagnosticCompilerXml=True,primaryEndpointUseAllowed=False)
    if kind in ("sample", "sample-calibration", "compiler", "floor"):
        if record["mode"] != "sample" or record["primaryMetric"]["scoreUnit"] != "ns/op":
            raise ValueError("Wrong latency mode/units")
        forks = record["primaryMetric"].get("rawDataHistogram", [])
        if len(forks) != 1:
            raise ValueError("Missing per-fork JMH histograms")
        if len(forks[0])!=conditioning+inputs["Measurements"]:
            raise ValueError("JMH raw histogram conditioning/measurement count differs")
        if conditioning:
            merged_histograms(forks[0],[int(r["operations"]) for r in conditioned+rows])
        result.update(merged_histograms(forks[0][conditioning:], operations))
        result["reportedJmhPercentiles"] = record["primaryMetric"]["scorePercentiles"]
        result["reportedJmhPercentilesIncludeConditioning"]=bool(conditioning)
        result["p999Adequate"] = result["sampleCount"] >= 100_000
        if not result["p999Adequate"] and kind != "compiler":
            reasons.append("fewer than 100000 retained observations for p99.9")
    elif kind in ("allocation", "throughput"):
        if record["mode"] != "thrpt" or record["primaryMetric"]["scoreUnit"] != "ops/s":
            raise ValueError("Wrong throughput mode/units")
        result["operationsPerSecond"] = record["primaryMetric"]["score"]
        if conditioning:
            raw_data=record["primaryMetric"]["rawData"]
            if len(raw_data)!=1 or len(raw_data[0])!=conditioning+inputs["Measurements"]:
                raise ValueError("Incomplete throughput conditioning/analysis evidence")
            result["reportedJmhOperationsPerSecondIncludingConditioning"]=result["operationsPerSecond"]
            result["operationsPerSecond"]=statistics.mean(raw_data[0][conditioning:])
        if kind == "allocation":
            metrics = record["secondaryMetrics"]
            required = ("gc.alloc.rate", "gc.alloc.rate.norm", "gc.count", "gc.time")
            if any(name not in metrics for name in required):
                raise ValueError("Missing allocation/GC profiler evidence")
            result["gcProfiler"] = {name: metrics[name] for name in required}
            if conditioning:
                result["reportedGcProfilerIncludingConditioning"]=result["gcProfiler"]
                result["gcProfilerAnalysisWindow"]={}
                vectors,zeros=allocation_profiler_vectors(metrics,conditioning+inputs['Measurements'],
                    (raw/kind/'jmh.txt').read_text(),record['jmhVersion'])
                result['gcProfilerPhysicalVectors']=vectors
                result['gcTimeZeroFilledIterations']=zeros
                result['gcTimeAlignmentVersion']='jmh-gc-time-indexed-v1'
                for name in required:
                    tail=vectors[name][conditioning:]
                    if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in tail):
                        raise ValueError("Invalid analysis-window allocation profiler values")
                    result["gcProfilerAnalysisWindow"][name]=sum(tail) if name in ("gc.count","gc.time") else statistics.mean(tail)
                result["gcProfiler"]={name:dict(score=result["gcProfilerAnalysisWindow"][name],
                    scoreUnit=metrics[name]["scoreUnit"],rawData=[vectors[name][conditioning:]],
                    derivedFromAnalysisWindows=True) for name in required}
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
        values=metric.get("rawData",[[]])[0]
        if len(values)!=conditioning+inputs["Measurements"]:
            raise ValueError("Incomplete broad compiler conditioning evidence")
        result["compilerTotalMs"] = sum(values[conditioning:]) if conditioning else metric["score"]
        result["reportedCompilerTotalIncludingConditioningMs"]=metric["score"]
        result["broadCompilerPerIterationMs"] = values[conditioning:]
        reasons.extend(compiler_rejection_reasons(result["compilerTotalMs"], result["broadCompilerPerIterationMs"],
                                                  inputs["Measurements"]))
    result["accepted"] = not reasons
    return result


def hierarchical_ratio(blocks, seed=24301, resamples=5000, confidence=0.95):
    """Paired fork ordinals within counterbalanced passes; two-level bootstrap."""
    if len(blocks) < 2 or any(len(block) < 3 for block in blocks):
        raise ValueError("Require two independent passes and three paired forks per pass")
    if any(a <= 0 or b <= 0 or not math.isfinite(a + b) for block in blocks for a, b in block):
        raise ValueError("Endpoints must be positive and finite")
    if resamples < 1000:
        raise ValueError("At least 1000 bootstrap replicates required")
    if not 0 < confidence < 1:
        raise ValueError("Confidence must be strictly between zero and one")
    tail = (1 - confidence) / 2
    if resamples * tail < 20:
        raise ValueError("At least twenty bootstrap draws per requested tail required")
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
    result = {"ratio": math.exp(statistics.median(math.log(r) for r in estimates)),
            "lower": draws[math.ceil(tail * resamples) - 1],
            "upper": draws[math.ceil((1 - tail) * resamples) - 1],
            "confidenceLevel": confidence,
            "blockRatios": estimates, "independentPasses": len(blocks),
            "pairedForksPerPass": [len(block) for block in blocks], "resamples": resamples,
            "method": "paired-fork hierarchical bootstrap, outer counterbalanced passes",
            "limits": "Two outer passes give coarse uncertainty. No operations/iterations are independent replicas."}
    if confidence == 0.95:
        result.update(lower95=result["lower"], upper95=result["upper"])
    return result


def between_operation_fraction(directory):
    """Quantization bounds on time outside service intervals, not pure observer CPU cost.

    This also includes genuine pauses between calls; it must not reject a pressure
    condition merely because the studied GC effect increased this fraction.
    """
    from tailcache12_analysis import histogram
    worker = pathlib.Path(directory) / "worker"
    config = (worker / "configuration.txt").read_text()
    if "histogramSignificantDigits=3\n" not in config:
        raise ValueError("HDR quantization bounds require the pinned three-digit recorder")
    with (worker / "iterations.csv").open(newline="") as stream:
        rows = [r for r in csv.DictReader(stream) if r["phase"] == "MEASUREMENT"]
    elapsed = service_lower = service_upper = operations = 0
    for row in rows:
        count = int(row["operations"])
        elapsed += int(row["endNs"]) - int(row["startNs"])
        operations += count
        for upper, n in histogram(worker / f"iteration-{row['iteration']}-service-bins.csv", count):
            width = 1 << max(0, int(upper).bit_length() - 11)
            if int(upper) % width != width - 1:
                raise ValueError("Histogram bin is not an HDR upper equivalent")
            service_lower += (upper - width + 1) * n
            service_upper += upper * n
    if operations <= 0 or elapsed <= 0 or service_lower > elapsed:
        raise ValueError("Service histograms cannot fit inside the recorded worker windows")
    return dict(lower=max(0, (elapsed - service_upper) / elapsed),
                upper=max(0, (elapsed - service_lower) / elapsed), operations=operations,
                interpretation="Wall time outside recorded service intervals; includes recorder/loop work and between-call pauses")


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
