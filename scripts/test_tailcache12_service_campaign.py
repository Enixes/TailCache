import copy
import unittest
import tailcache12_service_campaign as service


def row(spec, ratio=1):
    r = dict(spec, status='OK', latencyVerified=True, warnings=[], trace={'traceSha256':'fixed'})
    r['latency'] = {c:dict(count=100,percentilesNs={p:100*(ratio if spec['backend']=='CHRONICLE_IN_MEMORY' else 1)
                                                for p in service.PERCENTILES})
                    for c in service.CHANNELS[:-1]}
    return r


class ServiceCampaignTest(unittest.TestCase):
    def test_screen_is_bounded_balanced_and_reproducible(self):
        specs=service.screen_schedule()
        self.assertEqual(specs,service.screen_schedule())
        self.assertEqual(len(specs),20)
        self.assertEqual(len({s['label'] for s in specs}),20)
        for p in service.PAYLOADS:
            for live in (0,208):
                pair=[s for s in specs if (s['payload'],s['liveMiB'])==(p,live)]
                self.assertEqual({r['backend'] for r in pair},set(service.BACKENDS))
                self.assertEqual({r['qps'] for r in pair},{0})

    def test_baseline_advantage_does_not_create_pressure_bracket(self):
        p=[dict(valid=True,liveMiB=0,ratio=.8),dict(valid=True,liveMiB=208,ratio=.7)]
        self.assertIsNone(service.pressure_bracket(p))

    def test_pressure_and_payload_confirmation_are_distinct(self):
        rows=[]
        for live,ratio in [(0,1.3),(208,.7)]:
            rows += [row(s,ratio) for s in service.pair_specs('screen',1024,live)]
        self.assertEqual(service.select_confirmation(rows,1024)['kind'],'pressure')
        rows=[]
        for payload,ratio in [(512,.7),(1024,1.3)]:
            rows += [row(s,ratio) for s in service.pair_specs('screen',payload,0)]
        selected=service.select_confirmation(rows,1024)
        self.assertEqual(selected['kind'],'payload')
        self.assertEqual({e['liveMiB'] for e in selected['endpoints']},{0})

    def test_failed_arm_cannot_become_a_latency_winner(self):
        rows=[row(s,.5) for s in service.pair_specs('screen',1024,208)]
        rows[1]['status']='OOM_SETUP'
        pair=service.pairs(rows)[0]
        self.assertFalse(pair['valid'])
        self.assertNotIn('ratio',pair)

    def test_confirmation_cannot_change_discovery_selection(self):
        rows=[]
        for payload,ratio in [(512,.7),(1024,1.3)]:
            rows += [row(s,ratio) for s in service.pair_specs('screen',payload,0)]
        before=service.select_confirmation(rows,1024)
        rows += [row(s,.001) for s in service.pair_specs('confirmation',4096,400)]
        self.assertEqual(service.select_confirmation(rows,1024),before)

    def test_failed_intermediate_payload_cannot_be_bridged(self):
        rows=[]
        for payload,ratio in [(512,.7),(1024,1),(2048,1.3)]:
            pair=[row(s,ratio) for s in service.pair_specs('screen',payload,0)]
            if payload==1024:pair[0]['status']='OOM_SETUP'
            rows+=pair
        self.assertEqual(service.select_confirmation(rows,2048)['kind'],'none')

    def test_probe_cap_and_failure_stop_are_enforced(self):
        p=[dict(valid=True,liveMiB=208,ratio=1.2,caffeineHeapFraction=.7)]
        self.assertLessEqual(service.next_pressure(p,4096,3),348)
        p.append(dict(valid=False,liveMiB=340))
        self.assertIsNone(service.next_pressure(p,4096,1))

    def test_duplicate_backend_is_an_error_and_warnings_are_preserved(self):
        rows=[row(s,.8) for s in service.pair_specs('screen',512,0)]
        rows[0]['warnings']=['compiler warning']
        original=copy.deepcopy(rows)
        self.assertTrue(service.pairs(rows)[0]['warnings']['CAFFEINE'])
        self.assertEqual(original,rows)
        with self.assertRaisesRegex(ValueError,'Duplicated backend'):
            service.pairs(rows+[rows[0]])


if __name__=='__main__':unittest.main()
