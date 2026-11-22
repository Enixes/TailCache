#!/usr/bin/env python3
"""Build the standalone TailCache reader from the frozen paired results."""

import argparse
import collections
import hashlib
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUANTILES = ("50", "99", "99.9", "99.99", "99.999")
SNAPSHOT = ROOT / "docs/preprint/review-chart-data.json"


def load(path):
    return json.loads(path.read_text())


def mixed_time(directory, filename):
    manifest = load(directory / "MANIFEST.json")
    file = directory / filename
    record = next(details for details in manifest["collections"] if details["file"] == filename)
    if hashlib.sha256(file.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError(f"Archive hash differs: {file}")
    times = {}
    with tarfile.open(file, "r:xz") as archive:
        for item in archive:
            if not item.name.startswith("research/slots/") or not item.name.endswith("/result.json"):
                continue
            data = json.load(archive.extractfile(item))
            times[data["spec"]["label"]] = sum(
                event["overlapNs"] for event in data["gc"]["pauses"]
                if event["kind"].startswith("Pause Young (Mixed)")
            ) / 1_000_000
    return times


def metrics(record, second_host=False):
    channels = {}
    for label in ("service", "read-service", "update-service", "response"):
        stats = record["latency"].get(label)
        if stats and stats["count"]:
            results = (stats["percentiles"] if second_host else stats["percentilesNs"])
            channels[label] = [
                results[q]["ns"] if second_host else results[q] for q in QUANTILES
            ]
    return channels | {"gc": record["gc"]["pauseOverlapMs"], "warnings": record["warnings"]}


def make_pair(caffeine, chronicle, axes, second_host=False):
    return axes | {
        "c": metrics(caffeine, second_host),
        "h": metrics(chronicle, second_host),
    }


def second_host_pairs(root, name, select=None, mixed=None):
    data = load(root / name / "research/results-compact.json")
    by_label = {r["spec"]["label"]: r for r in data["observations"]}
    pairs = []
    for pair in data["pairs"]:
        caffeine, chronicle = sorted(
            (by_label[label] for label in pair["labels"]), key=lambda r: r["spec"]["backend"]
        )
        spec = caffeine["spec"]
        if select and not select(spec):
            continue
        if not pair["usable"]:
            raise ValueError(f"Unexpected unusable pair in {name}")
        row = make_pair(caffeine, chronicle, dict(
            key=spec["updateHotset"], payload=spec["payloadBytes"], heap=spec["liveMiB"],
            writes=spec["writeBps"] / 100, seed=spec["seed"], block=spec["block"],
        ), True)
        if mixed is not None:
            row["c"]["mixed"] = mixed[spec["label"]]
            row["h"]["mixed"] = mixed[chronicle["spec"]["label"]]
        pairs.append(row)
    return pairs


def first_host_locality():
    data = load(ROOT / "docs/mechanism/mechanism-data-20261118.json")
    forks = {r["id"]: r for r in data["forks"]}
    return [
        make_pair(forks[p["c"]], forks[p["h"]],
                  dict(key=p["hotset"], seed=p["seed"], block=p["block"]))
        for p in data["pairs"]
        if p["cohort"] in {"hotset-screen", "hotset-repeat"} and p["valid"]
    ]


def early_pressure():
    data = load(ROOT / "docs/preprint/paper-data.json")
    blocks = collections.defaultdict(list)
    for record in data["observations"]:
        if record["dataset"] == "midpoint" and record["cohort"] == "primary":
            blocks[(record["liveMiB"], record["seed"], record["block"])].append(record)
    return [
        make_pair(*sorted(records, key=lambda r: r["backend"]),
                  dict(heap=heap, seed=seed, block=block))
        for (heap, seed, block), records in sorted(blocks.items())
    ]


def collect(root):
    data = {
        "locality": {
            "first": first_host_locality(),
            "second": second_host_pairs(root, "locality",
                                        mixed=mixed_time(root / "archive", "locality.tar.xz")),
            "long": second_host_pairs(root, "followups-01/locality-long",
                                      mixed=mixed_time(root / "archive", "followups-01-locality-long.tar.xz")),
        },
        "payload": second_host_pairs(root, "pressure-write-02/saturated-write-pressure"),
        "pressure": {
            "short": early_pressure(),
            "full": second_host_pairs(root, "followups-01/rq-matrix",
                                      lambda s: s["qps"] and s["payloadBytes"] == 4096),
        },
    }
    counts = [len(rows) for rows in data["locality"].values()]
    counts += [len(data["payload"])] + [len(rows) for rows in data["pressure"].values()]
    if counts != [8, 4, 8, 48, 9, 8]:
        raise ValueError(f"Unexpected reader data coverage: {counts}")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path,
                        help="Regenerate the snapshot from docs/second-host-20261120 on the portability branch")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "output/html/tailcache-preprint-reader.html")
    args = parser.parse_args()
    if args.evidence:
        data = collect(args.evidence)
        SNAPSHOT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    else:
        data = load(SNAPSHOT)
    page = (ROOT / "scripts/tailcache_preprint_reader.html").read_text()
    snapshot = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page.replace("/*__EVIDENCE__*/", snapshot))


if __name__ == "__main__":
    main()
