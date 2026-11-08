#!/usr/bin/env python3
"""Last narrow refinements for the observed RQ tradeoffs; no large matrix."""
import subprocess,sys
import tailcache12 as evidence

def main():
    source=evidence.source_hash()
    stages=[('focused-rq1-response-long-20261108-001',['--payload','4096','--live','0','288','--passes','3','--regimes','arrival','--warmup-ms','12000','--measure-ms','30000','--budget-seconds','720']),
        ('focused-rq1-capacity-20261108-001',['--payload','4096','--live','364','--passes','3','--regimes','closed','--budget-seconds','300']),
        ('focused-rq2-midpoint-20261108-001',['--payload','256','--live','464','--passes','3','--regimes','closed','--budget-seconds','300']),
        ('focused-reuse-256-20261108-001',['--payload','256','--live','480','--passes','3','--reuse','--budget-seconds','480']),
        ('focused-reuse-4k-20261108-001',['--payload','4096','--live','352','--passes','3','--regimes','arrival','--reuse','--budget-seconds','300'])]
    for attempt,args in stages:
        if evidence.source_hash()!=source:raise ValueError('Source changed; preserve completed refinements')
        command=[sys.executable,str(evidence.ROOT/'scripts/tailcache12_focused.py'),attempt,*args]
        if (evidence.ROOT/'evidence-archives'/attempt).exists():command.append('--resume')
        result=subprocess.run(command,cwd=evidence.ROOT)
        print('FOCUS_REFINEMENT_FINISHED '+attempt+' exit='+str(result.returncode),flush=True)

if __name__=='__main__':main()
