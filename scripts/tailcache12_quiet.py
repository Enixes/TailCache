#!/usr/bin/env python3
"""Retain a bounded, non-benchmark quiet-host preflight before qualification."""
import argparse
import csv
import json
import math
import pathlib
import re
import time

import tailcache12 as evidence


def run_preflight(attempt, quiet_seconds=60, timeout_seconds=300):
    if not 10 <= quiet_seconds <= timeout_seconds <= 600:
        raise ValueError("Require 10 ≤ quiet seconds ≤ timeout seconds ≤ 600")
    attempt = pathlib.Path(attempt)
    attempt.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    samples, quiet, rejected = [], [], []
    passed, failure = False, None
    try:
        while time.monotonic() - started < timeout_seconds:
            sample = evidence.host_snapshot()
            samples.append(sample)
            if quiet and sample["monotonicNs"] - quiet[-1]["monotonicNs"] > 5e9:
                rejected.append(dict(sampleIndex=len(samples) - 1,
                                     reasons=["host sampling gap exceeds five seconds"]))
                quiet = []
            quiet.append(sample)
            if len(quiet) >= 2:
                reasons, _ = evidence.host_gate(quiet)
                if reasons:
                    rejected.append(dict(sampleIndex=len(samples) - 1, reasons=reasons))
                    quiet = [sample]
                elif quiet[-1]["monotonicNs"] - quiet[0]["monotonicNs"] >= quiet_seconds * 1e9:
                    passed = True
                    break
            time.sleep(1)
    except Exception as error:
        failure = f"{type(error).__name__}: {error}"
    finally:
        if samples:
            with (attempt / "host.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(samples[0]))
                writer.writeheader()
                writer.writerows(samples)
        result = dict(stage="quiet-preflight", reportable=False,
            hostRuleVersion=evidence.HOST_RULE_VERSION, sourceSha256=evidence.source_hash(),
            requiredQuietSeconds=quiet_seconds, timeoutSeconds=timeout_seconds,
            elapsedSeconds=time.monotonic() - started, quietPass=passed, monitorFailure=failure,
            rejectedWindows=rejected, sampleCount=len(samples),
            limits="A quiet preflight does not replace host monitoring in any measurement block.")
        evidence.save(attempt / "quiet.json", result)
    print(f"quiet={attempt / 'quiet.json'} pass={passed} samples={len(samples)}", flush=True)
    return result


def replay_preflight(attempt, source_hash, quiet_seconds=60, timeout_seconds=300, native_version=5):
    """Reconstruct a retry prerequisite from retained host intervals, not its flag."""
    attempt = pathlib.Path(attempt)
    result = json.loads((attempt / "quiet.json").read_text())
    if (result.get("stage") != "quiet-preflight" or result.get("sourceSha256") != source_hash
            or result.get("hostRuleVersion") != evidence.HOST_RULE_VERSION
            or result.get("requiredQuietSeconds") != quiet_seconds
            or result.get("timeoutSeconds") != timeout_seconds):
        raise ValueError("Retry preflight identity or declared timing changed")
    with (attempt / "host.csv").open(newline="") as stream:
        samples = [evidence.decode_host_row(row) for row in csv.DictReader(stream)]
    if result.get("sampleCount") != len(samples) or not samples:
        raise ValueError("Missing or inconsistent retry preflight samples")
    if any(s.get("windowsHostRequired") != 1 or s.get("windowsMonitorVersion") != native_version
           or not s.get("windowsCpuCounter") or s.get("windowsCpuCounter") == "unspecified"
           or not math.isfinite(s["monotonicNs"]) for s in samples):
        raise ValueError("Retry preflight requires the declared native observer")
    if any(a["monotonicNs"] >= b["monotonicNs"] for a, b in zip(samples, samples[1:])):
        raise ValueError("Retry preflight sample clock did not advance")
    span = (samples[-1]["monotonicNs"] - samples[0]["monotonicNs"]) / 1e9
    elapsed = result.get("elapsedSeconds", float("nan"))
    if not math.isfinite(elapsed) or not span <= elapsed + 1 <= timeout_seconds + 6:
        raise ValueError("Retry preflight elapsed time is inconsistent")
    quiet, passed, pass_index = [], False, None
    for index, sample in enumerate(samples):
        if quiet and sample["monotonicNs"] - quiet[-1]["monotonicNs"] > 5e9:
            quiet = []
        quiet.append(sample)
        if len(quiet) >= 2:
            reasons, _ = evidence.host_gate(quiet)
            if reasons:
                quiet = [sample]
            elif quiet[-1]["monotonicNs"] - quiet[0]["monotonicNs"] >= quiet_seconds * 1e9:
                passed, pass_index = True, index
                break
    if passed != result.get("quietPass") or (passed and pass_index != len(samples) - 1):
        raise ValueError("Retry quiet flag disagrees with raw host intervals")
    return dict(quietPass=passed and result.get("monitorFailure") is None,
                firstMonotonicNs=samples[0]["monotonicNs"],
                lastMonotonicNs=samples[-1]["monotonicNs"], sampleCount=len(samples),
                powerSchemes=sorted({s["windowsPowerScheme"] for s in samples}),
                cpuCounters=sorted({s["windowsCpuCounter"] for s in samples}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt_id")
    parser.add_argument("--quiet-seconds", type=int, default=60)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.attempt_id):
        parser.error("Invalid attempt ID")
    if not 10 <= args.quiet_seconds <= args.timeout_seconds <= 600:
        parser.error("Require 10 ≤ quiet seconds ≤ timeout seconds ≤ 600")
    result = run_preflight(evidence.REPORTS / args.attempt_id, args.quiet_seconds, args.timeout_seconds)
    return 0 if result["quietPass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
