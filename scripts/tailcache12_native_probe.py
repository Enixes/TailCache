#!/usr/bin/env python3
"""Bounded, non-benchmark CPU observer validation using known inside/outside work."""
import argparse
import csv
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tarfile
import time

import tailcache12 as evidence
import tailcache12_native_host as native
from tailcache12_provenance import measurement_source_hash

BUSY = "import time; end=time.monotonic()+4; x=1\nwhile time.monotonic()<end: x=(x*1664525+1013904223)&0xffffffff"
OUTSIDE = ("import pathlib,subprocess,sys; print(pathlib.Path('/proc/self/cgroup').read_text(),flush=True); "
           "children=[subprocess.Popen([sys.executable,'-c'," + repr(BUSY) + "]) for _ in range(3)]; "
           "[p.wait() for p in children]")


def phase(path, outside, unit):
    samples = [evidence.host_snapshot()]
    children = []
    try:
        if outside:
            children.append(subprocess.Popen(["systemd-run", "--user", "--scope", "--quiet",
                "--expand-environment=no", "--unit=tailcache12-outside-" + unit,
                sys.executable, "-c", OUTSIDE], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        else:
            children = [subprocess.Popen([sys.executable, "-c", BUSY]) for _ in range(3)]
        for _ in range(6):
            time.sleep(1)
            samples.append(evidence.host_snapshot())
        output = []
        for child in children:
            stdout, stderr = child.communicate(timeout=10)
            if child.returncode:
                raise ValueError("Controlled CPU probe failed: " + str(stderr))
            if stdout:
                output.append(stdout)
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(samples[0]))
            writer.writeheader()
            writer.writerows(samples)
    intervals = native.cpu_intervals(samples)
    return dict(reasons=evidence.host_gate(samples)[0], maxOutsideUpperPercent=max(r["outsideUpperPercent"] for r in intervals),
                maxOutsidePercent=max(r["outsidePercent"] for r in intervals), output=output,
                scope=samples[0]["nativeCgroup"], samples=len(samples))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt_id")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.attempt_id):
        parser.error("Invalid attempt ID")
    path = evidence.REPORTS / args.attempt_id
    path.mkdir(parents=True, exist_ok=False)
    source = evidence.source_hash()
    with tarfile.open(path / "source.tar.gz", "w:gz") as archive:
        for file in evidence.sources():
            archive.add(file, arcname=str(file.relative_to(evidence.ROOT)))
    try:
        inside = phase(path / "inside.csv", False, args.attempt_id)
        outside = phase(path / "outside.csv", True, args.attempt_id)
    except Exception as error:
        evidence.save(path / "result.json", dict(reportable=False, passed=False, sourceSha256=source,
                                                 monitorFailure=f"{type(error).__name__}: {error}"))
        raise
    result = dict(reportable=False, observerVersion=native.VERSION, inside=inside, outside=outside,
                  sourceSha256=source, sourceUnchanged=source == evidence.source_hash(),
                  sourceArchiveSha256=hashlib.sha256((path / "source.tar.gz").read_bytes()).hexdigest(),
                  measurementSourceSha256=measurement_source_hash(evidence.ROOT),
                  passed=source == evidence.source_hash() and not inside["reasons"]
                         and outside["reasons"] == ["Native CPU outside benchmark scope exceeded 10% upper bound"]
                         and any("tailcache12-outside-" in text and inside["scope"] not in text
                                 for text in outside["output"]))
    evidence.save(path / "result.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
