#!/usr/bin/env python3
"""Export complete primary/robustness data with all candidates and raw dependencies.

Collection completeness and scientific resolution are different: valid unstable
comparisons remain unresolved in the export. No rejected candidate is pooled.
"""
import argparse
import csv
import json
import pathlib
import tarfile

import tailcache12 as evidence
import tailcache12_calibrate as calibration
import tailcache12_campaign as campaign


def collect_dependencies(attempt, seen=None):
    seen = seen if seen is not None else set()
    if attempt in seen:
        return seen
    seen.add(attempt)
    manifest = json.loads((attempt/"manifest.json").read_text())
    if manifest.get("initialQuietRef"):
        seen.add(attempt.parent/manifest["initialQuietRef"]["attempt"])
    for field in ("dependencyRefs","qualificationRefs"):
        for ref in manifest.get(field,{}).values():
            collect_dependencies(attempt.parent/ref["attempt"],seen)
    for invocation in manifest["invocations"]:
        seen.add(evidence.raw_directory(attempt,invocation))
    return seen


def export(primary_path, robustness_path, destination):
    primary = campaign.replay(primary_path)
    robustness = campaign.replay(robustness_path)
    pm = json.loads((primary_path/"manifest.json").read_text())
    rm = json.loads((robustness_path/"manifest.json").read_text())
    if (pm["stage"] != "campaign" or rm["stage"] != "robustness"
            or rm["dependencyRefs"]["primary"] != campaign.reference(primary_path)
            or not primary["analysisReady"] or not robustness["analysisReady"]
            or rm["seedSelections"] != campaign.robustness_selection(primary,pm["inputs"])):
        raise ValueError("Final export requires complete, related primary/robustness datasets")
    destination.mkdir(parents=True,exist_ok=False)
    output = dict(schemaVersion="tailcache12-final-dataset-v1", taskComplete=False,
        requiresResearcherReview=True, analysisReady=True,
        primaryAttempt=primary_path.name, robustnessAttempt=robustness_path.name,
        primary=primary, robustness=robustness, primaryProtocolSha256=pm["protocolSha256"],
        robustnessProtocolSha256=rm["protocolSha256"],
        limits=["Complete collection does not guarantee a resolved crossover.",
                "Variance failures and unresolved intervals prohibit a resolved claim for that comparison.",
                "Two independent outer passes give coarse bootstrap uncertainty; adjusted intervals are nominal.",
                "Periodic uniform trace, single worker, fixed heap, in-memory Chronicle: no persisted cold/open or multi-worker claim."])
    evidence.save(destination/"dataset.json",output)
    columns=["experiment","label","logicalSlot","candidateOrdinal","selected","accepted","backend","payloadBytes",
             "applicationLiveBytes","seed","channel","block","fork","p99Ns","p999Ns","hostReasons","qualityReasons"]
    with (destination/"coverage.csv").open("w",newline="") as stream:
        writer=csv.DictWriter(stream,columns)
        writer.writeheader()
        for experiment,result in (("primary",primary),("robustness",robustness)):
            for row in result["observations"]:
                p=row["inputs"]
                values=[experiment,row["label"],row["slotLabel"],row["ordinal"],row["selectedForAnalysis"],row["accepted"],
                    p["Backend"],p["Payload"],p["LiveBytes"],p["Seed"],p["Channel"],p["Block"],p["ForkOrdinal"],
                    row.get("servicePercentilesNs",{}).get("99"),row.get("servicePercentilesNs",{}).get("99.9"),
                    json.dumps(row["hostRejectionReasons"]),json.dumps(row["rejectionReasons"])]
                writer.writerow(dict(zip(columns,values)))
    for name,path in (("primary",primary_path),("robustness",robustness_path)):
        (destination/(name+"-protocol.json")).write_bytes((path/"protocol.json").read_bytes())
    paths=collect_dependencies(primary_path)|collect_dependencies(robustness_path)
    # Explicitly include every historical sibling attempt as retained context, without
    # adding any of its observations to either primary or robustness statistics.
    paths.update(p for p in evidence.REPORTS.iterdir() if p.is_dir() and (p/"manifest.json").is_file())
    archive_path=destination/"raw-sources.tar.gz"
    inventory=[]
    with tarfile.open(archive_path,"x:gz") as archive:
        for path in sorted(paths):
            if not path.is_dir():
                raise ValueError("Missing retained evidence directory")
            for file in sorted(path.rglob("*")):
                if file.is_file():
                    name=str(file.relative_to(evidence.ROOT))
                    inventory.append(dict(path=name,bytes=file.stat().st_size,sha256=calibration.sha(file)))
                    archive.add(file,arcname=name,recursive=False)
    evidence.save(destination/"archive-inventory.json",inventory)
    # Read back every archive member; a launched compression process is not a verified archive.
    with tarfile.open(archive_path,"r:gz") as archive:
        members=archive.getmembers()
        if [m.name for m in members] != [r["path"] for r in inventory]:
            raise ValueError("Archive member coverage differs from inventory")
        import hashlib
        for member,entry in zip(members,inventory):
            if hashlib.sha256(archive.extractfile(member).read()).hexdigest()!=entry["sha256"]:
                raise ValueError("Archive content checksum mismatch")
    evidence.save(destination/"archive.json",dict(path=archive_path.name,bytes=archive_path.stat().st_size,
        sha256=calibration.sha(archive_path),verifiedMembers=len(inventory),historicalEvidencePooled=False))
    (destination/"README.md").write_text(
        "# TailCache Task 12 dataset\n\nPrimary and separate seed-robustness observations, all candidate decisions and immutable protocols are in dataset.json and coverage.csv. "
        "Raw/source dependencies and historical attempts are retained in the verified archive; historical and rejected data are never pooled. "
        "Researcher review is still required before task completion or publication. Read each comparison's variance, coverage and nominal uncertainty limits.\n")
    print(f"Verified analysis-ready export: {destination}; researcher review pending",flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary",required=True)
    parser.add_argument("--robustness",required=True)
    parser.add_argument("--output",required=True,type=pathlib.Path)
    args=parser.parse_args()
    destination=args.output.resolve()
    if destination.is_relative_to(evidence.ROOT/"build"):
        parser.error("Final dataset must be retained outside build/")
    export(evidence.REPORTS/args.primary,evidence.REPORTS/args.robustness,destination)


if __name__=="__main__":
    main()
