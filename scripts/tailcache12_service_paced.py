#!/usr/bin/env python3
"""Fixed matched-arrival service/response diagnostic; same retained Java runtime."""
import argparse
import csv
import random
import tailcache12_service_campaign as core
import tailcache12_focused as focus

ROOT=core.ROOT
REFERENCE='evidence-archives/service-followup-20261117-001'


def schedule():
    slots=[]
    for block in (1,2):
        cells=[(p,live) for p in (256,4096) for live in (0,208,336)]
        random.Random(24350+block).shuffle(cells)
        for index,(payload,live) in enumerate(cells):
            pair=core.pair_specs('paced-load',payload,live,block=block,reverse=bool((block+index)%2))
            for row in pair:row.update(regime='arrival',qps=50000)
            slots+=pair
    return slots


class Paced(core.Campaign):
    def run_controls(self):
        for label,payload,floor,supply,inject in [('timer',256,True,False,0),
                ('injected-stall',256,True,False,20),('supply256',256,False,True,0),
                ('supply4096',4096,False,True,0)]:
            s=core.pair_specs('paced-control-'+label,payload,0,block=0)[0]
            s.update(regime='arrival',qps=50000,residents=64,churnMiB=0,floor=floor,supply=supply,inject=inject)
            result=self.execute([s],control=True)[0]
            core.check(result['status']=='OK' and result['measurement']['operations']==200000,
                       'Paced control conservation')
            if inject:
                core.check(result['latency']['response']['percentilesNs']['99.9']>=1000000,
                           'Injected queue debt not visible')
                core.check(result['latency']['service']['maxNs']>=15000000,
                           'Injected service pause not visible')

    def run(self):
        old=focus.load(ROOT/REFERENCE/'protocol.json')
        core.check(self.protocol['runtimeSha256']==old['runtimeSha256'],'Paced check must use identical measured Java runtime')
        self.run_controls();self.execute(self.protocol['design']['schedule']);self.check_frozen()
        rows=self.observations();by={r['label']:r for r in rows};pairs=core.pairs(rows)
        for r in rows:
            if r['status']=='OK':
                core.check(r['measurement']['scheduled']==r['measurement']['operations']==1500000,
                           'Incomplete paced measurement cannot be a complete distribution')
        for p in pairs:
            if not p['valid']:continue
            c,h=[by[p['labels'][b]] for b in core.BACKENDS]
            core.check(c['measurement']['writes']==h['measurement']['writes'],'Paired writes differ')
            p['ratios']['response']={q:h['latency']['response']['percentilesNs'][q]/c['latency']['response']['percentilesNs'][q]
                                     for q in core.PERCENTILES if c['latency']['response']['percentilesNs'][q]}
        core.immutable(self.out/'study.json',dict(kind='matched-arrival-load-and-payload-check',collectionComplete=True,
                       observations=rows,pairs=pairs,workloadJvms=len(rows),
                       primary='service p99.9 during fixed intended arrivals; scheduled response is a labelled follow-up',
                       limits=['Two paired repetitions per cell; no significance or exact-threshold claim.',
                               'No pooling with saturated service, old traces or other observer regimes.']))
        with (self.out/'pairs.csv').open('x',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['payload','ballastMiB','block','valid','serviceP999Ratio','responseP999Ratio','warnings'])
            for p in pairs:writer.writerow([p['payload'],p['liveMiB'],p['block'],p['valid'],
                p['ratios'].get('service',{}).get('99.9'),p['ratios'].get('response',{}).get('99.9'),str(p['warnings'])])
        self.state.update(complete=True,collectionComplete=True,researchComplete=False,completedUtc=focus.now(),
                          newWorkloadJvms=len(rows),sourceUnchanged=True)
        self.checkpoint();print('PACED_COLLECTION_COMPLETE',self.out,len(rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('attempt');args=parser.parse_args()
    core.check(focus.evidence.re.fullmatch('[A-Za-z0-9._-]+',args.attempt),'Invalid attempt name')
    paths=[ROOT/REFERENCE/p for p in ('protocol.json','independent-audit-001/audit.json')]
    design=dict(kind='matched-arrival-load-check-v1',maxWorkloadJvms=24,controls=4,functionalValidationJvms=0,
                primaryEndpoint='ordinary 95/5 combined service p99.9 at 50000 intended arrivals/s',
                schedule=schedule(),protocol='docs/TAILCACHE_SERVICE_PACED_PROTOCOL.md',
                discoveryInputs={str(p.relative_to(ROOT)):focus.sha(p) for p in paths})
    Paced(ROOT/'evidence-archives'/args.attempt,design=design).run()
