#!/usr/bin/env python3
"""Four-JVM larger-value worth pilot with at most one frozen eight-JVM follow-up."""
import argparse
import random
import shutil
import subprocess
import sys
import tailcache12_service_campaign as core
import tailcache12_focused as focus

ROOT=core.ROOT
CP=ROOT/'build/service-policy-trace-20261117/classpath.txt'


def pilot_schedule():
    return [row for i,live in enumerate((0,208))
            for row in core.pair_specs('large-pilot',8192,live,reverse=bool(i%2))]


def select(pairs):
    points={p['liveMiB']:p for p in pairs}
    if set(points)!={0,208} or not all(p['valid'] for p in points.values()):
        return dict(kind='none',reason='Incomplete/failed pair; no latency winner or expansion.')
    low,high=points[0]['ratio'],points[208]['ratio']
    c0,h0=[points[0]['selectionCounts'][k] for k in ('caffeine','chronicle')]
    ch,hh=[points[208]['selectionCounts'][k] for k in ('caffeine','chronicle')]
    result=dict(kind='none',baselineRatio=low,highRatio=high,relativePressureRatio=high/low,
                discoveryWarnings={str(k):p['warnings'] for k,p in points.items()},
                selectionCounts={str(k):p['selectionCounts'] for k,p in points.items()})
    if h0>=c0 and 10*hh<=11*ch and 10*hh*c0<=9*h0*ch:
        result.update(kind='pressure',endpoints=[dict(payload=8192,liveMiB=live) for live in (0,208)])
    elif 10*h0<=9*c0:
        result.update(kind='payload',endpoints=[dict(payload=p,liveMiB=0) for p in (4096,8192)])
    else:result['reason']='Frozen p99.9 worth rule not met; retain results and stop.'
    return result


def confirmation_schedule(choice):
    if choice['kind']=='none':return []
    cells=[(p,block) for p in choice['endpoints'] for block in (1,2)]
    random.Random(24401).shuffle(cells)
    return [row for i,(cell,block) in enumerate(cells)
            for row in core.pair_specs('large-confirmation-'+choice['kind'],cell['payload'],cell['liveMiB'],
                                       block=block,reverse=bool((i+block)%2))]


class Experiment(core.Campaign):
    def run_controls(self):
        controls=[('timer',8192,True,False,0),('injected-stall',8192,True,False,20)]
        controls += [('supply'+str(p),p,False,True,0) for p in self.protocol['design']['controlPayloads']]
        for label,payload,floor,supply,inject in controls:
            row=core.pair_specs('large-control-'+label,payload,0,block=0)[0]
            row.update(residents=64,churnMiB=0,floor=floor,supply=supply,inject=inject)
            r=self.execute([row],control=True)[0]
            core.check(r['status']=='OK' and r['latencyVerified'],'Large-payload control failed')
            if inject:core.check(r['latency']['service']['maxNs']>=15000000,'Injected service pause not visible')

    def run(self):
        self.run_controls();self.execute(self.protocol['design']['schedule']);self.check_frozen()
        rows=self.observations();pairs=core.pairs(rows)
        core.check(len(rows)==self.protocol['maxWorkloadJvms'],'Fixed large-payload workload budget')
        core.immutable(self.out/'study.json',dict(kind=self.protocol['design']['kind'],collectionComplete=True,
            observations=rows,pairs=pairs,workloadJvms=len(rows),primary='ordinary combined saturated-service p99.9',
            limits=['Separate discovery/confirmation and phase regimes; no pooled percentiles.',
                    'One/two paired repetitions are descriptive, not significance or an exact universal threshold.']))
        if self.state.get('collectionComplete'):
            print('LARGE_RETAINED_COLLECTION_VERIFIED',self.out,flush=True);return
        self.state.update(complete=True,collectionComplete=True,researchComplete=False,completedUtc=focus.now(),
                          newWorkloadJvms=len(rows));self.checkpoint()
        print('LARGE_COLLECTION_COMPLETE',self.out,len(rows),flush=True)


def audit(attempt):
    base=ROOT/'evidence-archives'/attempt
    for label,script,extra in [('raw','tailcache12_service_audit.py',[]),
            ('mechanism','tailcache12_service_mechanism.py',['--out',str(base/'mechanism-audit-001/report.json')])]:
        command=[sys.executable,str(ROOT/'scripts'/script),attempt,*extra]
        receipt=base/('postprocess-'+label+'.json')
        if receipt.exists():
            core.check(focus.load(receipt)['exitCode']==0,'Earlier postprocess failure retained');continue
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        core.immutable(receipt,dict(command=command,exitCode=result.returncode,stdout=result.stdout,stderr=result.stderr))
        core.check(result.returncode==0,'Large-payload '+label+' audit failed; inspect retained receipt')
    destination=base/'mechanism-audit-001'
    if not (destination/'auditor.py').exists():shutil.copyfile(ROOT/'scripts/tailcache12_service_mechanism.py',destination/'auditor.py')
    core.immutable(destination/'receipt.json',dict(passed=True,auditorSha256=focus.sha(destination/'auditor.py'),
                                                 reportSha256=focus.sha(destination/'report.json')))


def design(kind,schedule,warmup=12000,conditioning=2000,measure=10000,extra_inputs=None):
    compilation='build/service-policy-trace-20261117/compilation.json'
    qualification='build/service-policy-trace-20261117/policy-functional-validation.json'
    core.validate_compilation(ROOT/compilation,ROOT/qualification,'policy')
    inputs={p:focus.sha(ROOT/p) for p in (compilation,qualification,
        'evidence-archives/service-followup-20261117-001/protocol.json',
        'evidence-archives/service-followup-20261117-001/independent-audit-001/audit.json')}
    inputs.update(extra_inputs or {})
    payloads=sorted({s['payload'] for s in schedule})
    return dict(kind=kind,schedule=schedule,maxWorkloadJvms=len(schedule),controls=2+len(payloads),
        controlPayloads=payloads,functionalValidationJvms=0,functionalValidationReceipt=qualification,
        warmupMs=warmup,conditioningMs=conditioning,measureMs=measure,processTimeoutSeconds=180,
        primaryEndpoint='ordinary 95/5 combined saturated-service p99.9 at larger payload',
        protocol='docs/TAILCACHE_SERVICE_LARGE_PAYLOAD_PROTOCOL.md',discoveryInputs=inputs)


def status(phase,attempt=None):
    p=ROOT/'docs/TAILCACHE_SERVICE_STATUS.json';d=focus.load(p)
    d.update(phase=phase,updatedUtc=focus.now(),running=dict(attempt=attempt) if attempt else None)
    focus.save(p,d)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('pilot');parser.add_argument('--confirmation',required=True)
    args=parser.parse_args()
    for name in (args.pilot,args.confirmation):core.check(focus.evidence.re.fullmatch('[A-Za-z0-9._-]+',name),'Invalid attempt')
    core.check(args.pilot!=args.confirmation,'Distinct evidence directories required')
    status('LARGE_PAYLOAD_PILOT_RUNNING',args.pilot)
    out=ROOT/'evidence-archives'/args.pilot
    Experiment(out,design=design('large-payload-worth-pilot-v1',pilot_schedule()),classpath_file=CP).run()
    audit(args.pilot)
    study=focus.load(out/'study.json');by={r['label']:r for r in study['observations']}
    for pair in study['pairs']:
        if pair['valid']:
            pair['selectionCounts']={name:by[pair['labels'][backend]]['latency']['service']['percentilesNs']['99.9']
                for name,backend in [('caffeine','CAFFEINE'),('chronicle','CHRONICLE_IN_MEMORY')]}
    choice=select(study['pairs'])
    core.immutable(out/'worth-decision.json',dict(choice,primary='service p99.9',pilotStudySha256=focus.sha(out/'study.json'),
        pilotRawAuditSha256=focus.sha(out/'independent-audit-001/audit.json')))
    print('LARGE_WORTH_DECISION',choice,flush=True)
    if choice['kind']!='none':
        status('LARGE_PAYLOAD_CONFIRMATION_RUNNING',args.confirmation)
        inputs={str(p.relative_to(ROOT)):focus.sha(p) for p in (out/'study.json',out/'independent-audit-001/audit.json',out/'worth-decision.json')}
        Experiment(ROOT/'evidence-archives'/args.confirmation,design=design('large-payload-confirmation-v1',
            confirmation_schedule(choice),60000,4000,30000,inputs),classpath_file=CP).run()
        audit(args.confirmation)
    status('FINAL_RESEARCH_REVIEW_PENDING')
    print('LARGE_PAYLOAD_SCOPE_COMPLETE',flush=True)
