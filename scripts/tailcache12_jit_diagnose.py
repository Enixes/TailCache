#!/usr/bin/env python3
"""Explain retained compiler screens; narrower evidence never overrides acceptance.

HotSpot task wall time is not compiler CPU time or JVM pause duration. XML stamp
alignment uses the retained GC uptime/nano clock anchors with a 1-ms uncertainty.
"""
import argparse
import csv
import hashlib
import json
import pathlib
import re
import statistics
import xml.etree.ElementTree as ET

from tailcache12_calibrate import verify_invocation


def classify_tasks(xml_path, gc_path, windows):
    if not windows or any(a >= b for a, b in windows):
        raise ValueError("Missing or invalid worker windows")
    anchors = [(int(ns) - int(ms) * 1_000_000)
               for ms, ns in re.findall(r"\[(\d+)ms\]\[(-?\d+)ns\]", gc_path.read_text())]
    if not anchors:
        raise ValueError("GC clock anchors are missing")
    origin = int(statistics.median(anchors))
    relative = [((a - origin) / 1e9, (b - origin) / 1e9) for a, b in windows]
    root = ET.parse(xml_path).getroot()
    tasks, incomplete = [], 0
    for task in root.iter("task"):
        done = task.find("task_done")
        if done is None or "stamp" not in task.attrib or "stamp" not in done.attrib:
            incomplete += 1
            continue
        start, end = float(task.attrib["stamp"]), float(done.attrib["stamp"])
        if end < start:
            raise ValueError("Compiler task ends before it starts")
        if any(end >= a - 0.001 and start <= b + 0.001 for a, b in relative):
            where = "possible-worker-overlap"
        elif start > max(b for _, b in relative) + 0.001:
            where = "after-worker-windows"
        else:
            where = "outside-worker-windows"
        tasks.append({"method": task.get("method"), "compileId": task.get("compile_id"),
                      "startSeconds": start, "endSeconds": end,
                      "taskWallMs": (end - start) * 1000, "location": where,
                      "success": done.get("success")})
    deoptimizations = [{"kind": tag, **node.attrib,
                        "frames": [dict(frame.attrib) for frame in node.iter("jvms")]}
                       for tag in ("deoptimized", "uncommon_trap", "make_not_entrant")
                       for node in root.iter(tag) if "stamp" in node.attrib]
    return {"jvmStartNanoEstimate": origin, "alignmentUncertaintyMs": 1,
            "workerWindowsSeconds": relative, "incompleteCompilerTasks": incomplete,
            "tasks": tasks, "deoptimizationEvents": deoptimizations}


def diagnose(attempt):
    manifest = json.loads((attempt / "manifest.json").read_text())
    if manifest["stage"] != "jit":
        raise ValueError("Expected a compiler-screen attempt")
    snapshot = attempt / "source.tar.gz"
    if hashlib.sha256(snapshot.read_bytes()).hexdigest() != manifest["sourceArchiveSha256"]:
        raise ValueError("Changed source snapshot")
    observations = []
    for invocation in manifest["invocations"]:
        raw = verify_invocation(attempt, invocation) / "compiler"
        record = json.loads((raw / "results.json").read_text())[0]
        metric = record["secondaryMetrics"]["compiler.time.profiled"]
        values = metric["rawData"][0]
        paths = {name: list(raw.glob(pattern)) for name, pattern in
                 (("xml", "jit-*.xml"), ("gc", "gc-*.log"), ("worker", "iterations-*.csv"))}
        if any(len(p) != 1 for p in paths.values()):
            raise ValueError("Expected one XML, GC log and worker sidecar per compiler fork")
        with paths["worker"][0].open(newline="") as stream:
            rows = [r for r in csv.DictReader(stream) if r["phase"] == "MEASUREMENT"]
        if len(rows) != 8 or len(values) != 8:
            raise ValueError("Incomplete compiler measurement evidence")
        windows = [(int(r["envelopeStartNs"]), int(r["envelopeEndNs"])) for r in rows]
        worker = [int(r["workerEnvelopeCompilerMs"]) for r in rows]
        details = classify_tasks(paths["xml"][0], paths["gc"][0], windows)
        observations.append({"label": invocation["label"], "parameters": record["params"],
                             "compilerTotalMs": metric["score"], "compilerPerIterationMs": values,
                             "workerEnvelopeCompilerMs": worker,
                             "jitPass": metric["score"] <= 80 and max(values) <= 10,
                             "topPossibleWorkerTasks": sorted(
                                 (t for t in details["tasks"] if t["location"] == "possible-worker-overlap"),
                                 key=lambda t: t["taskWallMs"], reverse=True)[:20],
                             "topAfterWorkerTasks": sorted(
                                 (t for t in details["tasks"] if t["location"] == "after-worker-windows"),
                                 key=lambda t: t["taskWallMs"], reverse=True)[:20],
                             "clockAlignmentUncertaintyMs": details["alignmentUncertaintyMs"],
                             "deoptimizationEvents": details["deoptimizationEvents"],
                             "incompleteCompilerTasks": details["incompleteCompilerTasks"]})
    return {"schemaVersion": "tailcache12-jit-diagnosis-v1", "reportable": False,
            "attempt": str(attempt), "gitHead": manifest["gitHead"],
            "sourceSha256": manifest["sourceSha256"],
            "diagnosticToolSha256": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
            "compilerLimits": {"totalMs": 80, "perIterationMs": 10},
            "observations": observations,
            "limits": ["Explanatory analysis does not override the compiler or host acceptance rule.",
                       "Task wall times cannot be summed as compiler CPU time or pause time.",
                       "XML/nano alignment has 1-ms uncertainty; overlap is deliberately labeled possible."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=pathlib.Path)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Refusing to overwrite a prior diagnosis")
    result = diagnose(args.attempt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    for row in result["observations"]:
        print(f"{row['label']}: total={row['compilerTotalMs']}ms "
              f"max={max(row['compilerPerIterationMs'])}ms workerMax={max(row['workerEnvelopeCompilerMs'])}ms "
              f"jitPass={row['jitPass']}")
    print(f"diagnosis={args.out}")


if __name__ == "__main__":
    main()
