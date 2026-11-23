import unittest
import tailcache12_service_extension as extension
import tailcache12_service_campaign as core


class ExtensionTest(unittest.TestCase):
    def test_fixed_schedules_fit_the_declared_budget(self):
        pressure=extension.pressure_schedule()
        primary=extension.matrix('payload-confirmation',3,24301,24310)
        holdout=extension.matrix('payload-holdout',1,24302,24320)
        self.assertEqual((len(pressure),len(primary),len(holdout)),(16,48,16))
        all_slots=pressure+primary+holdout
        self.assertEqual(len({s['label'] for s in all_slots}),80)
        self.assertEqual(len(all_slots)+16,96)
        self.assertEqual({s['liveMiB'] for s in pressure},{240,272,304,336})

    def test_seed_and_stage_identity_are_not_pooled(self):
        primary=extension.matrix('payload-confirmation',3,24301,24310)
        holdout=extension.matrix('payload-holdout',1,24302,24320)
        self.assertEqual({r['seed'] for r in primary},{24301})
        self.assertEqual({r['seed'] for r in holdout},{24302})
        self.assertEqual({r['block'] for r in primary},{1,2,3})

    def test_confirmation_cannot_select_itself(self):
        # Stage filtering is the barrier against feeding favourable repetitions into discovery.
        rows=[dict(stage='payload-confirmation',payload=2048,liveMiB=336,seed=24301,block=1,
                   backend='CAFFEINE',status='OOM_SETUP',latencyVerified=False,warnings=[])]
        self.assertEqual(extension.choice_from_discovery([],rows)['kind'],'none')


if __name__=='__main__':unittest.main()
