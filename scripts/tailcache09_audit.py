#!/usr/bin/env python3
"""Validate and join the separate TailCache 09 capacity, latency and throughput runs."""
import argparse
import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
ESTIMATES = ["HALF", "MATCH", "DOUBLE", "CONSTANT"]
PAYLOADS = [256, 4096]


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def key(row):
    return (int(row["actualPayloadBytes"]), row["estimate"])


def index_jmh(path, mode, unit, errors):
    try:
        records = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        errors.append(f"{path}: {error}")
        return {}
    expected = {(payload, estimate) for payload in PAYLOADS for estimate in ESTIMATES}
    indexed = {}
    for record in records:
        record_key = key(record["params"])
        if record_key in indexed:
            errors.append(f"duplicate {mode} record: {record_key}")
        indexed[record_key] = record
        if record["mode"] != mode or record["primaryMetric"]["scoreUnit"] != unit:
            errors.append(f"bad {mode} mode/unit: {record_key}")
        if record["threads"] != 1:
            errors.append(f"wrong worker count: {record_key}")
    if set(indexed) != expected:
        errors.append(f"{mode}: incomplete sizing matrix")
    return indexed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    args = parser.parse_args()
    run = ROOT / "build" / "reports" / "tailcache09" / args.run_id
    errors = []
    try:
        with (run / "capacity" / "capacity.csv").open(newline="") as stream:
            capacity_rows = list(csv.DictReader(stream))
    except OSError as error:
        parser.error(str(error))
    capacity = {}
    for row in capacity_rows:
        k = (row["storage"], *key(row))
        if k in capacity:
            errors.append(f"duplicate capacity row: {k}")
        capacity[k] = row
        if int(row["finalMapSize"]) != int(row["successfulInserts"]):
            errors.append(f"capacity size mismatch: {k}")
        if not row["firstFailureClass"] and row["censoredAtMaxInserts"].lower() == "false":
            errors.append(f"first failure not recorded: {k}")
    expected_capacity = {(storage, payload, estimate) for storage in ("IN_MEMORY", "PERSISTED")
                         for payload in PAYLOADS for estimate in ESTIMATES}
    if set(capacity) != expected_capacity:
        errors.append("capacity matrix is incomplete or has unexpected conditions")
    latency = index_jmh(run / "sample" / "results.json", "sample", "ns/op", errors)
    throughput = index_jmh(run / "thrpt" / "results.json", "thrpt", "ops/s", errors)
    rows = []
    for payload in PAYLOADS:
        for estimate in ESTIMATES:
            k = (payload, estimate)
            if k not in latency or k not in throughput or ("IN_MEMORY", *k) not in capacity:
                continue
            cap = capacity[("IN_MEMORY", *k)]
            resident = int(latency[k]["params"].get("residentEntries", 64))
            if resident != int(throughput[k]["params"].get("residentEntries", 64)):
                errors.append(f"resident set differs across timing modes: {k}")
            if int(cap["successfulInserts"]) <= resident:
                errors.append(f"benchmark resident set reaches capacity boundary: {k}")
            l = latency[k]["primaryMetric"]
            t = throughput[k]["primaryMetric"]
            count = sum(int(pair[1]) for fork in l.get("rawDataHistogram", [])
                        for iteration in fork for pair in iteration)
            if count == 0:
                errors.append(f"no SampleTime observations: {k}")
            rows.append({"actualPayloadBytes": payload, "estimate": estimate,
                         "configuredSamplePayloadBytes": cap["configuredSamplePayloadBytes"],
                         "residentEntries": resident, "inMemorySuccessfulInserts": cap["successfulInserts"],
                         "persistedSuccessfulInserts": capacity.get(("PERSISTED", *k), {}).get("successfulInserts", ""),
                         "persistedFileBytesAtFailure": capacity.get(("PERSISTED", *k), {}).get("fileBytes", ""),
                         "samples": count, "p50Ns": l["scorePercentiles"]["50.0"],
                         "p95Ns": l["scorePercentiles"]["95.0"],
                         "p99Ns": l["scorePercentiles"]["99.0"],
                         "p999Ns": l["scorePercentiles"]["99.9"],
                         "throughputOpsPerSec": t["score"]})
            if (latency[k]["forks"] < 2 or latency[k]["warmupIterations"] < 8
                    or latency[k]["measurementIterations"] < 5
                    or throughput[k]["forks"] < 2 or throughput[k]["warmupIterations"] < 8
                    or throughput[k]["measurementIterations"] < 5):
                errors.append(f"short validation timing/forks: {k}")
    with (run / "summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    save(run / "quality.json", {"machineChecksPass": not errors, "errors": errors,
         "researchStatus": "requires_manual_review" if not errors else "validation_only",
         "limits": ["Capacity insertion is untimed and separate from steady-state JMH.",
                    "Average-sample lengths are nominal payload bytes, not exact serialized sizes.",
                    "In-memory and persisted capacity are separate checksum/storage strata."]})
    print(f"rows={len(rows)} errors={len(errors)} status={'validation_only' if errors else 'requires_manual_review'}")
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
