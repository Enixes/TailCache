#!/usr/bin/env python3
"""Prospectively bounded extension after the retained 20-JVM service screen."""
import argparse
import pathlib
import random

import tailcache12_service_campaign as core
import tailcache12_focused as focus

ROOT=core.ROOT
DISCOVERY='evidence-archives/service-followup-20261117-001'
PAYLOADS=(512,1024,2048,4096)


def matrix(stage,passes,seed,order_seed):
    schedule=[]
    for block in range(1,passes+1):
        cells=[(p,live) for p in PAYLOADS for live in (0,208)]
        random.Random(order_seed+block).shuffle(cells)
        for index,(payload,live) in enumerate(cells):
            schedule+=core.pair_specs(stage,payload,live,block=block,seed=seed,reverse=bool((index+block)%2))
    return schedule


def pressure_schedule():
    cells=[(p,live) for p in (2048,4096) for live in (240,272,304,336)]
    random.Random(24317).shuffle(cells)
    return [s for index,(p,live) in enumerate(cells)
            for s in core.pair_specs('pressure-discovery',p,live,reverse=bool(index%2))]


def choice_from_discovery(original,new_rows):
    points=core.pairs(original)+core.pairs([r for r in new_rows if r['stage']=='pressure-discovery'])
    choices=[]
    for payload in (2048,4096):
        bracket=core.pressure_bracket([p for p in points if p['payload']==payload])
        if bracket:
            a,b=bracket
            choices.append((b['liveMiB']-a['liveMiB'],payload,a['liveMiB'],a,b))
    if not choices:return dict(kind='none',endpoints=[])
    chosen=min(choices,key=lambda c:c[:3])
    return dict(kind='pressure',endpoints=[dict(payload=p['payload'],liveMiB=p['liveMiB']) for p in chosen[-2:]],
                discoveryRatios=[p['ratio'] for p in chosen[-2:]])


def design():
    paths=[ROOT/DISCOVERY/p for p in ('study.json','protocol.json','independent-audit-001/audit.json')]
    return dict(kind='service-rq-extension-v1',maxWorkloadJvms=96,
                protocol='docs/TAILCACHE_SERVICE_RQ_EXTENSION_PROTOCOL.md',
                discoveryInputs={str(p.relative_to(ROOT)):focus.sha(p) for p in paths},
                pressureSchedule=pressure_schedule(),
                primarySchedule=matrix('payload-confirmation',3,24301,24310),
                holdoutSchedule=matrix('payload-holdout',1,24302,24320),
                adaptiveConfirmationMaximumJvms=16)


class Extension(core.Campaign):
    def run(self):
        old_protocol=focus.load(ROOT/DISCOVERY/'protocol.json')
        core.check(self.protocol['runtimeSha256']==old_protocol['runtimeSha256'],
                   'Extension must retain exactly the screen Java runtime')
        self.run_controls()
        plan=self.protocol['design']
        self.execute(plan['pressureSchedule'])
        self.execute(plan['primarySchedule'])
        self.execute(plan['holdoutSchedule'])
        old=focus.load(ROOT/DISCOVERY/'study.json')['observations']
        choice=choice_from_discovery(old,self.observations())
        self.decision('pressure-confirmation-selection',choice)
        if choice['endpoints']:
            cells=[(b,e) for b in (1,2,3) for e in choice['endpoints']]
            random.Random(24330).shuffle(cells)
            for index,(block,e) in enumerate(cells):
                self.execute(core.pair_specs('pressure-confirmation',e['payload'],e['liveMiB'],
                                            block=block,reverse=bool(index%2)))
            for index,e in enumerate(choice['endpoints']):
                self.execute(core.pair_specs('pressure-holdout',e['payload'],e['liveMiB'],
                                            seed=24302,reverse=bool(index%2)))
        self.check_frozen()
        core.report(self.out,self.observations(),choice)
        self.state.update(complete=True,collectionComplete=True,researchComplete=False,
                          completedUtc=focus.now(),newWorkloadJvms=len(self.observations()),
                          confirmationKind=choice['kind'],sourceUnchanged=True)
        self.checkpoint()
        print('SERVICE_EXTENSION_COLLECTION_COMPLETE',self.out,len(self.observations()),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('attempt');args=parser.parse_args()
    core.check(focus.evidence.re.fullmatch('[A-Za-z0-9._-]+',args.attempt),'Invalid attempt')
    Extension(ROOT/'evidence-archives'/args.attempt,design=design()).run()
