#!/usr/bin/env python3
"""Freeze, collect and audit Task 12 primary and separate seed-robustness datasets.

No campaign launch is allowed before replayed pilot/floor qualification. Candidate
replacements use only the prospectively declared host-quality policy. Uncertain
or unstable valid forks remain visible; they cannot be replaced as outliers.
"""
import argparse
import csv
import json
import random
import re
import subprocess
import tarfile

import tailcache12 as evidence
import tailcache12_calibrate as calibration
import tailcache12_native_retry as native_retry
import tailcache12_observer as observer
import tailcache12_pilot as pilot
from tailcache12_provenance import archive_measurement_source_hash, measurement_source_hash
from tailcache12_study_analysis import hierarchical_ratio, variance_reasons

VERSION = "tailcache12-campaign-v1"
RULES = dict(version=VERSION, passes=2, primaryForksPerPass=3, measurements=8,
    conditioningIterations=8,
    transportWarmupVersion=evidence.TRANSPORT_WARMUP_VERSION,
    p99BetweenPassCeiling=1.25, p999BetweenPassCeiling=1.5,
    minimumTailObservations=100000, bootstrapResamples=50000,
    familyComparisons=32, familyAlpha=.05, descriptiveConfidence=.95,
    robustnessSeeds=[0xC0FFEE, 0xBADC0DE],
    robustnessSelection="Always range endpoints; all adjacent point-estimate crossings in either channel/endpoint, plus immediate neighboring levels",
    confidenceMethod="Nominal Bonferroni intervals from paired fork/pass bootstrap; two outer passes give coarse uncertainty",
    gcExposure="At least one measured GC and measured post-GC occupancy per logged fork; actual counts/durations reported, no claim about unobserved rarer pauses",
    outliers="Retain all quality-passing forks; variance failure is unresolved evidence, never grounds for replacement",
    primaryChannels=list(pilot.PRIMARY), diagnosticChannels=[c for c in pilot.TASKS if c not in pilot.PRIMARY])


def schedule(inputs, order_seed, selections=None):
    if (len(inputs["liveBytes"]) != 4 or set(inputs["payloads"]) != {256, 4096}
            or inputs["warmups"] < 12 or inputs["measurements"] != RULES["measurements"]):
        raise ValueError("Campaign requires four calibrated levels and qualified preparation")
    # Each seed is a separate experiment. Never merge seed histograms or forks.
    selections = selections or {str(inputs["seed"]): {str(p): inputs["liveBytes"] for p in inputs["payloads"]}}
    grid = []
    for seed_text, by_payload in selections.items():
        seed = int(seed_text)
        cells = [(int(p), live) for p, levels in by_payload.items() for live in levels]
        random.Random(order_seed ^ seed).shuffle(cells)
        channels = list(pilot.TASKS)
        for block in (1, 2):
            for payload, live in (cells if block == 1 else list(reversed(cells))):
                for channel in (channels if block == 1 else list(reversed(channels))):
                    for fork in range(1, (3 if channel in pilot.PRIMARY else 1) + 1):
                        for backend in (evidence.BACKENDS if (block+fork) % 2 == 0 else tuple(reversed(evidence.BACKENDS))):
                            label = f"s{seed}-b{block}-{channel}-p{payload}-live{live}-f{fork}-{backend}"
                            props = dict(Backend=backend, Payload=payload, LiveBytes=live, Residents=inputs["residents"],
                                HeapMiB=inputs["heapMiB"], ChurnBytesPerSecond=inputs["churnBytesPerSecond"], Seed=seed,
                                Warmups=inputs["warmups"], Measurements=inputs["measurements"],
                                Channel=channel, Block=block, ForkOrdinal=fork)
                            if channel != "every-operation":
                                props.update(Backends=backend, Payloads=payload, Forks=1)
                            grid.append((label, props))
    return calibration.preparation_controls(grid,inputs)


def reference(path):
    return dict(attempt=path.name, manifestSha256=calibration.sha(path/"manifest.json"),
                sourceArchiveSha256=calibration.sha(path/"source.tar.gz"),
                measurementSourceSha256=archive_measurement_source_hash(path/"source.tar.gz"))


def verify_refs(attempt, manifest):
    for ref in manifest["dependencyRefs"].values():
        path = attempt.parent/ref["attempt"]
        if reference(path) != ref:
            raise ValueError("Changed campaign prerequisite")
        dependency = json.loads((path/"manifest.json").read_text())
        for invocation in dependency["invocations"]:
            calibration.verify_invocation(path, invocation)


def verify_protocol(attempt, manifest):
    frozen = attempt/"protocol.json"
    if (manifest["schemaVersion"] != VERSION or manifest["rules"] != RULES
            or calibration.sha(frozen) != manifest["protocolSha256"]):
        raise ValueError("Changed frozen campaign rules")
    declaration = json.loads(frozen.read_text())
    for key in declaration:
        if declaration[key] != manifest[key]:
            raise ValueError("Campaign manifest differs from prospective protocol: " + key)
    if (calibration.sha(attempt/"source.tar.gz") != manifest["sourceArchiveSha256"]
            or archive_measurement_source_hash(attempt/"source.tar.gz") != manifest["measurementSourceSha256"]):
        raise ValueError("Changed campaign source archive")
    grid = schedule(manifest["inputs"], manifest["orderSeed"], manifest["seedSelections"])
    if manifest["schedule"] != [dict(label=k, properties=v) for k,v in grid]:
        raise ValueError("Changed canonical campaign schedule")
    native_retry.verify_declaration(attempt, manifest, grid)
    verify_refs(attempt, manifest)
    return grid


def comparison_rows(rows, inputs, selections, full=True):
    results = []
    for seed, by_payload in selections.items():
        for channel in pilot.PRIMARY:
            for payload, levels in by_payload.items():
                for live in levels:
                    chosen = [r for r in rows if r["inputs"]["Seed"] == int(seed)
                        and r["inputs"]["Payload"] == int(payload) and r["inputs"]["LiveBytes"] == live
                        and r["inputs"]["Channel"] == channel]
                    c = dict(seed=int(seed), channel=channel, payloadBytes=int(payload), applicationLiveBytes=live,
                             complete=False, varianceRejectionReasons=[], ratios={})
                    if len(chosen) == 12 and all(r["accepted"] for r in chosen):
                        endpoints = {backend: [[next(r["servicePercentilesNs"] for r in chosen
                            if r["inputs"]["Backend"] == backend and r["inputs"]["Block"] == block
                            and r["inputs"]["ForkOrdinal"] == fork) for fork in (1,2,3)] for block in (1,2)]
                            for backend in evidence.BACKENDS}
                        c["varianceRejectionReasons"] = variance_reasons(endpoints,
                            RULES["p99BetweenPassCeiling"], RULES["p999BetweenPassCeiling"])
                        c["complete"] = True
                        if full:
                            for endpoint in ("99", "99.9"):
                                blocks = [[(endpoints["CAFFEINE"][b][f][endpoint], endpoints["CHRONICLE_IN_MEMORY"][b][f][endpoint])
                                           for f in range(3)] for b in range(2)]
                                # Robustness seed families remain separate, with the same conservative 32-comparison correction.
                                interval = hierarchical_ratio(blocks, resamples=RULES["bootstrapResamples"],
                                    confidence=1-RULES["familyAlpha"]/RULES["familyComparisons"])
                                descriptive = hierarchical_ratio(blocks)
                                interval.update(descriptiveLower95=descriptive["lower95"], descriptiveUpper95=descriptive["upper95"],
                                    direction="chronicle-lower" if interval["upper"] < 1 else
                                              "caffeine-lower" if interval["lower"] > 1 else "unresolved")
                                c["ratios"][endpoint] = interval
                    results.append(c)
    return results


def crossing_regions(comparisons, levels):
    regions = []
    keys = sorted({(c["seed"], c["channel"], c["payloadBytes"]) for c in comparisons})
    for seed, channel, payload in keys:
        cells = sorted([c for c in comparisons if (c["seed"],c["channel"],c["payloadBytes"]) == (seed,channel,payload)],
                       key=lambda c:c["applicationLiveBytes"])
        for endpoint in ("99", "99.9"):
            complete = len(cells) == len(levels) and all(c["complete"] and c["ratios"] and not c["varianceRejectionReasons"] for c in cells)
            transitions = []
            if complete:
                for a,b in zip(cells,cells[1:]):
                    if (a["ratios"][endpoint]["direction"], b["ratios"][endpoint]["direction"]) == ("caffeine-lower","chronicle-lower"):
                        transitions.append([a["applicationLiveBytes"],b["applicationLiveBytes"]])
            directions = [c["ratios"].get(endpoint,{}).get("direction","missing") for c in cells]
            regions.append(dict(seed=seed, channel=channel, payloadBytes=payload, endpoint=endpoint,
                supportedRegions=transitions, fullTestedRangeCovered=complete,
                interpretation="supported crossing region" if transitions else
                    "same resolved direction throughout tested range" if complete and len(set(directions)) == 1 and directions[0] != "unresolved"
                    else "unresolved; no global no-crossover claim"))
    return regions


def replay(attempt):
    manifest = json.loads((attempt/"manifest.json").read_text())
    verify_protocol(attempt, manifest)
    rows = []
    for invocation in manifest["invocations"]:
        trace = manifest["traceBySeed"][str(invocation["properties"]["Seed"])]
        row = pilot.analyze(attempt, dict(manifest, traceSha256=trace), invocation)
        rows.append(row)
    state = native_retry.select(manifest, rows)
    checks, errors = native_retry.verify_preflights(attempt, manifest, rows, state)
    selected = [r for r in rows if r["label"] in state["selectedLabels"]]
    for row in rows:
        row.update(state["attemptStatuses"][row["label"]])
    errors += state["terminalRejectionReasons"]
    if manifest.get("terminalDriverFailure"):
        errors.append("Terminal campaign driver failure: " + manifest["terminalDriverFailure"]["reason"])
    data_pass = state["complete"] and not errors and all(r["accepted"] for r in selected)
    comparisons = comparison_rows(selected, manifest["inputs"], manifest["seedSelections"], full=data_pass)
    variance_pass = all(c["complete"] and not c["varianceRejectionReasons"] for c in comparisons)
    result = dict(schemaVersion=VERSION, stage=manifest["stage"], reportable=False,
        dataCompleteAndQualityPass=data_pass, variancePass=variance_pass,
        analysisReady=data_pass, claimsRequireVarianceAndRobustnessReview=True,
        observations=rows, comparisons=comparisons, nativeHostRetryState=state,
        nativeRetryPreflightRejectionReasons=errors, replayedRetryPreflights=checks,
        completedBlocks=len(selected), expectedBlocks=len(manifest["expectedBlocks"]), recordedJvmAttempts=len(rows),
        missingBlocks=state["missingSlots"], rejectionReasons=errors,
        crossingRegions=crossing_regions(comparisons, manifest["inputs"]["liveBytes"]),
        rules=RULES, replaySourceSha256=evidence.source_hash(),
        limits=[RULES["confidenceMethod"], RULES["gcExposure"], RULES["outliers"],
                "Seed robustness is analyzed separately; pilot/floors/rejected forks never enter primary comparisons.",
                "Only in-memory Chronicle is compared; persisted cold/open/page-fault behavior is outside this experiment."])
    evidence.save(attempt/"campaign.json", result)
    print(f"{manifest['stage']}={attempt/'campaign.json'} blocks={len(selected)}/{len(manifest['expectedBlocks'])} quality={data_pass}",flush=True)
    return result


def robustness_selection(primary, inputs):
    if not primary["dataCompleteAndQualityPass"]:
        raise ValueError("Robustness requires the complete primary dataset")
    levels = inputs["liveBytes"]
    selected = {str(p): {levels[0],levels[-1]} for p in inputs["payloads"]}
    for p in inputs["payloads"]:
        for channel in pilot.PRIMARY:
            cells = sorted([c for c in primary["comparisons"] if c["payloadBytes"] == p and c["channel"] == channel],
                           key=lambda c:c["applicationLiveBytes"])
            if len(cells) != 4 or any(not c["complete"] or not c["ratios"] for c in cells):
                raise ValueError("Missing primary comparison for robustness selection")
            for index,(a,b) in enumerate(zip(cells,cells[1:])):
                if any((a["ratios"][e]["ratio"]-1)*(b["ratios"][e]["ratio"]-1) <= 0 for e in ("99","99.9")):
                    selected[str(p)].update(levels[max(0,index-1):min(4,index+3)])
    return {str(seed): {p: sorted(lives) for p,lives in selected.items()} for seed in RULES["robustnessSeeds"]}


def freeze(attempt, args):
    if attempt.exists():
        raise ValueError("Frozen attempts are immutable; use a new ID")
    pilot_path, floor_path = evidence.REPORTS/args.pilot, evidence.REPORTS/args.floors
    reviewed = observer.coherence(pilot_path, floor_path)
    pilot_result = pilot.replay(pilot_path)
    if not reviewed["observerQualified"] or not pilot_result["provisionalVariancePass"]:
        raise ValueError("Replayed pilot/coherence gates must pass before protocol freeze")
    parent = json.loads((pilot_path/"manifest.json").read_text())
    inputs = parent["inputs"]
    if inputs.get("conditioning",0)!=RULES["conditioningIterations"]:
        raise ValueError("Campaign requires prospectively declared measurement-mode conditioning")
    if inputs.get("transportWarmupVersion")!=RULES["transportWarmupVersion"]:
        raise ValueError("Campaign requires qualified result-transport preparation")
    pilot.verify_native_environments([parent], evidence.host_snapshot())
    source = measurement_source_hash(evidence.ROOT)
    if source != archive_measurement_source_hash(pilot_path/"source.tar.gz"):
        raise ValueError("Current measurement source differs from qualified pilot")
    dependencies = dict(pilot=reference(pilot_path),floors=reference(floor_path))
    if args.primary:
        primary_path = evidence.REPORTS/args.primary
        primary = replay(primary_path)
        previous = json.loads((primary_path/"manifest.json").read_text())
        if previous["stage"] != "campaign" or previous["dependencyRefs"] != dependencies:
            raise ValueError("Robustness primary uses different prerequisites")
        selections = robustness_selection(primary,inputs)
        dependencies["primary"] = reference(primary_path)
        stage = "robustness"
    else:
        stage = "campaign"
        selections = {str(inputs["seed"]): {str(p): inputs["liveBytes"] for p in inputs["payloads"]}}
    # Fingerprints must be supplied from the deterministic trace tool before collection,
    # rather than learned from the first benchmark fork.
    traces = json.loads(args.traces.read_text())
    if (set(traces) != {str(inputs["seed"]), *map(str,RULES["robustnessSeeds"])}
            or any(not re.fullmatch(r"[0-9a-f]{64}",v) for v in traces.values())
            or traces[str(inputs["seed"])] != parent["traceSha256"]):
        raise ValueError("Missing predeclared primary/robustness trace fingerprints")
    grid = schedule(inputs,args.order_seed,selections)
    attempt.mkdir(parents=True)
    manifest = dict(schemaVersion=VERSION, stage=stage, reportable=False, rules=RULES,
        sourceSha256=evidence.source_hash(), measurementSourceSha256=source, hostRuleVersion=evidence.HOST_RULE_VERSION,
        gitHead=subprocess.check_output(["git","rev-parse","HEAD"],cwd=evidence.ROOT,text=True).strip(),
        dependencyRefs=dependencies, qualificationRefs=parent["qualificationRefs"], inputs=inputs,
        runtimeIdentity=parent["runtimeIdentity"], calibrationBands=parent["calibrationBands"],
        orderSeed=args.order_seed, traceBySeed=traces, seedSelections=selections,
        expectedBlocks=[k for k,_ in grid], schedule=[dict(label=k,properties=v) for k,v in grid], invocations=[])
    native_retry.initialize(attempt,manifest,grid,native_retry.declare_policy(2,8,stage),evidence.host_snapshot())
    with tarfile.open(attempt/"source.tar.gz","w:gz") as archive:
        for path in evidence.sources():
            archive.add(path,arcname=str(path.relative_to(evidence.ROOT)))
    manifest["sourceArchiveSha256"] = calibration.sha(attempt/"source.tar.gz")
    # Freeze all launch, analysis, environment, source and prerequisite controls.
    declaration = {k:v for k,v in manifest.items() if k not in ("invocations","nativeRetryPreflights")}
    evidence.save(attempt/"protocol.json",declaration)
    manifest["protocolSha256"] = calibration.sha(attempt/"protocol.json")
    evidence.save(attempt/"manifest.json",manifest)
    print(f"Frozen {stage}: {len(grid)} JVM slots; no benchmark launched.",flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=("freeze","run","audit"))
    parser.add_argument("attempt_id")
    parser.add_argument("--pilot")
    parser.add_argument("--floors")
    parser.add_argument("--primary")
    parser.add_argument("--traces",type=evidence.pathlib.Path)
    parser.add_argument("--order-seed",type=int,default=24301)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._-]+",args.attempt_id):
        parser.error("Invalid attempt ID")
    attempt = evidence.REPORTS/args.attempt_id
    if args.stage == "freeze":
        if not all((args.pilot,args.floors,args.traces)):
            parser.error("Freeze requires --pilot, --floors and --traces")
        freeze(attempt,args)
        return 0
    manifest = json.loads((attempt/"manifest.json").read_text())
    if args.stage == "run":
        verify_protocol(attempt,manifest)
        if manifest["sourceSha256"] != evidence.source_hash():
            raise ValueError("Source changed after protocol freeze; collection cannot resume")
        native_retry.run_grid(attempt,manifest,replay,lambda p:pilot.TASKS[p["Channel"]])
    return 0 if replay(attempt)["dataCompleteAndQualityPass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
