#!/usr/bin/env python3
"""Bounded fresh midpoint/seed cohorts. Resume slots, never replace observations."""
import argparse
import json
import pathlib
import subprocess
import sys

import tailcache12 as evidence
import tailcache12_focused as focus


def adaptive_midpoint(summary):
    """Use all three clean pairs; mixed/incomplete evidence never drives bisection."""
    directions={}
    for row in summary['comparisons']:
        pairs=row['passes']
        if len(pairs)!=3 or any(not p['usable'] or any(p['warnings'].values()) for p in pairs):return None
        ratios=[p['ratios']['response']['99.9'] for p in pairs]
        directions[row['liveMiB']]='caffeine' if min(ratios)>1 else 'chronicle' if max(ratios)<1 else 'mixed'
    if directions=={0:'caffeine',104:'chronicle',208:'chronicle'}:return 52
    if directions=={0:'caffeine',104:'caffeine',208:'chronicle'}:return 156
    return None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',default='midpoint-study-20261110-001')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    if not evidence.re.fullmatch('[A-Za-z0-9._-]+',args.study):parser.error('Invalid study label')
    root=evidence.ROOT/'evidence-archives'/args.study
    source=evidence.source_hash()
    if root.exists():
        if not args.resume:raise ValueError('Study exists; use resume rather than overwrite')
        state=focus.load(root/'state.json')
        if state['sourceSha256']!=source:raise ValueError('Frozen source changed; preserve study')
    else:
        root.mkdir()
        protected={str(p.relative_to(evidence.ROOT)):focus.sha(p) for p in (evidence.ROOT/'evidence-archives').glob('focused-rq*-delivery-20261108-001.tar.gz')}
        state=dict(kind='bounded-midpoint-follow-up',sourceSha256=source,declaredUtc=focus.now(),
            maximumWorkloadForks=36,replacements=0,complete=False,stages=[],historicalDeliveries=protected,
            plan='docs/TAILCACHE_MIDPOINT_EXECUTION_PLAN.md',adaptiveBallastMiB=None)
        focus.save(root/'state.json',state)

    def stage(label,levels,passes,seed):
        if evidence.source_hash()!=source:raise ValueError('Source changed during collection')
        attempt=args.study+'-'+label
        directory=evidence.ROOT/'evidence-archives'/attempt
        command=[sys.executable,str(evidence.ROOT/'scripts/tailcache12_focused.py'),attempt,
            '--payload','4096','--live',*[str(x) for x in levels],'--passes',str(passes),'--regimes','arrival',
            '--seed',str(seed),'--warmup-ms','12000','--conditioning-ms','2000','--measure-ms','30000',
            '--budget-seconds','1500']
        if directory.exists():command.append('--resume')
        code=subprocess.run(command,cwd=evidence.ROOT).returncode
        summary=focus.load(directory/'summary.json') if (directory/'summary.json').exists() else None
        receipt=dict(label=label,attempt=attempt,seed=seed,levelsMiB=levels,passes=passes,exitCode=code,
            completed=bool(code==0 and summary and summary['completeCollection']),
            collected=summary['collected'] if summary else None,updatedUtc=focus.now())
        state['stages']=[x for x in state['stages'] if x['label']!=label]+[receipt]
        focus.save(root/'state.json',state)
        if not receipt['completed']:raise RuntimeError('Stage incomplete; resume preserved slots: '+attempt)
        return summary

    primary=stage('primary',[0,104,208],3,24301)
    stage('seed24302',[0,104,208],1,24302)
    stage('seed24303',[0,104,208],1,24303)
    middle=adaptive_midpoint(primary)
    state['adaptiveBallastMiB']=middle
    state['adaptiveDecision']='one clean consistent bracket; adaptive exploration' if middle else 'no three-pair clean bracket; no adaptive collection'
    focus.save(root/'state.json',state)
    if middle is not None:stage('adaptive'+str(middle),[middle],3,24301)
    for path,wanted in state['historicalDeliveries'].items():
        if focus.sha(evidence.ROOT/path)!=wanted:raise ValueError('Historical delivery changed: '+path)
    if evidence.source_hash()!=source:raise ValueError('Source changed during follow-up')
    state.update(complete=True,completedUtc=focus.now(),sourceUnchanged=True,
        collectedWorkloadForks=sum(x['collected'] for x in state['stages']))
    focus.save(root/'state.json',state)
    print('MIDPOINT_COLLECTION_COMPLETE '+json.dumps(state),flush=True)


if __name__=='__main__':main()
