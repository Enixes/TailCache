#!/usr/bin/env python3
"""Reproducible data-quality and schedule gate for TailCache 10 secondary work."""
import argparse
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRIORITY = ["persisted two-JVM sharing", "Chronicle getUsing/object reuse",
            "cold/open/page-fault behavior"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=pathlib.Path,
                        default=ROOT / "docs" / "TAILCACHE_10_EVIDENCE.json")
    parser.add_argument("--out", type=pathlib.Path,
                        default=ROOT / "build" / "reports" / "tailcache10" / "decision.json")
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text())
    as_of = dt.date.fromisoformat(evidence["asOfDate"])
    task_due = dt.date.fromisoformat(evidence["task10DueDate"])
    target = dt.date.fromisoformat(evidence["projectTargetDate"])
    primary = evidence["primaryQuality"]
    allowed = {"sound", "invalid", "missing"}
    if set(primary) != {"rq1", "rq2", "persistedWarm"} or any(v not in allowed for v in primary.values()):
        parser.error("primaryQuality needs rq1, rq2 and persistedWarm with sound/invalid/missing states")
    remaining = evidence["remainingResearchHours"]
    minimum = evidence["minimumSecondaryHours"]
    if remaining is not None and remaining < 0 or minimum < 0:
        parser.error("research hours cannot be negative")
    reasons = []
    for name in ["rq1", "rq2", "persistedWarm"]:
        if primary[name] != "sound":
            reasons.append(f"{name} evidence is {primary[name]}")
    persisted_artifact_path = ROOT / evidence["sources"]["persistedWarm"]
    try:
        persisted_artifact = json.loads(persisted_artifact_path.read_text())
        persisted_machine_pass = persisted_artifact["machineChecksPass"] is True
    except (OSError, ValueError, KeyError) as error:
        persisted_machine_pass = False
        reasons.append(f"persisted-warm quality artifact unavailable: {error}")
    if not persisted_machine_pass:
        reasons.append("persisted-warm machine checks did not pass")
    if task_due < as_of or target < as_of:
        reasons.append("task or project target date has passed")
    if remaining is None:
        reasons.append("remaining research hours have not been verified")
    elif remaining < minimum:
        reasons.append(f"remaining research hours {remaining} are below the {minimum}-hour reserve")
    decision = {
        "schemaVersion": "tailcache10-gate-v1", "asOfDate": as_of.isoformat(),
        "task10DueDate": task_due.isoformat(), "projectTargetDate": target.isoformat(),
        "calendarDaysToTaskDue": (task_due - as_of).days,
        "calendarDaysToProjectTarget": (target - as_of).days,
        "remainingResearchHours": remaining, "minimumSecondaryHours": minimum,
        "primaryQuality": primary, "sourceEvidence": evidence["sources"],
        "persistedWarmMachineChecksPass": persisted_machine_pass,
        "secondaryDecision": "NO_GO" if reasons else "GO",
        "reasons": reasons, "priorityIfGatePasses": PRIORITY,
        "nextWork": "repair and rerun RQ1/RQ2 and persisted-warm primary evidence"
                    if reasons else PRIORITY[0],
        "evictionPolicySimulation": "cut_first"
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n")
    print(f"TailCache 10: {decision['secondaryDecision']} — {decision['nextWork']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
