#!/usr/bin/env python3
"""One bounded odd-period diagnostic; never qualifies or launches a campaign."""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
from types import SimpleNamespace

import tailcache12 as evidence
from tailcache12_calibration_start import prepare_file_cache
from tailcache12_provenance import measurement_source_hash
from tailcache12_quiet import run_preflight

OPAQUE_OPTIONS = (
    '-XX:+UnlockDiagnosticVMOptions',
    '-XX:CompileCommand=dontinline,io.github.enixes.tailcache.workload.CrossoverWorkload::executeNext',
    '-XX:CompileCommand=dontinline,io.github.enixes.tailcache.workload.CrossoverWorkload::executeSupplyFloorNext',
    '-XX:CompileCommand=PrintInlining,io.github.enixes.tailcache.workload.CrossoverLatencyRunner::runWindow',
    '-XX:CompileCommand=PrintInlining,io.github.enixes.tailcache.benchmark.jmh_generated.CrossoverBenchmark_mixedWorkload_jmhTest::mixedWorkload_sample_jmhStub',
)
TLAB_OPTIONS = ('-Xlog:gc+tlab=debug:stdout:timenanos,pid,tid,level,tags',)


def run_fixed_probe(attempt,quiet):
    """A new eight-slot diagnostic, with full recorder contracts and frozen quiet proof."""
    import tailcache12_calibrate as calibration
    import tailcache12_native_retry as native_retry
    from tailcache12_provenance import archive_measurement_source_hash
    from tailcache12_study_analysis import every_operation_fork_summary
    options=SimpleNamespace(stage='probe',heap_mib=512,residents=32768,churn_mib=32,live_mib=[0],
        payloads=[256],seed=24301,warmups=120,measurements=8,repeats=2,
        channels=['sample-calibration','every-operation'],conditioning=16,
        transport_warmup=True,maintenance_warmup=True,resume=False)
    grid=calibration.calibration_grid(calibration.vars_inputs(options))
    manifest=calibration.prepare(attempt,options,grid)
    current=evidence.host_snapshot()
    if os.environ.get('TAILCACHE_REQUIRE_NATIVE_HOST')!='1' or current.get('nativeScopeQualified')!=1:
        raise ValueError('Fixed-buffer probe requires exclusive native scope')
    manifest.update(diagnosticOnly=True,primaryEndpointUseAllowed=False,replacements=0,maxFreshJvms=8,
        measurementSourceSha256=measurement_source_hash(evidence.ROOT),nativeEnvironmentVersion=1,
        nativeEnvironmentDeclaration=evidence.native_host.environment_declaration(current),
        plan='docs/TAILCACHE_12_BUFFER_DECIMATION_PLAN.md')
    policy=native_retry.declare_policy(2)
    manifest['initialQuietRef']=native_retry.initial_quiet_reference(quiet,manifest,policy,current)
    evidence.save(attempt/'manifest.json',manifest)
    for index,(label,props) in enumerate(grid):
        if index==0:
            native_retry.verify_initial_quiet(attempt,dict(manifest,nativeHostRetryPolicy=policy),before_launch=True)
        evidence.invoke(attempt,manifest,label,'tailCache12SampleCalibration' if props['Channel']=='sample-calibration'
                        else 'tailCache12EveryOperation',calibration.command_properties(props))
    result=calibration.replay(attempt)
    if (archive_measurement_source_hash(attempt/'source.tar.gz')!=manifest['measurementSourceSha256']
            or len(manifest['invocations'])!=8
            or [(i['label'],i['properties']) for i in manifest['invocations']]!=
                [(k,calibration.command_properties(v)) for k,v in grid]):
        raise ValueError('Fixed-buffer diagnostic source/schedule changed or incomplete')
    traces={r['traceSha256'] for r in result['observations'] if r['channel']=='sample-calibration'}
    if len(traces)!=1:raise ValueError('Fixed-buffer trace identities differ')
    full=[]
    for inv,row in zip(manifest['invocations'],result['observations']):
        if row['channel']=='every-operation':
            summary=every_operation_fork_summary(
                    pathlib.Path(inv['rawDirectory'])/'every-operation',inv['properties'],
                    next(iter(traces)),runtime_identity=result['runtimeIdentity'])
            row=dict(row,**summary)
        full.append(row)
    quiet_replay=native_retry.verify_initial_quiet(attempt,dict(manifest,nativeHostRetryPolicy=policy),full)
    passed=len(full)==8 and all(not r['rejectionReasons'] and not r['hostRejectionReasons'] for r in full)
    evidence.save(attempt/'fixed-buffer-review.json',dict(observations=full,diagnosticOnly=True,
        primaryEndpointUseAllowed=False,reportable=False,qualityPass=passed,initialQuietReplay=quiet_replay))
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('attempt_id')
    parser.add_argument('quiet_id')
    parser.add_argument('--plan', choices=('odd-period', 'mixed-selector', 'opaque-operation', 'tlab-debug','fixed-buffer'), default='odd-period')
    args = parser.parse_args()
    if any(not re.fullmatch(r'[A-Za-z0-9._-]+', v) for v in (args.attempt_id, args.quiet_id)):
        parser.error('Invalid attempt IDs')
    attempt, quiet = (evidence.REPORTS / v for v in (args.attempt_id, args.quiet_id))
    preparation = evidence.REPORTS / (args.quiet_id + '-cache-preparation.json')
    declaration = evidence.REPORTS / (args.attempt_id + '-declaration.json')
    if any(p.exists() for p in (attempt, quiet, preparation, declaration)):
        raise ValueError('Retained attempt exists; inspect it rather than overwriting or duplicating')
    environment = None
    overrides = {}
    diagnostic_options = []
    if args.plan=='fixed-buffer' and any(os.environ.get(k) for k in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS')):
        raise ValueError('Fixed-buffer validation requires clean unprofiled JVM options')
    if args.plan in ('opaque-operation', 'tlab-debug'):
        if os.environ.get('JAVA_TOOL_OPTIONS'):
            raise ValueError('Inherited JAVA_TOOL_OPTIONS must be absent; refusing an ambiguous diagnostic')
        diagnostic_options = list(OPAQUE_OPTIONS if args.plan == 'opaque-operation' else TLAB_OPTIONS)
        overrides = {'JAVA_TOOL_OPTIONS': ' '.join(diagnostic_options)}
        environment = dict(os.environ, **overrides)
    command = [sys.executable, str(evidence.ROOT / 'scripts/tailcache12_calibrate.py'),
        'probe', args.attempt_id, '--live-mib', '0', '--payloads', '256', '--residents', '32768',
        '--heap-mib', '512', '--churn-mib', '32', '--seed', '24301', '--repeats', '2',
        '--channels', 'sample-calibration', 'every-operation', '--warmups', '120',
        '--conditioning', '16', '--measurements', '8', '--transport-warmup', '--maintenance-warmup']
    if args.plan=='fixed-buffer':
        command=[sys.executable,str(pathlib.Path(__file__).resolve()),args.attempt_id,args.quiet_id,'--plan','fixed-buffer']
    source = evidence.source_hash()
    with declaration.open('x') as stream:
        json.dump(dict(command=command, sourceSha256=source,
            measurementSourceSha256=measurement_source_hash(evidence.ROOT),
            expectedJvmAttempts=8, replacements=0, reportable=False,
            primaryEndpointUseAllowed=False, quiet=args.quiet_id,
            environmentOverrides=overrides, diagnosticJvmOptions=diagnostic_options,
            plan={'odd-period':'docs/TAILCACHE_12_SAMPLING_DESIGN_PLAN.md',
                  'mixed-selector':'docs/TAILCACHE_12_SAMPLE_SELECTION_PLAN.md',
                  'opaque-operation':'docs/TAILCACHE_12_OPAQUE_OPERATION_PLAN.md',
                  'tlab-debug':'docs/TAILCACHE_12_TLAB_OBSERVATION_PLAN.md',
                  'fixed-buffer':'docs/TAILCACHE_12_BUFFER_DECIMATION_PLAN.md'}[args.plan]), stream, indent=2)
    cache = (prepare_file_cache(preparation,include_build_outputs=True,stream_inventory=True) if args.plan=='fixed-buffer'
             else prepare_file_cache(preparation))
    if args.plan=='fixed-buffer' and cache.get('version')!=4:raise ValueError('Require declared streaming preparation')
    result = run_preflight(quiet, 120, 300)
    evidence.save(quiet / 'host-preparation.json', cache)
    if not result['quietPass'] or source != evidence.source_hash():
        raise ValueError('Quiet preparation failed or source changed; no diagnostic JVM launched')
    if args.plan=='fixed-buffer':return run_fixed_probe(attempt,quiet)
    # Probe mode retains every scheduled diagnostic, even a rejected one. It
    # never returns calibrationReady and no old/source-mismatched fork is reused.
    return subprocess.run(command, cwd=evidence.ROOT, env=environment).returncode


if __name__ == '__main__':
    raise SystemExit(main())
