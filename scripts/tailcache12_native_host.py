"""Native CPU accounting. A scope accounts benchmark descendants without affinity changes.

Keep cumulative counters in raw samples. CPU outside the scope is a conservative
upper bound, including clock-tick quantization and counter-read uncertainty.
"""
import functools
import json
import math
import os
import pathlib
import re
import time

VERSION = "tailcache12-native-cgroup-v2"
STRING_FIELDS = ("nativeCgroup", "nativeScopeName", "nativeCpuCounter", "nativeControls",
                 "nativeTemperatures", "nativeThrottleCounts", "nativeBootId", "nativeKernelRelease")
ENVIRONMENT_FIELDS = ("nativeCgroup", "nativeScopeName", "nativeCpuCounter", "nativeControls",
                      "nativeObserverVersion", "nativeLogicalCpus", "nativeAffinityCpus",
                      "nativeClockTicksPerSecond", "nativeBootId", "nativeKernelRelease",
                      "governor", "externalPower", "memTotalKiB")
CPU_LIMIT_PERCENT = 10


def process_cgroup(text):
    matches = [line[3:] for line in text.splitlines() if line.startswith("0::/")]
    if len(matches) != 1 or ".." in pathlib.PurePosixPath(matches[0]).parts:
        raise ValueError("Expected one absolute cgroup-v2 membership")
    return matches[0]


@functools.lru_cache(maxsize=1)
def sensors():
    thermal = sorted(pathlib.Path("/sys/devices/system/cpu").glob("cpu*/thermal_throttle/*throttle_count"))
    temperatures = sorted(pathlib.Path("/sys/class/hwmon").glob("hwmon*/temp*_input"))
    frequencies = sorted(pathlib.Path("/sys/devices/system/cpu/cpufreq").glob("policy*/scaling_cur_freq"))
    return thermal, temperatures, frequencies


def read_controls(group):
    controls = {}
    path = pathlib.Path("/sys/fs/cgroup") / group.lstrip("/")
    root = pathlib.Path("/sys/fs/cgroup")
    while path.is_relative_to(root):
        for name in ("cpu.max", "cpu.weight", "cpuset.cpus.effective", "memory.max"):
            file = path / name
            if file.exists():
                controls[str(file.relative_to(root))] = file.read_text().strip()
            elif name in ("cpu.max", "memory.max"):
                # A controller disabled at this level cannot impose a local limit.
                # Ancestor limits still apply and are retained independently.
                controls[str(file.relative_to(root))] = "not-enabled"
        if path == root:
            break
        path = path.parent
    return controls


def snapshot():
    start = time.monotonic_ns()
    lines = pathlib.Path("/proc/stat").read_text().splitlines()
    counters = [int(x) for x in lines[0].split()[1:9]]
    if len(counters) != 8:
        raise ValueError("Incomplete aggregate CPU counters")
    cpus = sum(bool(re.match(r"^cpu\d+\s", line)) for line in lines)
    group = process_cgroup(pathlib.Path("/proc/self/cgroup").read_text())
    scope = os.environ.get("TAILCACHE_NATIVE_SCOPE", "unavailable")
    qualified = bool(re.fullmatch(r"tailcache12-[A-Za-z0-9._-]+\.scope", scope)
                     and group.endswith("/" + scope))
    usage = dict(line.split() for line in
                 (pathlib.Path("/sys/fs/cgroup") / group.lstrip("/") / "cpu.stat").read_text().splitlines())
    end = time.monotonic_ns()
    thermal, temperatures, frequencies = sensors()
    def optional_int(path):
        try:
            return int(path.read_text())
        except (OSError, ValueError):
            return None
    throttle = {str(p): optional_int(p) for p in thermal}
    temps = {str(p): dict(milliC=optional_int(p), criticalMilliC=optional_int(
        p.with_name(p.name.replace("_input", "_crit")))) for p in temperatures}
    freq = [value for p in frequencies if (value := optional_int(p)) is not None]
    pressure = pathlib.Path("/proc/pressure/cpu").read_text()
    load = [float(x) for x in pathlib.Path("/proc/loadavg").read_text().split()[:3]]
    hz = os.sysconf("SC_CLK_TCK")
    result = dict(nativeObserverVersion=2, nativeCgroup=group, nativeScopeName=scope,
                nativeScopeQualified=int(qualified), nativeCpuCounter="proc-stat-minus-cgroup-v2",
                nativeSampleStartNs=start, nativeSampleEndNs=end, nativeLogicalCpus=cpus,
                nativeClockTicksPerSecond=hz, nativeCpuTotalTicks=sum(counters),
                nativeCpuBusyTicks=sum(counters[i] for i in (0, 1, 2, 5, 6)),
                nativeCpuStealTicks=counters[7], nativeScopeUsageUs=int(usage["usage_usec"]),
                nativeAffinityCpus=len(os.sched_getaffinity(0)),
                nativeControls=json.dumps(read_controls(group), sort_keys=True),
                nativeTemperatures=json.dumps(temps, sort_keys=True),
                nativeThrottleCounts=json.dumps(throttle, sort_keys=True),
                nativeFrequencyMinKHz=min(freq, default=-1), nativeFrequencyMaxKHz=max(freq, default=-1),
                nativeCpuSomeTotalUs=int(re.search(r"^some .*total=(\d+)", pressure, re.M).group(1)),
                nativeCpuSomeAvg10=float(re.search(r"^some avg10=([\d.]+)", pressure, re.M).group(1)),
                nativeLoad1=load[0], nativeLoad5=load[1], nativeLoad15=load[2])
    result["nativeObserverReadDurationNs"] = time.monotonic_ns() - start
    result["nativeBootId"] = pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    result["nativeKernelRelease"] = pathlib.Path("/proc/sys/kernel/osrelease").read_text().strip()
    return result


def environment_declaration(sample):
    return {key: sample[key] for key in ENVIRONMENT_FIELDS}


def environment_reasons(rows, declaration):
    if set(declaration) != set(ENVIRONMENT_FIELDS):
        return ["Missing declared native host environment"]
    return [("external power is disconnected" if key == "externalPower"
             and any("=0" in row.get(key, "") for row in rows)
             else "externalPower changed during block" if key == "externalPower"
             else "Declared native " + key + " changed during/between blocks") for key in ENVIRONMENT_FIELDS
            if any(row.get(key) != declaration[key] for row in rows)]


def normalized_environment(declaration):
    """A different temporary scope name does not mean different hardware controls."""
    result = dict(declaration)
    group, scope = result.pop("nativeCgroup"), result.pop("nativeScopeName")
    controls = json.loads(result.pop("nativeControls"))
    result["resourceControls"] = {key.replace(group.lstrip("/"), "<benchmark-scope>"): value
                                   for key, value in controls.items()}
    return result


def cpu_intervals(rows):
    """Return replayable interval bounds; invalid accounting is never clamped away."""
    versions = {r["nativeObserverVersion"] for r in rows}
    if versions not in ({1}, {2}):
        raise ValueError("Unknown or mixed native observer versions")
    if versions == {2}:
        # Check every raw increment before merging a short final fragment.
        for before, after in zip(rows, rows[1:]):
            span = (after["nativeSampleEndNs"] - before["nativeSampleStartNs"]) / 1e9
            if (not 0 < span <= 2.5 or after["nativeSampleStartNs"] <= before["nativeSampleEndNs"]
                    or any(after[k] < before[k] for k in
                           ("nativeCpuTotalTicks", "nativeCpuBusyTicks", "nativeScopeUsageUs"))):
                raise ValueError("Invalid or stale native CPU accounting interval")
            read_ns = after["nativeSampleEndNs"] - after["nativeSampleStartNs"]
            if not 0 <= read_ns <= 50_000_000:
                raise ValueError("Invalid native CPU counter-read bracket")
        if (len(rows) >= 3 and
                rows[-1]["nativeSampleEndNs"] - rows[-2]["nativeSampleStartNs"] < 800_000_000):
            rows = [*rows[:-2], rows[-1]]
    result = []
    for before, after in zip(rows, rows[1:]):
        cpus, hz = after["nativeLogicalCpus"], after["nativeClockTicksPerSecond"]
        start, end = before["nativeSampleStartNs"], after["nativeSampleEndNs"]
        elapsed_us = (end - start) / 1000
        ticks = after["nativeCpuTotalTicks"] - before["nativeCpuTotalTicks"]
        busy = after["nativeCpuBusyTicks"] - before["nativeCpuBusyTicks"]
        scope = after["nativeScopeUsageUs"] - before["nativeScopeUsageUs"]
        read_us = ((before["nativeSampleEndNs"] - before["nativeSampleStartNs"])
                   + (after["nativeSampleEndNs"] - after["nativeSampleStartNs"])) / 1000
        if (cpus <= 0 or hz <= 0 or elapsed_us <= 0 or elapsed_us > 2_500_000
                or after["nativeSampleStartNs"] <= before["nativeSampleEndNs"]
                or ticks <= 0 or not 0 <= busy <= ticks or scope < 0
                or read_us < 0 or read_us > 100_000):
            raise ValueError("Invalid or stale native CPU accounting interval")
        capacity = ticks * 1_000_000 / hz
        uncertainty = 2 * cpus * 1_000_000 / hz + read_us * cpus
        if (abs(capacity - elapsed_us * cpus) > uncertainty + elapsed_us * cpus * 0.05
                or scope > busy * 1_000_000 / hz + uncertainty):
            raise ValueError("Native CPU accounting sources disagree")
        outside_us = max(0, busy * 1_000_000 / hz - scope)
        result.append(dict(startNs=start, endNs=end,
                           outsidePercent=100 * outside_us / capacity,
                           outsideUpperPercent=100 * (outside_us + uncertainty) / capacity))
    return result


def gate(rows, windows=None, expected_version=None):
    required = ("nativeObserverVersion", "nativeScopeQualified", "nativeSampleStartNs", "nativeSampleEndNs",
                "nativeLogicalCpus", "nativeClockTicksPerSecond", "nativeCpuTotalTicks", "nativeCpuBusyTicks",
                "nativeCpuStealTicks", "nativeScopeUsageUs", "nativeAffinityCpus")
    try:
        if len(rows) < 2 or any(any(k not in r or not math.isfinite(r[k]) for k in required) for r in rows):
            raise ValueError("Missing or invalid native CPU observations")
        versions = {r["nativeObserverVersion"] for r in rows}
        if (versions not in ({1}, {2}) or (expected_version is not None and versions != {expected_version})
                or any(r["nativeScopeQualified"] != 1 for r in rows)):
            raise ValueError("Native observer requires an isolated benchmark scope")
        if any(int(r[k]) != r[k] or r[k] < 0 for r in rows for k in required):
            raise ValueError("Native CPU counters must be nonnegative integers")
        for key in ("nativeCgroup", "nativeScopeName", "nativeCpuCounter", "nativeControls",
                    "nativeLogicalCpus", "nativeClockTicksPerSecond", "nativeAffinityCpus"):
            if len({r[key] for r in rows}) != 1:
                raise ValueError("Native accounting identity or resource controls changed")
        scope = rows[0]["nativeScopeName"]
        if (not re.fullmatch(r"tailcache12-[A-Za-z0-9._-]+\.scope", scope)
                or not rows[0]["nativeCgroup"].endswith("/" + scope)
                or rows[0]["nativeCpuCounter"] != "proc-stat-minus-cgroup-v2"):
            raise ValueError("Invalid native scope or CPU-counter identity")
        if any(r["nativeAffinityCpus"] != r["nativeLogicalCpus"] for r in rows):
            raise ValueError("Native benchmark CPU affinity is restricted")
        if any(r["nativeCpuStealTicks"] != rows[0]["nativeCpuStealTicks"] for r in rows):
            raise ValueError("Native CPU steal counter increased")
        if min(r["memAvailableKiB"] for r in rows) < 1024**2:
            raise ValueError("Native available memory fell below 1 GiB")
        controls = json.loads(rows[0]["nativeControls"])
        prefix = rows[0]["nativeCgroup"].lstrip("/") + "/"
        if (not isinstance(controls, dict) or prefix + "cpu.max" not in controls
                or prefix + "memory.max" not in controls):
            raise ValueError("Missing native scope resource controls")
        if any(v.split()[0] not in ("max", "not-enabled") for k, v in controls.items()
                               if k.endswith(("cpu.max", "memory.max"))):
            raise ValueError("Native benchmark has a CPU or memory resource limit")
        for row in rows:
            if row["nativeSampleEndNs"] < row["nativeSampleStartNs"]:
                raise ValueError("Invalid native sample bracket")
            if versions == {2} and row["nativeSampleEndNs"] - row["nativeSampleStartNs"] > 50_000_000:
                raise ValueError("Invalid native CPU counter-read bracket")
            for sensor in json.loads(row["nativeTemperatures"]).values():
                if sensor["milliC"] is not None and sensor["criticalMilliC"] is not None:
                    if sensor["milliC"] >= sensor["criticalMilliC"]:
                        raise ValueError("Native temperature reached its critical limit")
        throttle = [json.loads(r["nativeThrottleCounts"]) for r in rows]
        if any(set(t) != set(throttle[0]) for t in throttle):
            raise ValueError("Native thermal-throttle sensor set changed")
        for key, first in throttle[0].items():
            values = [t[key] for t in throttle]
            if first is None or any(v is None or v < first for v in values):
                raise ValueError("Native thermal-throttle counter unavailable or reset")
            if max(values) > first:
                raise ValueError("Native thermal-throttle counter increased")
        intervals = cpu_intervals(rows)
        selected = [r for r in intervals if not windows or any(
            r["endNs"] >= a - 10_000_000_000 and r["startNs"] <= b for a, b in windows)]
        if len(selected) < (2 if windows else 1):
            raise ValueError("Missing native CPU settling/measurement coverage")
        if windows and (intervals[0]["startNs"] > min(a for a, _ in windows)
                        or intervals[-1]["endNs"] < max(b for _, b in windows)):
            raise ValueError("Incomplete native CPU settling/measurement coverage")
        if max(r["outsideUpperPercent"] for r in selected) > CPU_LIMIT_PERCENT:
            raise ValueError("Native CPU outside benchmark scope exceeded 10% upper bound")
        return []
    except (KeyError, ValueError, TypeError, AttributeError, json.JSONDecodeError) as error:
        return [str(error)]


def worker_reasons(directory, rows, require_allocation=False):
    """Check the actual JVM's membership, not only the controller's environment."""
    files = list(pathlib.Path(directory).rglob("worker-process-*.properties"))
    if not files:
        return ["Missing native worker cgroup evidence"]
    expected = {r.get("nativeCgroup") for r in rows}
    try:
        for file in files:
            values = dict(line.split("=", 1) for line in file.read_text().splitlines() if "=" in line)
            if {values["cgroup"]} != expected or int(values["pid"]) <= 0:
                return ["Native worker escaped the benchmark accounting scope"]
            if require_allocation:
                if values.get("workerAllocationCounters") != "true":
                    return ["Missing worker allocation counter capability evidence"]
                backend, mode, payload = values["backend"], values["mode"], int(values["payloadBytes"])
                if backend not in ("CAFFEINE", "CHRONICLE_IN_MEMORY") or mode not in (
                        "workload", "supply-floor", "timer", "retention") or not 16 <= payload <= 32768:
                    return ["Invalid worker allocation-demand metadata"]
                if mode != "retention":
                    sidecar = file.parent / ("iterations-" + values["pid"] + ".csv")
                    if not sidecar.exists():
                        sidecar = file.parent / "iterations.csv"
                    import csv
                    with sidecar.open(newline="") as stream:
                        measured = [r for r in csv.DictReader(stream) if r["phase"] == "MEASUREMENT"]
                    if not measured:
                        return ["Missing worker allocation intervals"]
                    for row in measured:
                        operations, writes = int(row["operations"]), int(row["writes"])
                        allocated = int(row["workerJvmAllocatedBytes"])
                        demand = (operations if mode == "workload" and backend == "CHRONICLE_IN_MEMORY"
                                  else writes if mode != "timer" else 0) * payload
                        if not 0 <= writes <= operations or allocated < demand or allocated < 0:
                            return ["Worker allocation is below mandatory fresh-payload/materialization demand"]
        records = list(pathlib.Path(directory).glob("*/results.json"))
        if records:
            expected_count = sum(int(r["forks"]) for path in records for r in json.loads(path.read_text()))
            if len(files) != expected_count:
                return ["Incomplete native worker cgroup evidence"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        return ["Invalid native worker cgroup evidence: " + str(error)]
    return []
