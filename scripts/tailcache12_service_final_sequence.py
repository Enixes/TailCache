#!/usr/bin/env python3
"""Run only the declared policy/trace cohorts and audits, serially and resumably."""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

import tailcache12_service_campaign as core
import tailcache12_focused as focus

ROOT=core.ROOT


def steps(policy,trace):
    return [(kind,attempt,script,arguments) for attempt in (policy,trace) for kind,script,arguments in (
        ('collection','tailcache12_service_policy.py' if attempt==policy else 'tailcache12_service_trace.py',[attempt]),
        ('raw-audit','tailcache12_service_audit.py',[attempt]),
        ('mechanism-audit','tailcache12_service_mechanism.py',[attempt,'--out',
            str(ROOT/'evidence-archives'/attempt/'mechanism-audit-001/report.json')]))]


def completed(kind,attempt,source):
    base=ROOT/'evidence-archives'/attempt
    if kind=='collection':
        if not (base/'study.json').exists() or not focus.load(base/'state.json').get('collectionComplete'):return False
        core.check(focus.load(base/'protocol.json')['sourceSha256']==source,'Frozen child source identity')
        study=focus.load(base/'study.json')
        for row in study['observations']:focus.verify_retained(base/'slots'/row['label'],row)
        for p in (base/'controls').glob('*/service-result.json'):focus.verify_retained(p.parent,focus.load(p))
        return True
    path=base/('independent-audit-001/audit.json' if kind=='raw-audit' else 'mechanism-audit-001/report.json')
    if not path.exists():return False
    result=focus.load(path)
    core.check(result.get('passed') is True and result['studySha256']==focus.sha(base/'study.json'),
               'Audit completion not matched to retained study')
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sequence');parser.add_argument('--policy',required=True);parser.add_argument('--trace',required=True)
    args=parser.parse_args()
    for name in (args.sequence,args.policy,args.trace):
        core.check(focus.evidence.re.fullmatch('[A-Za-z0-9._-]+',name),'Invalid attempt name')
    core.check(len({args.sequence,args.policy,args.trace})==3,'Distinct attempt identities required')
    core.check(focus.evidence.host_snapshot().get('nativeScopeQualified')==1,'Exclusive native scope required')
    out=ROOT/'evidence-archives'/args.sequence
    source,_=core.source_identity()
    declaration=dict(sourceSha256=source,policy=args.policy,trace=args.trace,
                     steps=[dict(kind=k,attempt=a,script=s,arguments=v) for k,a,s,v in steps(args.policy,args.trace)],
                     limits='Serial collection/audits only; final researcher review, docs and deployment remain pending.')
    out.mkdir(exist_ok=True)
    core.immutable(out/'sequence-protocol.json',declaration)
    state=focus.load(out/'state.json') if (out/'state.json').exists() else dict(completed=[],complete=False)
    for index,(kind,attempt,script,arguments) in enumerate(steps(args.policy,args.trace)):
        core.check(core.source_identity()[0]==source,'Frozen sequence source changed')
        key=f'{index+1:02d}-{kind}-{attempt}'
        if completed(kind,attempt,source):
            if key not in state['completed']:state['completed'].append(key)
            continue
        stdout=out/(key+'.stdout');stderr=out/(key+'.stderr')
        core.check(not stdout.exists() and not stderr.exists(),'Interrupted step logs retained; explicit adjudication required')
        state.update(running=key,updatedUtc=focus.now());focus.save(out/'state.json',state)
        status_path=ROOT/'docs/TAILCACHE_SERVICE_STATUS.json'
        status=focus.load(status_path)
        status.update(phase=('POLICY_' if attempt==args.policy else 'TRACE_')+kind.upper().replace('-','_'),
            updatedUtc=focus.now(),running=dict(sequence=str(out.relative_to(ROOT)),attempt=attempt,step=kind,
            nativeScope=os.environ.get('TAILCACHE_NATIVE_SCOPE')))
        focus.save(status_path,status)
        command=[sys.executable,str(ROOT/'scripts'/script),*arguments]
        print('SEQUENCE_START',key,flush=True)
        with stdout.open('x') as output,stderr.open('x') as error:
            result=subprocess.run(command,cwd=ROOT,stdout=output,stderr=error)
        core.immutable(out/(key+'.execution.json'),dict(command=command,exitCode=result.returncode,
            completedUtc=focus.now(),stdoutSha256=focus.sha(stdout),stderrSha256=focus.sha(stderr)))
        if result.returncode:
            state.update(failedStep=key,exitCode=result.returncode);focus.save(out/'state.json',state)
            raise RuntimeError('Sequence step failed; retained logs: '+key)
        core.check(completed(kind,attempt,source),'Child exited without a matched completion artifact')
        if kind=='mechanism-audit':
            destination=ROOT/'evidence-archives'/attempt/'mechanism-audit-001'
            shutil.copyfile(ROOT/'scripts/tailcache12_service_mechanism.py',destination/'auditor.py')
            core.immutable(destination/'receipt.json',dict(passed=True,
                auditorSha256=focus.sha(destination/'auditor.py'),reportSha256=focus.sha(destination/'report.json')))
        state['completed'].append(key);state.update(running=None,updatedUtc=focus.now());focus.save(out/'state.json',state)
        print('SEQUENCE_COMPLETE',key,flush=True)
    state.update(complete=True,collectionAndAuditsComplete=True,researchComplete=False,completedUtc=focus.now(),running=None)
    focus.save(out/'state.json',state)
    status_path=ROOT/'docs/TAILCACHE_SERVICE_STATUS.json';status=focus.load(status_path)
    status.update(phase='FINAL_RESEARCH_REVIEW_PENDING',updatedUtc=focus.now(),running=None,
                  finalSequence=dict(directory=str(out.relative_to(ROOT)),collectionAndAuditsComplete=True))
    focus.save(status_path,status)
    print('FINAL_COLLECTION_AND_AUDITS_COMPLETE',out,flush=True)


if __name__=='__main__':main()
