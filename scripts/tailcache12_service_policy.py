#!/usr/bin/env python3
"""Fixed cache-policy sensitivity, with unchanged timed operation boundary."""
import argparse
import collections
import random
import tailcache12_service_campaign as core
import tailcache12_focused as focus

ROOT=core.ROOT
ARMS=('CAFFEINE','CAFFEINE_BOUNDED_DIRECT','CAFFEINE_UNBOUNDED','CHRONICLE_IN_MEMORY')


def schedule():
    slots=[]
    cells=[(payload,block) for payload in (512,4096) for block in (1,2)]
    random.Random(24370).shuffle(cells)
    for i,(payload,block) in enumerate(cells):
        rotation=i%len(ARMS)
        arms=ARMS[rotation:]+ARMS[:rotation]
        if block==2:arms=arms[::-1]
        for backend in arms:
            row=core.pair_specs('policy',payload,0,block=block)[0]
            row.update(backend=backend,label=f'policy-p{payload}-live0-b{block}-s24301-{backend}')
            slots.append(row)
    return slots


def comparisons(rows):
    grouped=collections.defaultdict(dict)
    for row in rows:
        key=(row['payload'],row['liveMiB'],row['seed'],row['block'])
        core.check(row['backend'] not in grouped[key],'Duplicated policy arm')
        grouped[key][row['backend']]=row
    pairs=[]
    for key,arms in sorted(grouped.items()):
        core.check(set(arms)==set(ARMS),'Incomplete four-arm policy block')
        for reference in ARMS[:-1]:
            chosen={reference:arms[reference],'CHRONICLE_IN_MEMORY':arms['CHRONICLE_IN_MEMORY']}
            valid=all(core.usable(r) for r in chosen.values())
            pair=dict(stage='policy',payload=key[0],liveMiB=key[1],seed=key[2],block=key[3],
                comparison=reference,referenceBackend=reference,comparisonBackend='CHRONICLE_IN_MEMORY',
                valid=valid,labels={b:r['label'] for b,r in chosen.items()},
                warnings={b:r['warnings'] for b,r in chosen.items()},ratios={})
            if valid:
                core.check(len({r['trace']['traceSha256'] for r in chosen.values()})==1,'Paired policy traces differ')
                for channel in core.CHANNELS[:-1]:
                    c,h=[chosen[b]['latency'][channel]['percentilesNs'] for b in (reference,'CHRONICLE_IN_MEMORY')]
                    pair['ratios'][channel]={p:h[p]/c[p] for p in core.PERCENTILES if c[p]}
                pair['ratio']=pair['ratios']['service']['99.9']
            pairs.append(pair)
    return pairs


class Policy(core.Campaign):
    def run(self):
        self.run_controls()
        self.execute(self.protocol['design']['schedule']);self.check_frozen()
        rows=self.observations();pairs=comparisons(rows)
        core.check(len(rows)==16 and len(pairs)==12,'Fixed policy budget')
        core.immutable(self.out/'study.json',dict(kind='cache-policy-sensitivity',collectionComplete=True,
            observations=rows,pairs=pairs,workloadJvms=len(rows),
            limits=['Unbounded Caffeine changes the capacity/policy/layout contract.',
                    'Shared Chronicle anchors make the three within-block contrasts dependent.',
                    'Two repetitions are descriptive; no pooling with previous cohorts.']))
        self.state.update(complete=True,collectionComplete=True,researchComplete=False,
                          completedUtc=focus.now(),newWorkloadJvms=len(rows))
        self.checkpoint();print('POLICY_COLLECTION_COMPLETE',self.out,len(rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('attempt');args=parser.parse_args()
    core.check(focus.evidence.re.fullmatch('[A-Za-z0-9._-]+',args.attempt),'Invalid attempt name')
    compilation='build/service-policy-trace-20261117/compilation.json'
    qualification='build/service-policy-trace-20261117/policy-functional-validation.json'
    core.validate_compilation(ROOT/compilation,ROOT/qualification,'policy')
    design=dict(kind='cache-policy-sensitivity-v1',maxWorkloadJvms=16,controls=4,functionalValidationJvms=1,
        functionalValidationReceipt=qualification,schedule=schedule(),
        primaryEndpoint='ordinary 95/5 combined saturated-service p99.9 by declared cache policy',
        protocol='docs/TAILCACHE_SERVICE_POLICY_PROTOCOL.md',
        discoveryInputs={p:focus.sha(ROOT/p) for p in (compilation,qualification,
            'evidence-archives/service-followup-20261117-001/protocol.json',
            'evidence-archives/service-followup-20261117-001/independent-audit-001/audit.json')})
    Policy(ROOT/'evidence-archives'/args.attempt,design=design,
           classpath_file=ROOT/'build/service-policy-trace-20261117/classpath.txt').run()
