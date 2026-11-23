#!/usr/bin/env python3
"""
Focused high-occupancy (88% -> 98%+ / OOM boundary) diagnostic runner.
Tests Caffeine vs Chronicle get() vs Chronicle getUsing() across the G1GC heap cliff.
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import time

SCRATCH = pathlib.Path(__file__).resolve().parent
OUT_DIR = SCRATCH.parent / "evidence-archives/native-final-cliff-crossover-diagnostic-20261108-001"
OUT_DIR.mkdir(parents=True, exist_ok=True)

JAVA = "/usr/lib/jvm/java-21-openjdk/bin/java"
GRADLE_CACHE = pathlib.Path(os.environ.get("GRADLE_USER_HOME", pathlib.Path.home() / ".gradle"))
MODULES_DIR = GRADLE_CACHE / "caches/modules-2/files-2.1"
ALL_JARS = [
    str(p) for p in sorted(MODULES_DIR.rglob("*.jar"))
    if not p.name.endswith("-sources.jar") and not p.name.endswith("-javadoc.jar")
]
CP = ":".join([
    str(SCRATCH),
    str(SCRATCH.parent / "build/classes/java/main"),
    *ALL_JARS,
])

JVM_EXPORTS = [
    "-Dchronicle.analytics.disable=true",
    "-Dtailcache12.lifecycleWarmupVersion=lifecycle-maintenance-v1",
    "--add-exports=java.base/jdk.internal.misc=ALL-UNNAMED",
    "--add-exports=java.base/jdk.internal.ref=ALL-UNNAMED",
    "--add-exports=java.base/jdk.internal.util=ALL-UNNAMED",
    "--add-exports=java.base/sun.nio.ch=ALL-UNNAMED",
    "--add-exports=jdk.compiler/com.sun.tools.javac.file=ALL-UNNAMED",
    "--add-exports=jdk.unsupported/sun.misc=ALL-UNNAMED",
    "--add-opens=java.base/java.io=ALL-UNNAMED",
    "--add-opens=java.base/java.lang=ALL-UNNAMED",
    "--add-opens=java.base/java.lang.reflect=ALL-UNNAMED",
    "--add-opens=java.base/java.util=ALL-UNNAMED",
    "--add-opens=jdk.compiler/com.sun.tools.javac=ALL-UNNAMED",
]


def parse_gc_log(gc_log_path: pathlib.Path, heap_mib: int):
    if not gc_log_path.exists():
        return {}
    post_gc_mib = []
    pauses_ms = []
    to_space_exhausted = 0
    full_gcs = 0
    for line in gc_log_path.read_text(errors="replace").splitlines():
        if "To-space exhausted" in line:
            to_space_exhausted += 1
        if "Pause Full" in line and line.endswith("ms"):
            full_gcs += 1
        m = re.search(r"Pause (?:Young|Full) .*? (\d+)M->(\d+)M\((\d+)M\) ([0-9.]+)ms", line)
        if m:
            after_m = int(m.group(2))
            pause_ms = float(m.group(4))
            post_gc_mib.append(after_m)
            pauses_ms.append(pause_ms)
    if not post_gc_mib:
        return {"postGcMedianPct": None, "postGcMaxPct": None, "loggedPauses": 0, "maxPauseMs": 0.0,
                "toSpaceExhausted": to_space_exhausted, "fullGcs": full_gcs}
    s = sorted(post_gc_mib)
    med_mib = s[len(s) // 2]
    max_mib = max(s)
    return {
        "postGcMedianPct": round(med_mib * 100.0 / heap_mib, 1),
        "postGcMaxPct": round(max_mib * 100.0 / heap_mib, 1),
        "loggedPauses": len(pauses_ms),
        "maxPauseMs": round(max(pauses_ms), 2),
        "toSpaceExhausted": to_space_exhausted,
        "fullGcs": full_gcs,
    }


def run_one(tag: str, mode: str, heap_mib: int, payload: int, live_mib: int,
            churn_mib: int = 32, warmups: int = 8, measurements: int = 8, target_qps: int = 100000):
    json_out = OUT_DIR / f"{tag}.json"
    gc_log = OUT_DIR / f"{tag}.gc.log"
    if json_out.exists():
        json_out.unlink()
    if gc_log.exists():
        gc_log.unlink()

    cmd = [
        JAVA,
        *JVM_EXPORTS,
        "-XX:+UseG1GC",
        f"-Xms{heap_mib}m",
        f"-Xmx{heap_mib}m",
        f"-Xlog:gc*,safepoint:file={gc_log}:uptimemillis,timenanos,level,tags:filecount=0",
        "-cp", CP,
        "TailCache12CliffCrossoverProbe",
        "--mode", mode,
        "--residents", "32768",
        "--payload", str(payload),
        "--live-mib", str(live_mib),
        "--churn-mib-sec", str(churn_mib),
        "--warmups", str(warmups),
        "--measurements", str(measurements),
        "--target-qps", str(target_qps),
        "--out", str(json_out),
    ]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    elapsed = time.time() - t0
    gc_info = parse_gc_log(gc_log, heap_mib)

    if proc.returncode != 0 or not json_out.exists():
        oom = "OutOfMemoryError" in (proc.stderr or "") or "OutOfMemoryError" in (proc.stdout or "")
        return {
            "tag": tag,
            "mode": mode,
            "heapMiB": heap_mib,
            "payloadBytes": payload,
            "liveMiB": live_mib,
            "status": "OOM" if oom else f"FAIL({proc.returncode})",
            "wallSec": round(elapsed, 1),
            "stderrTail": (proc.stderr or "")[-300:],
            **gc_info,
        }

    data = json.loads(json_out.read_text())
    data.update({
        "tag": tag,
        "heapMiB": heap_mib,
        "status": "OK",
        "wallSec": round(elapsed, 1),
        **gc_info,
    })
    return data


def main():
    modes = ["CAFFEINE", "CHRONICLE_GET", "CHRONICLE_GET_USING"]
    schedule = []

    # Sweep 1: 4 KiB payloads, 512 MiB heap, stepping live ballast from 288 MiB -> 352 MiB
    # (Caffeine post-GC occupancy goes ~90% -> 94% -> 96% -> 98% -> OOM)
    for live in [288, 312, 328, 340, 352]:
        for m in modes:
            schedule.append((f"p4096_live{live}_{m}", m, 512, 4096, live, 32, 8, 8, 50000))

    # Sweep 2: 256 B payloads, 256 MiB heap, stepping live ballast from 192 MiB -> 244 MiB
    # (Pushes 256 B into the actual 83% -> 98% occupancy zone that Task 12 never reached)
    for live in [192, 220, 232, 238, 244]:
        for m in modes:
            schedule.append((f"p256_h256_live{live}_{m}", m, 256, 256, live, 32, 6, 6, 100000))

    existing = {}
    summary_file = OUT_DIR / "summary.json"
    if summary_file.exists():
        for r in json.loads(summary_file.read_text()):
            if r.get("status") == "OK":
                existing[r["tag"]] = r

    results = []
    print(f"Running {len(schedule)} cliff diagnostic JVMs...")
    for idx, (tag, mode, heap, payload, live, churn, w, meas, qps) in enumerate(schedule, 1):
        if tag in existing:
            res = existing[tag]
            print(f"[{idx:02d}/{len(schedule):02d}] {tag} (CACHED) -> postGC={res.get('postGcMedianPct')}% "
                  f"gcTime={res.get('gcTimeMs')}ms closedP99.9={res.get('closedLoopSvcP999Us')}us "
                  f"openLoopP99.9={res.get('openLoopRespP999Us')}us", flush=True)
            results.append(res)
            continue
        print(f"[{idx:02d}/{len(schedule):02d}] {tag} ...", flush=True)
        res = run_one(tag, mode, heap, payload, live, churn, w, meas, qps)
        results.append(res)
        status = res.get("status")
        occ = res.get("postGcMedianPct")
        svc999 = res.get("closedLoopSvcP999Us")
        ol999 = res.get("openLoopRespP999Us")
        gc_ms = res.get("gcTimeMs")
        fulls = res.get("fullGcs")
        print(f"    -> status={status} postGC={occ}% gcTime={gc_ms}ms (fullGCs={fulls}) "
              f"closedP99.9={svc999}us openLoopP99.9={ol999}us", flush=True)
        summary_file.write_text(json.dumps(results, indent=2))

    print("All runs finished.")


if __name__ == "__main__":
    main()
