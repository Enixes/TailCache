#!/usr/bin/env python3
"""Three bounded follow-ups selected from the completed24-fork discovery batch."""
import pathlib,subprocess,sys
import tailcache12 as evidence

def main():
    source=evidence.source_hash()
    stages=[('focused-rq1-response-low-20261108-001',['--payload','4096','--live','0','288','--passes','3','--regimes','arrival','--budget-seconds','600']),
        ('focused-rq1-service-edge-20261108-001',['--payload','4096','--live','360','--passes','3','--regimes','closed','--budget-seconds','300']),
        ('focused-rq2-256-20261108-001',['--payload','256','--live','448','480','--passes','3','--budget-seconds','1200'])]
    for attempt,args in stages:
        if evidence.source_hash()!=source:raise ValueError('Source changed between follow-ups; preserve completed work')
        command=[sys.executable,str(evidence.ROOT/'scripts/tailcache12_focused.py'),attempt,*args]
        if (evidence.ROOT/'evidence-archives'/attempt).exists():command.append('--resume')
        result=subprocess.run(command,cwd=evidence.ROOT)
        print('FOCUS_FOLLOWUP_FINISHED '+attempt+' exit='+str(result.returncode),flush=True)
    if evidence.source_hash()!=source:raise ValueError('Source changed during follow-ups')

if __name__=='__main__':main()
