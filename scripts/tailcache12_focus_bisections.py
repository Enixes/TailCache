#!/usr/bin/env python3
"""Final24 targeted slots, followed by synthesis rather than more grid expansion."""
import subprocess,sys
import tailcache12 as evidence

def main():
    source=evidence.source_hash()
    stages=[('focused-rq1-response-bracket-20261108-001',['--payload','4096','--live','208','248','--passes','3','--regimes','arrival','--warmup-ms','12000','--measure-ms','30000','--budget-seconds','720']),
        ('focused-rq1-capacity-edge-20261108-001',['--payload','4096','--live','368','--passes','3','--regimes','closed','--budget-seconds','300']),
        ('focused-rq2-reverse-bracket-20261108-001',['--payload','256','--live','472','--passes','3','--regimes','closed','--budget-seconds','300'])]
    for attempt,args in stages:
        if evidence.source_hash()!=source:raise ValueError('Source changed; preserve completed bisections')
        command=[sys.executable,str(evidence.ROOT/'scripts/tailcache12_focused.py'),attempt,*args]
        if (evidence.ROOT/'evidence-archives'/attempt).exists():command.append('--resume')
        result=subprocess.run(command,cwd=evidence.ROOT)
        print('FOCUS_BISECTION_FINISHED '+attempt+' exit='+str(result.returncode),flush=True)
if __name__=='__main__':main()
