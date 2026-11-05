#!/usr/bin/env python3
"""Complete independent qualification stages without pooling an incomplete screen."""
import argparse
import csv
import json
import subprocess
import sys

import tailcache12 as evidence
import tailcache12_calibrate as calibration
import tailcache12_everyop_jit as everyop
import tailcache12_observer as observer
import tailcache12_pilot as pilot
from tailcache12_calibration_start import prepare_file_cache,qualification_bindings
from tailcache12_provenance import archive_measurement_source_hash,measurement_source_hash
from tailcache12_quiet import run_preflight
from tailcache12_study_analysis import jmh_fork_summary


def validate_completed(prefix):
    expected=measurement_source_hash(evidence.ROOT); manifests=[]; refs={}
    for name in ('functional','pause','jit'):
        path=evidence.REPORTS/(prefix+'-'+name); manifest=json.loads((path/'manifest.json').read_text())
        if (calibration.sha(path/'source.tar.gz')!=manifest['sourceArchiveSha256']
                or archive_measurement_source_hash(path/'source.tar.gz')!=expected
                or evidence.replay(path)):
            raise ValueError('Completed prerequisite no longer matches/passes: '+name)
        if (manifest['stage']!=dict(functional='validate',pause='pause',jit='jit')[name]
                or len(manifest['invocations'])!=dict(functional=14,pause=2,jit=8)[name]):
            raise ValueError('Incomplete or incorrect reusable qualification stage')
        if name=='jit':
            for invocation in manifest['invocations']:
                p=invocation['properties']
                expected_controls=dict(Warmups=120,Conditioning=8,Residents=32768,
                    TransportWarmupVersion=evidence.TRANSPORT_WARMUP_VERSION,
                    LifecycleWarmupVersion=evidence.LIFECYCLE_WARMUP_VERSION)
                if any(p.get(k)!=v for k,v in expected_controls.items()):
                    raise ValueError('Reusable JMH preparation differs')
                raw=evidence.raw_directory(path,invocation)
                record=json.loads((raw/'compiler/results.json').read_text())[0]
                runtime={k:record[k] for k in ('jmhVersion','jdkVersion','vmName','vmVersion')}
                props=dict(p,Backend=p['Backends'],Payload=p['Payloads'],HeapMiB=512,Seed=24301,
                           ConsoleFile=str(path/invocation['label']/'gradle.log'))
                summary=jmh_fork_summary(raw,'compiler',props,
                    '3310547f9e5d01436fb54781f8cb50f312c8b3d29079f719694026e43107dfb3',runtime)
                if not summary['accepted']: raise ValueError('Reusable JMH raw contract rejected')
        manifests.append(manifest)
        refs[name]=dict(attempt=path.name,manifestSha256=calibration.sha(path/'manifest.json'),
                        sourceArchiveSha256=manifest['sourceArchiveSha256'])
    path=evidence.REPORTS/(prefix+'-observer'); probe=json.loads((path/'result.json').read_text())
    if (not probe['passed'] or not probe['sourceUnchanged']
            or calibration.sha(path/'source.tar.gz')!=probe['sourceArchiveSha256']
            or archive_measurement_source_hash(path/'source.tar.gz')!=expected):
        raise ValueError('Controlled observer source/proof changed')
    for name in ('inside','outside'):
        rows=[evidence.decode_host_row(r) for r in csv.DictReader((path/(name+'.csv')).open())]
        reasons,_=evidence.host_gate(rows,native_required=True,native_version=2)
        wanted=[] if name=='inside' else ['Native CPU outside benchmark scope exceeded 10% upper bound']
        if reasons!=wanted: raise ValueError('Raw controlled observer proof changed')
        manifests.append(dict(nativeEnvironmentVersion=1,
            nativeEnvironmentDeclaration=evidence.native_host.environment_declaration(rows[0])))
    pilot.verify_native_environments(manifests,evidence.host_snapshot())
    return refs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('completion_id'); parser.add_argument('--prefix',required=True)
    parser.add_argument('--everyop-reference',required=True)
    args=parser.parse_args()
    if any(not evidence.re.fullmatch(r'[A-Za-z0-9._-]+',x) for x in vars(args).values()):
        parser.error('Invalid evidence identifier')
    checkpoint=evidence.REPORTS/(args.completion_id+'-sequence.json')
    quiet=evidence.REPORTS/(args.completion_id+'-quiet')
    cache_path=evidence.REPORTS/(args.completion_id+'-cache-preparation.json')
    paths=dict(everyop=evidence.REPORTS/args.everyop_reference,
        pressure96=evidence.REPORTS/(args.prefix+'-pressure96'),floors=evidence.REPORTS/(args.prefix+'-floors'))
    if any(p.exists() for p in (checkpoint,quiet,cache_path,*paths.values())):
        raise ValueError('Completion evidence exists; inspect instead of overwriting or duplicating')
    source=evidence.source_hash(); refs=validate_completed(args.prefix)
    state=dict(complete=False,sourceSha256=source,measurementSourceSha256=measurement_source_hash(evidence.ROOT),
        reusedCompleteStageRefs=refs,completed=[],planned={k:p.name for k,p in paths.items()})
    evidence.save(checkpoint,state)
    try:
        cache=prepare_file_cache(cache_path)
        if not run_preflight(quiet,120,300)['quietPass']: raise ValueError('Fresh quiet prerequisite failed')
        evidence.save(quiet/'host-preparation.json',cache)
        common=['--warmups','120','--conditioning','8','--transport-warmup','--maintenance-warmup']
        commands=[('everyop','tailcache12_everyop_jit.py',['run',paths['everyop'].name,*common,'--unprofiled']),
            ('pressure96','tailcache12_everyop_jit.py',['run',paths['pressure96'].name,*common,
                '--backends','CAFFEINE','--payloads','4096','--live-mib','96']),
            ('floors','tailcache12_observer.py',['floors',paths['floors'].name,*common,
                '--native-host-retries','2','--native-host-retry-budget','8'])]
        for name,script,options in commands:
            if source!=evidence.source_hash(): raise ValueError('Source changed during completion')
            code=subprocess.run([sys.executable,str(evidence.ROOT/'scripts'/script),*options],cwd=evidence.ROOT).returncode
            if code: raise ValueError(name+' failed; later stages suspended')
            result=observer.replay_floors(paths[name]) if name=='floors' else everyop.replay(paths[name])
            if not result['floorDataPass' if name=='floors' else 'qualityPass']:
                raise ValueError('Raw stage replay rejected')
            state['completed'].append(name); evidence.save(checkpoint,state)
        state['qualificationRefs']=qualification_bindings(args.prefix,args.everyop_reference)
        state['complete']=True; evidence.save(checkpoint,state)
        print('Complete qualification prerequisites passed; calibration/pilot/campaign remain.',flush=True)
    except Exception as error:
        state['failure']=f'{type(error).__name__}: {error}'; evidence.save(checkpoint,state); raise


if __name__=='__main__': main()
