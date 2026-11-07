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
from contextlib import nullcontext
import hashlib

import tailcache12 as evidence
from tailcache12_quiet import run_preflight
from tailcache12_provenance import archive_measurement_source_hash,measurement_source_hash


def memory_snapshot():
    fields=dict(line.split(':',1) for line in pathlib.Path('/proc/meminfo').read_text().splitlines())
    result={k+'KiB':int(fields[k].split()[0]) for k in ('MemFree','MemAvailable','Cached')}
    result['SwapUsedKiB']=int(fields['SwapTotal'].split()[0])-int(fields['SwapFree'].split()[0])
    return result


def verify_cache_inventory(directory,receipt):
    name=receipt.get('inventoryFile','')
    if not evidence.re.fullmatch(r'[A-Za-z0-9._-]+\.inventory\.jsonl',name):
        raise ValueError('Invalid private cache inventory reference')
    path=directory/name
    if path.is_symlink():raise ValueError('Cache inventory is a symlink')
    digest=hashlib.sha256();count=total=0;seen=set()
    with path.open('rb') as stream:
        while line:=stream.readline(65537):
            if len(line)>65536 or not line.endswith(b'\n'):raise ValueError('Oversized/truncated inventory row')
            digest.update(line);row=json.loads(line);relative=pathlib.PurePosixPath(row['path'])
            if (set(row)!={'path','bytes'} or relative.is_absolute() or '..' in relative.parts
                    or relative.as_posix()!=row['path'] or not relative.parts
                    or relative.parts[0] not in ('build','evidence-archives','.gradle')
                    or type(row['bytes']) is not int or row['bytes']<=0 or row['path'] in seen):
                raise ValueError('Invalid/duplicate private inventory row')
            seen.add(row['path']);count+=1;total+=row['bytes']
    if (digest.hexdigest()!=receipt.get('inventorySha256') or count!=receipt.get('inventoryCount')
            or total!=receipt.get('inventoryBytes')):raise ValueError('Private cache inventory changed/incomplete')
    return dict(files=count,bytes=total)


def prepare_file_cache(report,require_empty_swap=True,include_build_outputs=False,stream_inventory=False):
    """Release only clean cached pages of retained task files, outside collection."""
    if report.exists(): raise ValueError('Cache preparation evidence exists; refusing overwrite')
    if stream_inventory and not include_build_outputs:raise ValueError('Streaming preparation requires private roots')
    inventory=report.with_suffix('.inventory.jsonl')
    if stream_inventory and inventory.exists():raise ValueError('Preparation inventory exists; refusing overwrite')
    result=dict(version=4 if stream_inventory else 3 if include_build_outputs else 2,method='fsync-and-posix-fadvise-dontneed-task-files',
                sourceSha256=evidence.source_hash(),before=memory_snapshot(),files=[],errors=[],
                minimumFreeKiB=3*1024**2,requiresEmptySwap=require_empty_swap,preparationPass=False)
    roots=(evidence.ROOT/'build',evidence.ROOT/'evidence-archives',evidence.ROOT/'.gradle') if include_build_outputs else (
        evidence.REPORTS,evidence.ROOT/'evidence-archives')
    if include_build_outputs:result['roots']=['build','evidence-archives','.gradle']
    if include_build_outputs:
        for root in roots:
            if root.is_symlink() or not root.resolve().is_relative_to(evidence.ROOT.resolve()):
                result['errors'].append(dict(path=str(root),error='Private preparation root is a symlink or escapes the checkout'))
        if result['errors']:
            evidence.save(report,result)
            raise ValueError('Private cache preparation root escaped its declaration; no advice applied')
    digest=hashlib.sha256();count=total=0
    if stream_inventory:result.pop('files')
    with (inventory.open('xb') if stream_inventory else nullcontext()) as output:
        for root in roots:
            for path in (root.rglob('*') if stream_inventory else sorted(root.rglob('*'))):
                if stream_inventory and path==inventory:continue
                if path.is_symlink() or not path.is_file() or not path.stat().st_size:
                    continue
                if not path.resolve().is_relative_to(root.resolve()):
                    raise ValueError('Task file cache preparation escaped its declared root')
                try:
                    with path.open('rb') as stream:
                        os.fsync(stream.fileno())
                        os.posix_fadvise(stream.fileno(),0,0,os.POSIX_FADV_DONTNEED)
                    record=dict(path=str(path.relative_to(evidence.ROOT)),bytes=path.stat().st_size)
                    if stream_inventory:
                        line=(json.dumps(record,separators=(',',':'))+'\n').encode();output.write(line);digest.update(line)
                        count+=1;total+=record['bytes']
                    else:result['files'].append(record)
                except OSError as error:
                    result['errors'].append(dict(path=str(path),error=str(error)))
        if stream_inventory:
            output.flush();os.fsync(output.fileno())
            os.posix_fadvise(output.fileno(),0,0,os.POSIX_FADV_DONTNEED)
    if stream_inventory:
        result.update(inventoryFile=inventory.name,inventorySha256=digest.hexdigest(),inventoryCount=count,inventoryBytes=total)
    result['after']=memory_snapshot()
    result['preparationPass']=(not result['errors'] and result['after']['MemFreeKiB']>=result['minimumFreeKiB']
        and (not require_empty_swap or result['after']['SwapUsedKiB']==0))
    evidence.save(report,result)
    if not result['preparationPass']:
        raise ValueError('Task-local preparation failed, free RAM below3GiB or residual swap remains; no JVM launched')
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


def qualification_bindings(prefix,everyop_reference=None,conditioning=8):
    """Bind the reviewed qualification to this checkout and current native boot."""
    import tailcache12_calibrate as calibration
    import tailcache12_pilot as pilot
    if conditioning not in (8,16): raise ValueError('Unreviewed qualification conditioning count')
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
                v["properties"].get("Warmups")!=120 or v["properties"].get("Conditioning")!=conditioning
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
    parser.add_argument('--conditioning',type=int,choices=(8,16),default=8)
    parser.add_argument('--swap-preparation',help='Retained successful one-time residual-page recovery report ID')
    args=parser.parse_args()
    if any(not evidence.re.fullmatch(r"[A-Za-z0-9._-]+",v) for v in (args.attempt_id,args.quiet_id,args.qualification_prefix)):
        parser.error("Invalid attempt IDs")
    attempt,quiet=(evidence.REPORTS/v for v in (args.attempt_id,args.quiet_id))
    preparation=evidence.REPORTS/(args.quiet_id+'-cache-preparation.json')
    if attempt.exists() or quiet.exists() or preparation.exists():
        raise ValueError("Retained attempt exists; inspect it rather than duplicating or overwriting it")
    cache=prepare_file_cache(preparation)
    reset=None
    if args.swap_preparation:
        if not evidence.re.fullmatch(r'[A-Za-z0-9._-]+',args.swap_preparation):
            raise ValueError('Invalid swap preparation reference')
        import tailcache12_swap_prepare as swap
        reset=json.loads((evidence.REPORTS/(args.swap_preparation+'.json')).read_text())
        if (not reset.get('preparationPass') or not reset.get('configurationRestored')
                or reset.get('measurementSourceSha256')!=measurement_source_hash(evidence.ROOT)
                or swap.configuration(reset['before'])!=swap.configuration(reset['after'])
                or swap.configuration(swap.snapshot())!=swap.configuration(reset['after'])):
            raise ValueError('Swap preparation failed, source/policy changed or configuration not restored')
    bindings=qualification_bindings(args.qualification_prefix,args.everyop_reference,args.conditioning)
    source=evidence.source_hash()
    result=run_preflight(quiet,120,300)
    if not result["quietPass"] or source!=evidence.source_hash():
        raise ValueError("Quiet preparation failed or source changed; no calibration launched")
    if reset:
        evidence.save(quiet/'swap-preparation.json',reset)
        cache['swapPreparationSha256']=__import__('hashlib').sha256((quiet/'swap-preparation.json').read_bytes()).hexdigest()
    evidence.save(quiet/'host-preparation.json',cache)
    evidence.save(quiet/"qualification-bindings.json",dict(prefix=args.qualification_prefix,
        sourceSha256=source,qualificationRefs=bindings))
    command=[sys.executable,str(evidence.ROOT/"scripts/tailcache12_calibrate.py"),"calibrate",args.attempt_id,
        "--initial-quiet",args.quiet_id,"--heap-mib","512","--residents","32768","--churn-mib","32",
        "--qualification-prefix",args.qualification_prefix,
        "--live-mib","0","96","208","288","--payloads","4096","256","--high-first","--seed","24301",
        "--warmups","120","--conditioning",str(args.conditioning),"--transport-warmup","--maintenance-warmup","--measurements","8","--repeats","2",
        "--native-host-retries","2","--native-host-retry-budget","8"]
    return subprocess.run(command,cwd=evidence.ROOT).returncode


if __name__=="__main__": raise SystemExit(main())
