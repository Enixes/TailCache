#!/usr/bin/env python3
"""Export complete primary/robustness data with all candidates and raw dependencies.

Collection completeness and scientific resolution are different: valid unstable
comparisons remain unresolved in the export. No rejected candidate is pooled.
"""
import argparse
import csv
import fcntl
import json
import pathlib
import tarfile

import tailcache12 as evidence
import tailcache12_campaign as campaign
from tailcache12_archive import file_digest,stream_digest,advise


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


def archive_reports(archive_path,required):
    root=evidence.REPORTS.resolve()
    if archive_path.resolve().is_relative_to(root):raise ValueError('Dataset archive must be outside report tree')
    if any(not path.is_dir() or path.is_symlink() or not path.resolve().is_relative_to(root) for path in required):
        raise ValueError('Missing or external primary/robustness evidence dependency')
    files=sorted(path for path in evidence.REPORTS.rglob('*') if path.is_file() and not path.is_symlink()
                 and path!=evidence.REPORTS/'native-benchmark.lock')
    inventory=[]
    with tarfile.open(archive_path,'x:gz',compresslevel=1,dereference=True) as archive:
        for path in files:
            if not path.resolve().is_relative_to(root):raise ValueError('Evidence inventory escaped report tree')
            name=path.relative_to(evidence.ROOT).as_posix()
            inventory.append(dict(path=name,bytes=path.stat().st_size,sha256=file_digest(path)))
            archive.add(path,arcname=name,recursive=False);advise(path)
    advise(archive_path)
    entries={r['path']:r for r in inventory};seen=set()
    if len(entries)!=len(inventory):raise ValueError('Duplicate export inventory')
    with tarfile.open(archive_path,'r:gz') as archive:
        for member in archive:
            if not member.isfile() or member.name in seen or member.name not in entries:
                raise ValueError('Unexpected or duplicate export archive member')
            entry=entries[member.name]
            with archive.extractfile(member) as stream:
                if member.size!=entry['bytes'] or stream_digest(stream)!=entry['sha256']:
                    raise ValueError('Export archive checksum/size mismatch')
            seen.add(member.name)
    if seen!=set(entries):raise ValueError('Missing export archive members')
    result=dict(path=archive_path.name,bytes=archive_path.stat().st_size,sha256=file_digest(archive_path),
                verifiedMembers=len(inventory),historicalEvidencePooled=False,hashChunkBytes=1024*1024)
    advise(archive_path)
    return inventory,result


def export(primary_path,robustness_path,destination):
    if destination.exists():raise ValueError('Retained dataset exists; refusing overwrite')
    with (evidence.REPORTS/'native-benchmark.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Benchmark/controller/export active; dataset export refused')
        return export_locked(primary_path,robustness_path,destination)


def export_locked(primary_path, robustness_path, destination):
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
    # The unique report-tree inventory also preserves all available historical raw
    # siblings, not just their control manifests. Their observations are never pooled.
    archive_path=destination/"raw-sources.tar.gz"
    inventory,archive_result=archive_reports(archive_path,paths)
    evidence.save(destination/"archive-inventory.json",inventory)
    evidence.save(destination/"archive.json",archive_result)
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
