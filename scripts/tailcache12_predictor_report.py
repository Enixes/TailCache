#!/usr/bin/env python3
"""Rebuild every-point/model tables from the portable predictor dataset."""
import collections,csv,json,pathlib,re
import tailcache12_predictor_verify as verify
ROOT=pathlib.Path(__file__).resolve().parents[1];BASE=ROOT/'docs/predictor'
def main():
 d=json.loads((BASE/'predictor-data-20261118.json').read_text());checks=verify.verify(d);fs={r['id']:r for r in d['forks']}
 lines=['# Continuous-stream write-rate and pause-model results — 18 November 2026','',
 'The fixed study is complete: **18 qualification +30 primary +12 fresh secondary research JVMs**. Four controls, three functional JVMs and one compiler-only diagnostic are separate. All raw/mechanism audits pass. Warnings and the failed steady-state qualification remain; completion is not unconditional acceptance. Earlier datasets and the original Task12 NO_GO are unchanged.','',
 '## Research conclusions','',
 '**A response reversal exists; a stable write-rate boundary was not established.** At zero application ballast, all three primary pairs favor Caffeine at0% writes and Chronicle at0.5–5%. The two fresh secondary pairs repeat0%/5% endpoint directions but disagree at0.5%. The original0.5–2% before-run bracket forecast failed in the primary study. The updated0.5% replication forecast also failed (5/6 pair directions overall). Keep the contrary fresh fork, including its compiler warning. Neither warning-bearing outcome is removed.','',
 'This is **scheduled response** under fixed arrival demand, not a saturated ordinary-service crossing and not an isolated causal effect of value placement. One host, OpenJDK21.0.13.0.3+1, G1,512MiB heap,4KiB values,32768 residents,50k intended arrivals/s, zero extra ballast and common32MiB/s churn bound the inference. No additional payload-pressure matrix is implied.','',
 '**Conditional GC information explains winner directions more reliably than an ex ante write-ratio bracket.** M1 and M2 call15/15 primary and6/6 fresh p99.9 pairs correctly, including the contrary fresh0.5% outcome. The lower-total-pause rule also scores15/15 and6/6. Thus winner accuracy does not demonstrate superiority of the residual-pause equation over this simple baseline. Constant backend calls and abstentions are retained in the package.','',
 '**Queue-drain modeling improves aggregate numerical error, but is not uniformly better.** M2 improves median/p90 absolute p99.9 error in both primary and fresh cohorts. Its fresh Chronicle median relative error is56.9%; the constant pilot-quantile comparator is better for Chronicle (40.6%). Primary Chronicle gives65.1% versus28.1%. The successful aggregate comparison hides this backend asymmetry unless reported separately. Conditional reconstruction reads measured GC; it does not predict future pauses or provide latency guarantees.','',
 '**The experiment remains finite-window/transient-qualified.** The120-second pilot still failed the declared half-window occupancy criterion at0.5% writes (52.64%→41.31% heap). Warning-bearing research forks:3/18 pilot,10/30 primary (nine compiler, one outside-CPU),3/12 fresh. Both fresh0.5% pairs include a Chronicle compiler warning; Caffeine GC overlap differs (32.526 versus28.675ms), near the ideal30ms p99.9 pause budget. That association is consistent with the model, not a unique causal attribution.','',
 'The one separately instrumented compiler probe observes phase-exit deoptimization and a conditioning recompile, but no large measurement-period compiler delta. It cannot erase nine original warnings. See [compiler interpretation](COMPILER_DIAGNOSTIC.md) and [narrow extracted evidence](compiler-diagnostic-summary.json). No extra replacement or collector/skew/payload sweep was launched after the fixed confirmation.','',
 '## Paired response p99.9 results','',
 'Each range spans individual fork quantiles, never a pooled quantile or confidence interval. Cohorts remain separate.','',
 '| Cohort | Writes % | Warmup s | Pairs | Caffeine µs range | Chronicle µs range | Ch/C ratios | Direction |',
 '| --- | ---: | ---: | ---: | --- | --- | --- | --- |']
 for cohort in ('qualification','validation','confirmation'):
  groups=collections.defaultdict(list)
  for p in d['pairs']:
   if p['cohort']==cohort:groups[p['writeBps'],p['warmupMs']].append(p)
  for (w,warm),ps in sorted(groups.items()):
   vals=[[fs[p[key]]['latency']['response']['percentilesNs']['99.9']/1000 for p in ps] for key in ('c','h')];rs=[p['ratios']['response']['99.9'] for p in ps];direction='Chronicle lower' if max(rs)<1 else 'Caffeine lower' if min(rs)>1 else 'Mixed'
   lines.append(f"| {cohort} | {w/100:g} | {warm/1000:g} | {len(ps)} | {min(vals[0]):.3f}–{max(vals[0]):.3f} | {min(vals[1]):.3f}–{max(vals[1]):.3f} | {', '.join(f'{r:.4f}' for r in rs)} | {direction} |")
 lines+=['','## All-fork response p99.9 numerical error','','No below-budget, small or warning-bearing outcome is excluded. Constant quantiles were specified after primary outcomes, before fresh confirmation; primary comparison is retrospective. M2 was frozen after pilot and before primary unblinding.','','| Cohort / subset | Model | N | Median absolute µs | p90 absolute µs | Median relative % | p90 relative % |','| --- | --- | ---: | ---: | ---: | ---: | ---: |']
 for cohort in ('validation','confirmation'):
  for subset in ('all','CAFFEINE','CHRONICLE_IN_MEMORY'):
   for method in ('M0','M1','M2','constant'):
    e=d['numerical'][cohort][subset][method]['99.9'];lines.append(f"| {cohort} / {subset} | {method} | {e['n']} | {e['medianAbsoluteNs']/1000:.3f} | {e['p90AbsoluteNs']/1000:.3f} | {e['medianRelativeError']*100:.2f} | {e['p90RelativeError']*100:.2f} |")
 lines+=['','## Every comparison group','','Every row keeps its seed, phase duration and cohort. The CSV additionally supplies all channels and p50/p99/p99.9/p99.99/p99.999.','', '| Cohort | Writes % | Warmup s | Seed | Block | p99.9 Ch/C | p99.99 Ch/C | p99.999 Ch/C | Warning-free pair |','| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
 for p in d['pairs']:
  r=p['ratios']['response'];lines.append(f"| {p['cohort']} | {p['writeBps']/100:g} | {p['warmupMs']/1000:g} | {p['seed']} | {p['block']} | {r['99.9']:.5f} | {r['99.99']:.5f} | {r['99.999']:.5f} | {p['warningFree']} |")
 lines+=['','## Reproduction and boundaries','',
 'The portable package contains60 research forks,284 nonempty distributions,1420 exact percentile reconstructions,710 paired ratios and710 point conclusions. Empty update channels at0% are intentional. Independent portable checks conserve60 read/update unions,180 threshold rates,720 M0/M1/constant values and220 numerical summaries. The separate replay reproduces all168 M2 values across42 holdout forks from portable GC/schedule inputs using the frozen solver, not an independent implementation. Raw audits independently decode320 research/control HDR files and reconcile source/runtime, stream continuity, writes, GC and sampled RSS. The diagnostic is not counted in those cohort audits.','',
 'See [protocol](../TAILCACHE_PREDICTOR_PLAN.md), [secondary protocol](../TAILCACHE_PREDICTOR_CONFIRMATION_PROTOCOL.md), [portable verification](portable-verification.json), [model replay](model-replay.json), [figures](FIGURES.md), [working manuscript](../preprint/MANUSCRIPT.md) and [final researcher review](REVIEW.md). Dataset: `predictor-data-20261118.json`. Frozen models and stream code are preserved in committed source and per-cohort archives. Retained model-worth fields describe the consumed single expansion decision; they do not authorize another12 forks.','',
 'This is an agent-reviewed working artifact, not independent peer review, an author-approved preprint, a public raw-evidence deposit or a clean-machine performance replication. Rare tails share stall episodes. No general exact threshold, object-lifetime isolation, total-memory saving or universal cache-selection rule is supported.']
 text='\n'.join(lines)+'\n'
 text=re.sub(r'\b(at|by|the|all|Task|OpenJDK|primary|fresh|pilot|qualification|holdout|cohort|plus)(?=\d)',r'\1 ',text)
 (BASE/'RESULTS.md').write_text(text)
 with (BASE/'point-conclusions.csv').open('w') as f:
  w=csv.writer(f);w.writerow(['cohort','writeBps','warmupMs','seed','block','channel','percentile','caffeineNs','chronicleNs','ChOverC','direction','warningFree'])
  for p in d['pairs']:
   for channel,qs in p['ratios'].items():
    for q,ratio in qs.items():w.writerow([p['cohort'],p['writeBps'],p['warmupMs'],p['seed'],p['block'],channel,q,fs[p['c']]['latency'][channel]['percentilesNs'][q],fs[p['h']]['latency'][channel]['percentilesNs'][q],ratio,'Chronicle lower' if ratio<1 else 'Caffeine lower' if ratio>1 else 'Equal',p['warningFree']])
 with (BASE/'fork-model-errors.csv').open('w') as f:
  w=csv.writer(f);w.writerow(['id','cohort','backend','writeBps','warmupMs','seed','percentile','model','measuredNs','predictedNs','absoluteErrorNs','relativeError','warningBearing'])
  for r in d['forks']:
   for method,qs in r['predictionNs'].items():
    for q,pred in qs.items():
     measured=r['latency']['response']['percentilesNs'][q];w.writerow([r['id'],r['cohort'],r['backend'],r['writeBps'],r['warmupMs'],r['seed'],q,method,measured,pred,abs(pred-measured),abs(pred-measured)/measured,bool(r['warnings'])])
 print(json.dumps(checks['counts']))
if __name__=='__main__':main()
