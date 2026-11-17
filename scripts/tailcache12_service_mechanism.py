#!/usr/bin/env python3
"""Independent raw GC/event reconciliation and per-operation tail-mixture diagnostics."""
import argparse,bisect,collections,csv,hashlib,json,math,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text())
def rows(p):
 with p.open() as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(test,msg):
 if not test:raise ValueError(msg)
def overlap(a,b,c,d):return max(0,min(b,d)-max(a,c))
def raw_pauses(path,a,b):
 pending={};found=[]
 for line in path.open():
  m=re.search(r"\[([0-9]+)ns\]\[info\]\[([^]]+)\]\s+GC\(([0-9]+)\) (.*)",line)
  if not m:continue
  t=int(m[1]);tag=m[2].strip();gid=m[3];msg=m[4]
  if tag=="gc,start" and msg.startswith("Pause "):
   require((gid,msg) not in pending,"Duplicate GC start");pending[gid,msg]=t
  end=re.fullmatch(r"(Pause .+?)\s+([0-9.]+)ms",msg)
  if tag!="gc" or not end:continue
  heap=re.search(r"[0-9.]+[BKMGT]->[0-9.]+[BKMGT]\([0-9.]+[BKMGT]\)",end[1])
  kind=end[1][:heap.start()].strip() if heap else end[1]
  key=(gid,kind)
  if key not in pending and kind.endswith(" (Evacuation Failure)"):key=(gid,kind[:-len(" (Evacuation Failure)")])
  duration=round(float(end[2])*1000000);explicit=key in pending;start=pending.pop(key,t-duration)
  if overlap(start,t,a,b):found.append(dict(gcId=gid,kind=kind,startNs=start,endNs=t,loggedDurationNs=duration,startDerivedFromDuration=not explicit))
 require(not pending,"Unmatched GC starts")
 return found

def exceedance(distribution,threshold):
 definite=possible=total=0
 for upper,count in distribution.items():
  step=1<<max(0,upper.bit_length()-11)
  lower=upper-step+1
  total+=count
  if lower>threshold:definite+=count
  if upper>threshold:possible+=count
 return dict(thresholdNs=threshold,countLower=definite,countUpper=possible,operations=total,probabilityLower=definite/total,probabilityUpper=possible/total)

def analyze(base,row):
 directory=base/"slots"/row["label"];w=next(x for x in row["windows"] if x["phase"]=="MEASUREMENT")
 a,b=int(w["startNs"]),int(w["endNs"]);n=int(w["operations"])
 raw=raw_pauses(directory/"gc-through-measurement.log",a,b)
 retained=load(directory/"measured-gc.json")["pauses"]
 fields=("gcId","kind","startNs","endNs","loggedDurationNs","startDerivedFromDuration")
 require([{k:p[k] for k in fields} for p in raw]==[{k:p[k] for k in fields} for p in retained],"Raw GC timestamps differ: "+row["label"])
 events=[tuple(int(r[k]) for k in ("previousEndNs","operationStartNs","operationEndNs")) for r in rows(directory/"worker/stalls.csv")]
 require(len(events)==min(int(w["stallEvents"]),10000),"Event count")
 require(int(w["unexportedStallEvents"])==0,"Incomplete event export; cannot claim complete join")
 require(all(a<=p<=s<=e<=b and e-p>=1000000 for p,s,e in events),"Invalid sparse event interval")
 require(all(left[2]<=right[0] for left,right in zip(events,events[1:])),"Overlapping sparse event envelopes")
 ends=[e for p,s,e in events];large=[p for p in raw if overlap(p["startNs"],p["endNs"],a,b)>=1000000]
 service=gap=duration=0;affected=set();mapped=[]
 for pause in large:
  x,y=max(a,pause["startNs"]),min(b,pause["endNs"]);duration+=y-x
  i=bisect.bisect_right(ends,x);call=outside=0
  while i<len(events) and events[i][0]<y:
   prev,start,end=events[i];z=overlap(x,y,start,end);call+=z;outside+=overlap(x,y,prev,start)
   if z:affected.add(i)
   i+=1
  service+=call;gap+=outside
  mapped.append(dict(gcId=pause["gcId"],startNs=x,endNs=y,serviceOverlapNs=call,gapOverlapNs=outside,unmappedNs=y-x-call-outside))
 require(service+gap<=duration,"Double-counted event overlap")
 distributions={channel:{int(r["upperEquivalentNs"]):int(r["count"]) for r in rows(directory/"worker"/(channel+"-bins.csv"))} for channel in ("service","read-service","update-service")}
 require(sum(distributions["service"].values())==n,"Service count")
 union=collections.Counter(distributions["read-service"]);union.update(distributions["update-service"])
 require(dict(union)==distributions["service"],"Mixture bin union")
 boundary=row["latency"]["service"]["percentilesNs"]["99.9"]
 counts={c:sum(v for u,v in d.items() if u>boundary) for c,d in distributions.items()}
 require(counts["service"]==counts["read-service"]+counts["update-service"],"Mixture tail conservation")
 measurement=row["measurement"];allocated=int(w["workerAllocatedBytes"]);writes=int(w["writes"])
 payloadFloor=(n if row["backend"]=="CHRONICLE_IN_MEMORY" else writes)*row["payload"]
 demand=int(w["churnPayloadBytes"]);dropped=int(w["churnDroppedBytes"])
 return dict(label=row["label"],stage=row["stage"],backend=row["backend"],payload=row["payload"],liveMiB=row["liveMiB"],seed=row["seed"],block=row["block"],operations=n,writes=writes,
  percentilesNs=row["latency"]["service"]["percentilesNs"],warnings=row["warnings"],
  workerAllocatedBytes=allocated,minimumPayloadAllocationBytes=payloadFloor,materializationFloorPassed=allocated>=payloadFloor,
  churnPayloadBytes=demand,churnDroppedBytes=dropped,churnLostDemandFraction=dropped/(demand+dropped) if demand+dropped else 0,
  achievedChurnPayloadBytesPerSecond=measurement["achievedChurnPayloadBytesPerSecond"],
  gcPauseExposureFraction=row["gc"]["pauseExposureFraction"],postGcHeapFraction=row["gc"]["postGcUsedHeapMedianFraction"],maxHumongousRegions=row["gc"]["maxHumongousRegionsAfter"],
  allGcPauseCount=len(raw),largeGcPauseCount=len(large),largeGcOverlapNs=duration,largeGcServiceOverlapNs=service,largeGcBetweenCallOverlapNs=gap,
  largeGcUnmappedNs=duration-service-gap,largeGcAffectedServiceCalls=len(affected),largeGcAffectedCallFraction=len(affected)/n,
  sparseStallEvents=len(events),unexportedStallEvents=0,eventJoin=mapped,
  serviceExceedance=[exceedance(distributions["service"],t) for t in (100000,1000000,10000000)],
  mixtureAboveP999=dict(boundaryUpperEquivalentNs=boundary,counts=counts,readShare=counts["read-service"]/counts["service"] if counts["service"] else None),
  inputSha256={str(p.relative_to(base)):sha(p) for p in (directory/"gc-through-measurement.log",directory/"measured-gc.json",directory/"worker/stalls.csv",directory/"worker/service-bins.csv",directory/"worker/read-service-bins.csv",directory/"worker/update-service-bins.csv",directory/"service-result.json")})

def main():
 parser=argparse.ArgumentParser();parser.add_argument("attempt");parser.add_argument("--out",type=pathlib.Path,required=True);args=parser.parse_args()
 base=ROOT/"evidence-archives"/args.attempt;study=load(base/"study.json");report=[]
 for row in study["observations"]:
  if row["status"]=="OK" and row.get("latencyVerified"):report.append(analyze(base,row))
 result=dict(passed=True,cohort=args.attempt,studySha256=sha(base/"study.json"),observations=report,
  limits=["GC interval overlap supports temporal attribution, not isolated causal heap placement.","Only GC overlaps at least 1ms are required to map to sparse 1ms-gap events. Smaller pauses remain in the raw GC count/exposure.","HDR three-significant-digit bin ambiguity gives strict exceedance probability bounds.","Affected service-call fraction is operation weighted; pause exposure is wall-time weighted. These denominators differ.","No operation type is inferred for individual sparse stall events.","All seeds, observers and discovery/confirmation stages remain separate."])
 args.out.parent.mkdir(parents=True,exist_ok=True)
 with args.out.open("x") as f:json.dump(result,f,indent=2);f.write("\n")
 print(json.dumps(dict(passed=True,observations=len(report),largeGcPauses=sum(r["largeGcPauseCount"] for r in report),largeGcUnmappedNs=sum(r["largeGcUnmappedNs"] for r in report),materializationFloorFailures=sum(not r["materializationFloorPassed"] for r in report))))
if __name__=="__main__":main()
