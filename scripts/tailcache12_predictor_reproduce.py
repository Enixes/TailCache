#!/usr/bin/env python3
"""Replay frozen M2 from portable GC/schedule inputs, without retained raw archives."""
import argparse,hashlib,json,pathlib,runpy,time
import tailcache12_predictor_verify as verify

def main():
 p=argparse.ArgumentParser();p.add_argument('package',type=pathlib.Path);p.add_argument('--solver',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args();d=json.loads(a.package.read_text());verify.verify(d)
 params=d['models']['drain'];digest=hashlib.sha256(a.solver.read_bytes()).hexdigest();assert digest==params['solverSha256']==d['modelInputs']['drain_candidate.py.txt']
 solver=runpy.run_path(str(a.solver));checked=0;started=time.monotonic()
 for r in d['forks']:
  if 'M2' not in r['predictionNs']:continue
  service=solver['interpolate'](params['intrinsicServiceNs'][r['backend']],r['writeBps'])
  sim=solver['simulate'](r['pauseIntervalsNsRelative'],0,r['offeredWindowNs'],1_000_000_000//r['qps'],service,params['bookkeepingNs'][r['backend']],verify.Q)
  for q in verify.Q:
   assert sim['percentilesNs'][q]+params['timerBaselineNs'][q]==r['predictionNs']['M2'][q],r['id']+' q'+q
   checked+=1
  assert sim==r['simulation'],r['id']+' simulation mismatch'
 result={'passed':True,'packageSha256':hashlib.sha256(a.package.read_bytes()).hexdigest(),'solverSha256':digest,'forks':checked//4,'quantiles':checked,'elapsedSeconds':time.monotonic()-started,'rawArchivesRead':False,'independentAlgorithm':False,'meaning':'Exact replay of frozen M2 on portable GC/schedule inputs; independent verifier separately reconstructs M0/M1 and errors.'}
 a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
