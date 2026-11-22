#!/usr/bin/env python3
"""Audit timed operations, G1 aging, and the transition stall from retained forks."""

import argparse
import csv
import hashlib
import io
import json
import re
import statistics
import sys
import tarfile
from collections import defaultdict
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def archived_slots(directory, bundle, count, inputs):
    archive_path = directory / bundle["file"]
    if digest(archive_path.read_bytes()) != bundle["sha256"]:
        raise ValueError(f"Archive checksum differs: {archive_path}")
    slots = defaultdict(dict)
    with tarfile.open(archive_path, "r|xz") as archive:
        for member in archive:
            parts = member.name.split("/", 3)
            if not member.isfile() or len(parts) != 4 or parts[:2] != ["research", "slots"]:
                continue
            _, _, label, name = parts
            if name in inputs or name == "result.json":
                slots[label][name] = archive.extractfile(member).read()
    if len(slots) != count:
        raise ValueError(f"Expected {count} first-pass slots in {archive_path}, found {len(slots)}")
    for label, files in sorted(slots.items()):
        result = json.loads(files["result.json"])
        if result["status"] != "COMPLETE" or result["spec"]["label"] != label:
            raise ValueError(f"Incomplete or mislabelled slot: {label}")
        for name in inputs:
            if digest(files[name]) != result["rawSha256"][name]:
                raise ValueError(f"Raw digest differs: {label}/{name}")
        yield result, files


def slot_info(result):
    fields = ("label", "seed", "block", "backend", "payloadBytes", "liveMiB",
              "writeBps", "updateHotset")
    return {key: result["spec"][key] for key in fields} | {"warnings": result["warnings"]}


def measurement(result):
    window, = (window for window in result["windows"] if window["phase"] == "MEASUREMENT")
    return window


def csv_rows(data):
    return csv.DictReader(io.StringIO(data.decode()))


def latency(result, channel, quantile):
    return result["latency"][channel]["percentiles"][quantile]["ns"]


def saturated(result, files):
    channels = ("service", "read-service", "update-service")
    quantiles = ("50", "99", "99.9")
    counts = {}
    for channel in channels[1:]:
        rows = csv_rows(files[f"worker/{channel}-bins.csv"])
        bins = [(int(row["upperEquivalentNs"]), int(row["count"])) for row in rows]
        if sum(count for _, count in bins) != result["latency"][channel]["count"]:
            raise ValueError(f"Histogram count differs for {result['spec']['label']} {channel}")
        counts[channel] = {
            q: sum(count for upper, count in bins if upper > latency(result, "service", q))
            for q in quantiles[1:]
        }
    window = measurement(result)
    return slot_info(result) | {
        "percentilesNs": {channel: {q: latency(result, channel, q) for q in quantiles}
                          for channel in channels},
        "countsInBinsStrictlyAboveCombinedPercentile": counts,
        "churnDeliveredBytes": int(window["churnPayloadBytes"]),
        "churnDroppedBytes": int(window["churnDroppedBytes"]),
    }


AGE_ENTRY = re.compile(r"\[(-?\d+)ns\].*GC\((\d+)\) (.*)")
SURVIVOR_TARGET = re.compile(r"Desired survivor size (\d+) bytes, new threshold (\d+)")
AGE_ONE = re.compile(r"- age\s+1:\s+(\d+) bytes")


def ages(result, data):
    window = measurement(result)
    begin, end = int(window["startNs"]), int(window["endNs"])
    targets, age_one_bytes = {}, {}
    for line in data.decode().splitlines():
        event = AGE_ENTRY.search(line)
        if not event:
            continue
        stamp, collection, message = event.groups()
        if not begin <= int(stamp) <= end:
            continue
        target = SURVIVOR_TARGET.match(message)
        if target:
            size, threshold = map(int, target.groups())
            targets[collection] = (size, threshold)
        entry = AGE_ONE.match(message)
        if entry:
            age_one_bytes[collection] = int(entry[1])
    if not targets:
        raise ValueError(f"No in-window survivor targets for {result['spec']['label']}")
    mixed_ns = sum(pause["overlapNs"] for pause in result["gc"]["pauses"]
                   if pause["kind"].startswith("Pause Young (Mixed)"))
    return slot_info(result) | {
        "collectionCountWithAgeThreshold": len(targets),
        "tenuringThresholds": sorted({threshold for _, threshold in targets.values()}),
        "medianDesiredSurvivorBytes": statistics.median(size for size, _ in targets.values()),
        "medianAgeOneBytes": statistics.median(age_one_bytes.get(key, 0) for key in targets),
        "mixedPauseOverlapNs": mixed_ns,
        "totalPauseOverlapMs": result["gc"]["pauseOverlapMs"],
    }


SAFEPOINT = re.compile(r'\[(-?\d+)ns\][^\n]*Safepoint "[^"]+",[^\n]*Total: (\d+) ns')


def transition(slots):
    observations = []
    stalls = []
    for result, files in slots:
        info = slot_info(result)
        observations.append(ages(result, files["age.log"]) | {
            "responseP999Ns": latency(result, "response", "99.9"),
        })
        if info["backend"] != "CHRONICLE_IN_MEMORY" or info["writeBps"] != 125:
            continue
        events = list(csv_rows(files["worker/stalls.csv"]))
        if events:
            event = max(events, key=lambda row: int(row["operationEndNs"]) - int(row["operationStartNs"]))
            stalls.append((int(event["operationEndNs"]) - int(event["operationStartNs"]),
                           info, event, result, files["gc.log"]))
    duration, info, event, result, log = max(stalls, key=lambda row: row[0])
    begin, end = int(event["operationStartNs"]), int(event["operationEndNs"])
    safepoints = [(int(stamp) - int(total), int(stamp))
                  for stamp, total in SAFEPOINT.findall(log.decode())]
    if not safepoints:
        raise ValueError(f"No safepoint records for {info['label']}")
    return observations, info | {
        "operationIndex": int(event["operationIndex"]),
        "durationNs": duration,
        "readHistogramMaxUpperEquivalentNs": result["latency"]["read-service"]["maxUpperEquivalentNs"],
        "overlappingGcPauses": sum(p["startNs"] < end and p["endNs"] > begin for p in result["gc"]["pauses"]),
        "overlappingSafepoints": sum(start < end and stop > begin for start, stop in safepoints),
    }


def collect(directory):
    manifest = json.loads((directory / "MANIFEST.json").read_bytes())
    bundles = {bundle["file"]: bundle for bundle in manifest["collections"]}
    ages_inputs = {"age.log"}
    locality_archives = {"locality.tar.xz": 8, "followups-01-locality-long.tar.xz": 16}
    saturated_archive = "pressure-write-02-saturated-write-pressure.tar.xz"
    transition_archive = "pressure-write-02-write-transition.tar.xz"
    saturated_inputs = {f"worker/{channel}-bins.csv" for channel in ("read-service", "update-service")}
    locality = {
        name: [ages(result, files["age.log"]) for result, files
               in archived_slots(directory, bundles[name], count, ages_inputs)]
        for name, count in locality_archives.items()
    }
    operations = [saturated(result, files) for result, files in
                  archived_slots(directory, bundles[saturated_archive], 96, saturated_inputs)]
    sweep, stall = transition(archived_slots(directory, bundles[transition_archive], 48,
                                              ages_inputs | {"gc.log", "worker/stalls.csv"}))
    return {
        "archives": {name: bundles[name]["sha256"] for name in
                     (*locality_archives, saturated_archive, transition_archive)},
        "localityG1": locality,
        "saturatedOperations": operations,
        "writeTransition": sweep,
        "longestExportedChronicleOperationAt125Bps": stall,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Path to the second-host archive directory")
    args = parser.parse_args()
    print(json.dumps(collect(args.archive), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    if sys.version_info < (3, 10):
        raise SystemExit("Python 3.10 or later is required for the TailCache preprint audit.")
    main()
