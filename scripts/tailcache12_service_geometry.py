#!/usr/bin/env python3
"""Fixed equal-array logical trace-pattern control; fresh matched anchors."""
import argparse
import random
import shutil
import subprocess
import sys
import tailcache12_service_campaign as core
import tailcache12_focused as focus

ROOT=core.ROOT
PATTERNS=('uniform-long','repeated-short')


def schedule():
    cells=[(pattern,block) for pattern in PATTERNS for block in (1,2)]
    random.Random(24410).shuffle(cells)
    slots=[]
    for i,(pattern,block) in enumerate(cells):
        pair=core.pair_specs('geometry-'+pattern,4096,0,block=block,reverse=bool((i+block)%2))
        for row in pair:row.update(tracePattern=pattern,regime='arrival',qps=50000,
                                  extraArgs=['--trace-pattern',pattern])
        slots+=pair
    return slots


def validate():
    base=ROOT/'build/service-policy-trace-20261117'
    core.validate_compilation(base/'compilation.json',base/'policy-functional-validation.json','policy')
    base=ROOT/'build/service-geometry-20261117'
    compiled=focus.load(base/'compilation.json');qualified=focus.load(base/'functional-validation.json')
    core.check(compiled.get('passed') is True and qualified.get('passed') is True and qualified.get('mode')=='geometry',
               'Geometry qualification required')
    core.check(qualified['compilationSha256']==focus.sha(base/'compilation.json'),'Geometry qualification/compiler identity')
    for name,digest in compiled['sourceSha256'].items():core.check(focus.sha(ROOT/name)==digest,'Geometry source changed')
    for name,digest in compiled['compiledRuntime'].items():core.check(focus.sha(base/name)==digest,'Geometry class changed')


class Geometry(core.Campaign):
    def run_controls(self):
        controls=[('timer',True,False,0,'uniform-long'),('injected-stall',True,False,20,'uniform-long')]
        controls += [('supply-'+p,False,True,0,p) for p in PATTERNS]
        for label,floor,supply,inject,pattern in controls:
            row=core.pair_specs('geometry-control-'+label,4096,0,block=0)[0]
            row.update(tracePattern=pattern,extraArgs=['--trace-pattern',pattern],regime='arrival',qps=50000,
                       residents=64,churnMiB=0,floor=floor,supply=supply,inject=inject)
            r=self.execute([row],control=True)[0]
            core.check(r['status']=='OK' and r['measurement']['operations']==200000,'Geometry control conservation')
            if inject:core.check(r['latency']['service']['maxNs']>=15000000 and
                r['latency']['response']['percentilesNs']['99.9']>=1000000,'Known pause/queue-debt visibility')

    def run(self):
        self.run_controls();self.execute(self.protocol['design']['schedule']);self.check_frozen()
        rows=self.observations();pairs=core.pairs(rows);by={r['label']:r for r in rows}
        core.check(len(rows)==8 and len(pairs)==4,'Fixed geometry workload budget')
        for row in rows:
            if row['status']=='OK':
                expected={'WARMUP':3000000,'CONDITIONING':200000,'MEASUREMENT':1500000}
                core.check(all(int(w['scheduled'])==int(w['operations'])==expected[w['phase']] for w in row['windows']),
                           'Geometry all-phase conservation')
                core.check(row['trace']['tracePattern']==row['tracePattern'] and row['trace']['traceArrayPayloadBytes']=='9000027',
                           'Actual geometry treatment differs')
        for pair in pairs:
            if not pair['valid']:continue
            c,h=[by[pair['labels'][b]] for b in core.BACKENDS]
            core.check([(w['phase'],w['writes']) for w in c['windows']]==[(w['phase'],w['writes']) for w in h['windows']],
                       'Paired geometry-phase writes differ')
            pair['ratios']['response']={q:h['latency']['response']['percentilesNs'][q]/c['latency']['response']['percentilesNs'][q]
                                      for q in core.PERCENTILES if c['latency']['response']['percentilesNs'][q]}
        core.immutable(self.out/'study.json',dict(kind='equal-array-logical-trace-pattern-control',collectionComplete=True,
            observations=rows,pairs=pairs,workloadJvms=8,primary='scheduled-response p99.9 at baseline',
            limits=['Equal trace-array lengths/types do not isolate mutation coverage from read locality/order/lifetime.',
                    'New caller/workload classes require contemporaneous uniform anchors; no pooling with earlier traces.',
                    'Two repetitions are descriptive; compiler/host warnings and all contrary forks remain visible.']))
        if self.state.get('collectionComplete'):
            print('GEOMETRY_RETAINED_COLLECTION_VERIFIED',self.out,flush=True);return
        self.state.update(complete=True,collectionComplete=True,researchComplete=False,completedUtc=focus.now())
        self.checkpoint();print('GEOMETRY_COLLECTION_COMPLETE',self.out,len(rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('attempt');args=parser.parse_args()
    core.check(focus.evidence.re.fullmatch('[A-Za-z0-9._-]+',args.attempt),'Invalid attempt')
    validate();core.MAIN='io.github.enixes.tailcache.workload.GeometryCrossoverRunner'
    qualification='build/service-geometry-20261117/functional-validation.json'
    inputs=[qualification,'build/service-geometry-20261117/compilation.json',
            'build/service-policy-trace-20261117/compilation.json','build/service-policy-trace-20261117/policy-functional-validation.json']
    design=dict(kind='equal-array-trace-pattern-v1',maxWorkloadJvms=8,controls=4,functionalValidationJvms=1,
        functionalValidationReceipt=qualification,schedule=schedule(),warmupMs=60000,conditioningMs=4000,
        measureMs=30000,processTimeoutSeconds=180,primaryEndpoint='scheduled-response p99.9 under equal trace-array geometry',
        protocol='docs/TAILCACHE_SERVICE_GEOMETRY_PROTOCOL.md',discoveryInputs={p:focus.sha(ROOT/p) for p in inputs})
    out=ROOT/'evidence-archives'/args.attempt
    status_path=ROOT/'docs/TAILCACHE_SERVICE_STATUS.json';status=focus.load(status_path)
    status.update(phase='GEOMETRY_RUNNING',updatedUtc=focus.now(),running=dict(attempt=args.attempt))
    focus.save(status_path,status)
    Geometry(out,design=design,classpath_file=ROOT/'build/service-geometry-20261117/classpath.txt').run()
    for label,script,extra in [('raw','tailcache12_service_audit.py',[]),
            ('mechanism','tailcache12_service_mechanism.py',['--out',str(out/'mechanism-audit-001/report.json')])]:
        command=[sys.executable,str(ROOT/'scripts'/script),args.attempt,*extra]
        receipt=out/('postprocess-'+label+'.json')
        if receipt.exists():
            core.check(focus.load(receipt)['exitCode']==0,'Earlier geometry postprocess failure retained')
            artifact=out/('independent-audit-001/audit.json' if label=='raw' else 'mechanism-audit-001/report.json')
            verified=focus.load(artifact)
            core.check(verified.get('passed') is True and verified['studySha256']==focus.sha(out/'study.json'),
                       'Geometry audit/study mismatch')
            continue
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        core.immutable(receipt,dict(command=command,exitCode=result.returncode,stdout=result.stdout,stderr=result.stderr))
        core.check(result.returncode==0,'Geometry '+label+' audit failed; preserve evidence')
    destination=out/'mechanism-audit-001'
    if not (destination/'auditor.py').exists():
        shutil.copyfile(ROOT/'scripts/tailcache12_service_mechanism.py',destination/'auditor.py')
    core.immutable(destination/'receipt.json',dict(passed=True,auditorSha256=focus.sha(destination/'auditor.py'),
        reportSha256=focus.sha(destination/'report.json')))
    status=focus.load(status_path)
    status.update(phase='FINAL_RESEARCH_REVIEW_PENDING',updatedUtc=focus.now(),running=None,
                  geometry=dict(directory=str(out.relative_to(ROOT)),collectionComplete=True,rawAuditPassed=True,
                                mechanismAuditPassed=True,researchReviewComplete=False))
    focus.save(status_path,status)
    print('GEOMETRY_AUDITS_COMPLETE',flush=True)
