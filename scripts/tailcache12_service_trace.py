#!/usr/bin/env python3
"""Fixed matched-arrival baseline trace and longer-warmup sensitivity."""
import argparse
import random
import tailcache12_service_campaign as core
import tailcache12_focused as focus

ROOT=core.ROOT


def schedule():
    cells=[(trace,block) for trace in (40001,1000003) for block in (1,2)]
    random.Random(24380).shuffle(cells)
    slots=[]
    for i,(trace,block) in enumerate(cells):
        pair=core.pair_specs('trace-'+str(trace),4096,0,block=block,reverse=bool((i+block)%2))
        for row in pair:row.update(traceOperations=trace,regime='arrival',qps=50000)
        slots+=pair
    return slots


class Trace(core.Campaign):
    def run_controls(self):
        for label,payload,floor,supply,inject in [('timer',256,True,False,0),
                ('injected-stall',256,True,False,20),('supply256',256,False,True,0),
                ('supply4096',4096,False,True,0)]:
            row=core.pair_specs('trace-control-'+label,payload,0,block=0)[0]
            row.update(traceOperations=1000003,regime='arrival',qps=50000,residents=64,churnMiB=0,
                       floor=floor,supply=supply,inject=inject)
            r=self.execute([row],control=True)[0]
            core.check(r['status']=='OK' and r['measurement']['operations']==200000,'Trace control conservation')
            if inject:
                core.check(r['latency']['service']['maxNs']>=15000000 and
                           r['latency']['response']['percentilesNs']['99.9']>=1000000,'Injected trace-loop pause visibility')

    def run(self):
        self.run_controls();self.execute(self.protocol['design']['schedule']);self.check_frozen()
        rows=self.observations();pairs=core.pairs(rows);by={r['label']:r for r in rows}
        for r in rows:
            if r['status']=='OK':
                expected={'WARMUP':3000000,'CONDITIONING':200000,'MEASUREMENT':1500000}
                core.check(all(int(w['scheduled'])==int(w['operations'])==expected[w['phase']] for w in r['windows']),
                           'Every trace phase must complete its intended operations')
        for p in pairs:
            if not p['valid']:continue
            c,h=[by[p['labels'][b]] for b in core.BACKENDS]
            core.check([(w['phase'],w['writes']) for w in c['windows']]==[(w['phase'],w['writes']) for w in h['windows']],
                       'Paired trace-phase write counts differ')
            p['ratios']['response']={q:h['latency']['response']['percentilesNs'][q]/c['latency']['response']['percentilesNs'][q]
                                    for q in core.PERCENTILES if c['latency']['response']['percentilesNs'][q]}
        core.check(len(rows)==8 and len(pairs)==4,'Fixed trace budget')
        core.immutable(self.out/'study.json',dict(kind='baseline-trace-longer-warmup-sensitivity',collectionComplete=True,
            observations=rows,pairs=pairs,workloadJvms=8,
            primary='scheduled-response p99.9 at baseline, with matched longer warmup',
            limits=['Trace length changes sequence/coverage/lifetime and primitive-array footprint together.',
                    'Only baseline is tested; two pairs are descriptive, not a crossover interval.']))
        self.state.update(complete=True,collectionComplete=True,researchComplete=False,
                          completedUtc=focus.now(),newWorkloadJvms=len(rows))
        self.checkpoint();print('TRACE_COLLECTION_COMPLETE',self.out,len(rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('attempt');args=parser.parse_args()
    core.check(focus.evidence.re.fullmatch('[A-Za-z0-9._-]+',args.attempt),'Invalid attempt name')
    core.MAIN='io.github.enixes.tailcache.workload.TraceSensitivityRunner'
    compilation='build/service-policy-trace-20261117/compilation.json'
    qualification='build/service-policy-trace-20261117/trace-functional-validation.json'
    core.validate_compilation(ROOT/compilation,ROOT/qualification,'trace')
    design=dict(kind='baseline-trace-longer-warmup-v1',maxWorkloadJvms=8,controls=4,functionalValidationJvms=1,
        functionalValidationReceipt=qualification,schedule=schedule(),warmupMs=60000,conditioningMs=4000,
        measureMs=30000,processTimeoutSeconds=180,traceOperations='per-slot:40001-or-1000003',
        primaryEndpoint='scheduled-response p99.9 at baseline by trace design under 60-second warmup',
        protocol='docs/TAILCACHE_SERVICE_TRACE_PROTOCOL.md',
        discoveryInputs={p:focus.sha(ROOT/p) for p in (compilation,qualification,
            'evidence-archives/service-followup-20261117-001/protocol.json',
            'evidence-archives/service-followup-20261117-001/independent-audit-001/audit.json')})
    Trace(ROOT/'evidence-archives'/args.attempt,design=design,
          classpath_file=ROOT/'build/service-policy-trace-20261117/classpath.txt').run()
