#!/usr/bin/env python3
"""One exclusive native scope: qualification/audits then frozen validation/scoring."""
import argparse,json,pathlib,subprocess,sys
import tailcache12_focused as f
ROOT=f.evidence.ROOT
STATUS=ROOT/'docs/TAILCACHE_PREDICTOR_STATUS.json'
def step(out,name,args,artifact):
    receipt=out/(name+'.json')
    if receipt.exists():
        r=f.load(receipt)
        if r['exitCode']!=0:raise ValueError('Prior failed step retained; explicit adjudication needed: '+str(receipt))
        if not artifact.exists():raise ValueError('Missing completed artifact '+str(artifact))
        if r['artifactSha256']!=f.sha(artifact):raise ValueError('Retained step artifact changed')
        print('PREDICTOR_RETAINED_STEP',name,flush=True);return
    command=[sys.executable,str(ROOT/'scripts'/args[0]),*args[1:]]
    print('PREDICTOR_STEP',name,flush=True)
    with (out/(name+'.stdout')).open('x') as stdout,(out/(name+'.stderr')).open('x') as stderr:
        result=subprocess.run(command,cwd=ROOT,stdout=stdout,stderr=stderr)
    f.save(receipt,dict(command=command,exitCode=result.returncode,completedUtc=f.now(),artifactSha256=f.sha(artifact) if artifact.exists() else None))
    if result.returncode:raise ValueError('Sequence step failed; retain all evidence: '+name)

def main():
    p=argparse.ArgumentParser();p.add_argument('attempt');p.add_argument('--qualification',required=True);p.add_argument('--validation',required=True);a=p.parse_args()
    for value in (a.attempt,a.qualification,a.validation):
        if not f.evidence.re.fullmatch('[A-Za-z0-9._-]+',value):raise ValueError('Attempt')
    out=ROOT/'evidence-archives'/a.attempt;out.mkdir(exist_ok=True)
    for stage,attempt in [('qualification',a.qualification),('validation',a.validation)]:
        base=ROOT/'evidence-archives'/attempt
        command=['tailcache12_predictor_campaign.py',stage,attempt]+(['--qualification-attempt',a.qualification] if stage=='validation' else [])
        step(out,stage,command,base/'study.json')
        step(out,stage+'-raw',['tailcache12_predictor_audit.py',attempt],base/'independent-audit-001/audit.json')
        step(out,stage+'-mechanism',['tailcache12_service_mechanism.py',attempt,'--out',str(base/'mechanism-audit-001/report.json')],base/'mechanism-audit-001/report.json')
        step(out,stage+'-predict',['tailcache12_predictor_score.py','predict',attempt],base/'predictions-v1.json')
        step(out,stage+'-score',['tailcache12_predictor_score.py','score',attempt],base/'score-v1.json')
        status=f.load(STATUS);status[stage]=dict(attempt=attempt,collectionComplete=True,rawAuditPassed=True,mechanismAuditPassed=True,score=str((base/'score-v1.json').relative_to(ROOT)))
        status.update(phase='QUALIFIED_AWAITING_VALIDATION' if stage=='qualification' else 'COLLECTED_AND_SCORED_REVIEW_PENDING',running=None,updatedUtc=f.now());f.save(STATUS,status)
    f.save(out/'complete.json',dict(collectionAndAuditsComplete=True,completedUtc=f.now(),qualification=a.qualification,validation=a.validation,researchComplete=False))
    print('PREDICTOR_SEQUENCE_COMPLETE',flush=True)
if __name__=='__main__':main()
