#!/usr/bin/env python3
"""Rebuild the second-host reports from archived evidence without collecting new data."""

import collections
import math
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from tailcache_portable import load, report, require, retained, sha, verify_derivatives

LOG_DERIVED_FIELDS = {"geometricMeanRatio", "logRatioSampleSd", "exploratoryPairedBootstrap95"}


def same_summary(actual, expected, log_derived=False):
    """Allow libm rounding only in statistics derived from log ratios."""
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(
            same_summary(value, expected[key], key in LOG_DERIVED_FIELDS)
            for key, value in actual.items()
        )
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(
            same_summary(a, b, log_derived) for a, b in zip(actual, expected, strict=True)
        )
    if log_derived and isinstance(actual, float):
        return math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-15)
    return actual == expected


def extract(archive, destination):
    with tarfile.open(archive, "r:xz") as bundle:
        for member in bundle:
            name = PurePosixPath(member.name)
            require(member.isfile() and not name.is_absolute() and ".." not in name.parts,
                    f"Unsafe archive member in {archive.name}: {member.name}")
            target = destination.joinpath(*name.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(member) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)


def verify_phase(archive_dir, phase, evidence, reference, phase_dir, generated):
    run = load(phase_dir / "run.json")
    require(run["sourceRunSha256"] == reference["runSha256"]
            == evidence["sourceRunSha256"], f"Run provenance differs for {phase_dir}")
    require(load(phase_dir / "source-digests.json")["sourceResultsSha256"]
            == reference["sourceResultsSha256"], f"Results provenance differs for {phase_dir}")
    rebuilt = report(phase_dir, generated)
    require(rebuilt["allSlotsSuccessful"] and rebuilt["completed"] == evidence["workloadJvms"]
            == reference["completed"], f"Slot coverage differs for {phase_dir}")
    require((generated / "percentiles.csv").read_text()
            == (archive_dir / evidence["percentiles"]).read_text(),
            f"Percentiles differ for {phase_dir}")
    require(same_summary(load(generated / "point-conclusions.json"),
                         load(archive_dir / evidence["pointConclusions"])),
            f"Point conclusions differ for {phase_dir}")

    retry = rebuilt["retryReview"]
    retry_count = 0 if retry is None else sum(len(attempt["statuses"]) for attempt in retry["attempts"])
    require(retry_count == evidence["retryJvms"], f"Retry coverage differs for {phase_dir}")
    controls = len(rebuilt["timingControls"])
    require(controls == evidence["timingControlJvms"], f"Control coverage differs for {phase_dir}")
    for control in rebuilt["timingControls"]:
        slot = phase_dir / "controls" / control["label"]
        verify_derivatives(slot, retained(slot), run["config"])
    if "compactResults" in reference:
        compact = load(archive_dir.parent / reference["compactResults"])
        for key in ("pairs", "timingControls", "retryReview"):
            require(rebuilt[key] == compact.get(key), f"{key} differs for {phase_dir}")
        require(same_summary(rebuilt["summaries"], compact["summaries"]),
                f"Summaries differ for {phase_dir}")
        for current, original in zip(rebuilt["observations"], compact["observations"], strict=True):
            for name, digest in current["rawSha256"].items():
                if name != "worker/configuration.txt":
                    require(digest == original["rawSha256"][name],
                            f"Raw measurement differs for {phase_dir}: {name}")
    print(f"Verified {phase_dir.parent.name}/{phase}: {rebuilt['completed']} slots, "
          f"{retry_count} retries, {controls} controls")
    return {phase: rebuilt["completed"], "retry": retry_count, "control": controls}


def main():
    archive_dir = Path(__file__).resolve().parents[1] / "docs/second-host-20261120/archive"
    published = load(archive_dir.parent / "MANIFEST.json")["campaigns"]
    counts = collections.Counter()
    for bundle in load(archive_dir / "MANIFEST.json")["collections"]:
        archive = archive_dir / bundle["file"]
        require(sha(archive) == bundle["sha256"], f"Archive checksum differs: {archive.name}")
        campaign = published[bundle["campaign"]]
        suite = campaign.get("suites", {bundle["campaign"]: campaign})[bundle["suite"]]
        require(bundle["sourceCommit"] == suite["sourceCommit"],
                f"Source revision differs: {archive.name}")
        with tempfile.TemporaryDirectory(prefix="tailcache-verify-") as directory:
            work = Path(directory)
            collected = work / archive.name.removesuffix(".tar.xz")
            extract(archive, collected)
            if "phases" in suite:
                require(load(collected / "suite.json")["sourceSuiteSha256"]
                        == bundle["sourceSuiteSha256"] == suite["manifestSha256"],
                        f"Suite provenance differs: {archive.name}")
            phases = suite.get("phases", {"pilot": suite})
            require(bundle["phases"].keys() == phases.keys(), f"Phase coverage differs: {archive.name}")
            for phase, evidence in bundle["phases"].items():
                counts.update(verify_phase(archive_dir, phase, evidence, phases[phase],
                                           collected / phase, work / f"rebuilt-{phase}"))
    require(counts == {"research": 252, "retry": 2, "smoke": 32, "pilot": 4, "control": 60},
            f"Dataset coverage differs: {dict(counts)}")
    print(f"Verified {sum(counts.values())} JVM records across the archive.")


if __name__ == "__main__":
    main()
