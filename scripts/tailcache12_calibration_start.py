#!/usr/bin/env python3
"""Collect fresh quiet evidence and immediately launch the declared calibration.

The controller runs across model/usage interruptions. The calibration itself
freezes and replays the quiet reference and enforces its 360-second deadline.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

import tailcache12 as evidence
from tailcache12_quiet import run_preflight
from tailcache12_provenance import archive_measurement_source_hash,measurement_source_hash


def memory_snapshot():
    fields=dict(line.split(':',1) for line in pathlib.Path('/proc/meminfo').read_text().splitlines())
    return {k+'KiB':int(fields[k].split()[0]) for k in ('MemFree','MemAvailable','Cached')}


def prepare_file_cache(report):
    """Release only clean cached pages of retained task files, outside collection."""
    if report.exists(): raise ValueError('Cache preparation evidence exists; refusing overwrite')
    result=dict(version=1,method='fsync-and-posix-fadvise-dontneed-task-files',
                sourceSha256=evidence.source_hash(),before=memory_snapshot(),files=[],errors=[],
                minimumFreeKiB=3*1024**2,preparationPass=False)
    for root in (evidence.REPORTS,evidence.ROOT/'evidence-archives'):
        for path in sorted(root.rglob('*')):
            if path.is_symlink() or not path.is_file() or not path.stat().st_size:
                continue
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError('Task file cache preparation escaped its declared root')
            try:
                with path.open('rb') as stream:
                    os.fsync(stream.fileno())
                    os.posix_fadvise(stream.fileno(),0,0,os.POSIX_FADV_DONTNEED)
                result['files'].append(dict(path=str(path.relative_to(evidence.ROOT)),bytes=path.stat().st_size))
            except OSError as error:
                result['errors'].append(dict(path=str(path),error=str(error)))
    result['after']=memory_snapshot()
    result['preparationPass']=not result['errors'] and result['after']['MemFreeKiB']>=result['minimumFreeKiB']
    evidence.save(report,result)
    if not result['preparationPass']:
        raise ValueError('Task-local file cache preparation failed or free RAM below3GiB; no JVM launched')
    return result


def validate_actual_recorder(manifest,result):
    controls=dict(Residents=32768,HeapMiB=512,LiveBytes=0,ChurnBytesPerSecond=33554432,Seed=24301)
    props=[v['properties'] for v in manifest['invocations']]
    conditions=[(p['Backend'],p['Payload']) for p in props]
    expected={(backend,payload) for backend in evidence.BACKENDS for payload in (256,4096)}
    if (manifest.get('stage')!='everyop-jit' or result.get('qualityPass') is not True or result.get('compilerXml') is not False
            or len(props)!=8 or set(conditions)!=expected or any(conditions.count(c)!=2 for c in expected)
            or any(any(p.get(k)!=value for k,value in controls.items()) for p in props)):
        raise ValueError('Recorder reference must be a complete matching actual-unprofiled two-order screen')


def qualification_bindings(prefix,everyop_reference=None):
    """Bind the reviewed qualification to this checkout and current native boot."""
    import tailcache12_calibrate as calibration
    import tailcache12_pilot as pilot
    expected=measurement_source_hash(evidence.ROOT)
    manifests=[]
    refs={}
    for name,report,flag in (("functional","replayed-audit.json","functionalPass"),
            ("pause","replayed-audit.json","functionalPass"),("jit","replayed-audit.json","functionalPass"),
            ("everyop","everyop-jit.json","qualityPass"),("pressure96","everyop-jit.json","qualityPass"),
            ("floors","floors.json","floorDataPass")):
        if everyop_reference and not evidence.re.fullmatch(r'[A-Za-z0-9._-]+',everyop_reference):
            raise ValueError('Invalid explicit recorder reference')
        path=evidence.REPORTS/(everyop_reference if name=='everyop' and everyop_reference else prefix+"-"+name)
        manifest=json.loads((path/"manifest.json").read_text())
        result=json.loads((path/report).read_text())
        if (not result[flag] or calibration.sha(path/"source.tar.gz")!=manifest["sourceArchiveSha256"]
                or archive_measurement_source_hash(path/"source.tar.gz")!=expected):
            raise ValueError("Reviewed qualification source or acceptance changed: "+name)
        if name in ("jit","everyop") and len(manifest["invocations"])!=8:
            raise ValueError("Incomplete compiler qualification reference")
        if name=="everyop" and result.get("compilerXml") is not False:
            raise ValueError("Qualification did not exercise the actual unprofiled recorder")
        if name=='everyop': validate_actual_recorder(manifest,result)
        if name in ("jit","everyop","pressure96","floors") and any(
                v["properties"].get("Warmups")!=120 or v["properties"].get("Conditioning")!=8
                or v["properties"].get("TransportWarmupVersion")!=evidence.TRANSPORT_WARMUP_VERSION
                for v in manifest["invocations"]):
            raise ValueError("Qualification preparation controls differ from the declared grid")
        if name in ('jit','everyop','pressure96','floors') and any(
                v['properties'].get('LifecycleWarmupVersion')!=evidence.LIFECYCLE_WARMUP_VERSION
                for v in manifest['invocations']):
            raise ValueError('Qualification lifecycle preparation differs from the declared grid')
        manifests.append(manifest)
        refs[name]=dict(attempt=path.name,manifestSha256=calibration.sha(path/"manifest.json"),
            sourceArchiveSha256=manifest["sourceArchiveSha256"],measurementSourceSha256=expected)
    pilot.verify_native_environments(manifests,evidence.host_snapshot())
    return refs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt_id")
    parser.add_argument("quiet_id")
    parser.add_argument("--qualification-prefix",required=True)
    parser.add_argument('--everyop-reference')
    args=parser.parse_args()
    if any(not evidence.re.fullmatch(r"[A-Za-z0-9._-]+",v) for v in (args.attempt_id,args.quiet_id,args.qualification_prefix)):
        parser.error("Invalid attempt IDs")
    attempt,quiet=(evidence.REPORTS/v for v in (args.attempt_id,args.quiet_id))
    preparation=evidence.REPORTS/(args.quiet_id+'-cache-preparation.json')
    if attempt.exists() or quiet.exists() or preparation.exists():
        raise ValueError("Retained attempt exists; inspect it rather than duplicating or overwriting it")
    cache=prepare_file_cache(preparation)
    bindings=qualification_bindings(args.qualification_prefix,args.everyop_reference)
    source=evidence.source_hash()
    result=run_preflight(quiet,120,300)
    if not result["quietPass"] or source!=evidence.source_hash():
        raise ValueError("Quiet preparation failed or source changed; no calibration launched")
    evidence.save(quiet/'host-preparation.json',cache)
    evidence.save(quiet/"qualification-bindings.json",dict(prefix=args.qualification_prefix,
        sourceSha256=source,qualificationRefs=bindings))
    command=[sys.executable,str(evidence.ROOT/"scripts/tailcache12_calibrate.py"),"calibrate",args.attempt_id,
        "--initial-quiet",args.quiet_id,"--heap-mib","512","--residents","32768","--churn-mib","32",
        "--qualification-prefix",args.qualification_prefix,
        "--live-mib","0","96","208","288","--payloads","4096","256","--high-first","--seed","24301",
        "--warmups","120","--conditioning","8","--transport-warmup","--maintenance-warmup","--measurements","8","--repeats","2",
        "--native-host-retries","2","--native-host-retry-budget","8"]
    return subprocess.run(command,cwd=evidence.ROOT).returncode


if __name__=="__main__": raise SystemExit(main())
