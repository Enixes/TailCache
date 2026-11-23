import unittest
import tailcache12_service_large_payload as large


def pair(live,c,h,valid=True):
    return dict(liveMiB=live,valid=valid,ratio=h/c,selectionCounts=dict(caffeine=c,chronicle=h),warnings={})


class LargePayloadTest(unittest.TestCase):
    def test_pilot_is_four_workloads_and_alternates_backends(self):
        slots=large.pilot_schedule()
        self.assertEqual(len(slots),4)
        self.assertEqual(len({s['label'] for s in slots}),4)
        self.assertEqual({s['payload'] for s in slots},{8192})
        self.assertEqual({s['liveMiB'] for s in slots},{0,208})
        self.assertNotEqual(slots[0]['backend'],slots[2]['backend'])

    def test_pressure_worth_rule_includes_exact_boundary_without_float_error(self):
        decision=large.select([pair(0,1000,1200),pair(208,1000,1080)])
        self.assertEqual(decision['kind'],'pressure')
        slots=large.confirmation_schedule(decision)
        self.assertEqual(len(slots),8)
        self.assertEqual(len({s['label'] for s in slots}),8)
        self.assertEqual({s['payload'] for s in slots},{8192})

    def test_baseline_advantage_selects_payload_question(self):
        decision=large.select([pair(0,1000,800),pair(208,1000,700)])
        self.assertEqual(decision['kind'],'payload')
        slots=large.confirmation_schedule(decision)
        self.assertEqual(len(slots),8)
        self.assertEqual({s['payload'] for s in slots},{4096,8192})
        self.assertEqual({s['liveMiB'] for s in slots},{0})

    def test_failure_cannot_select_a_favorable_surviving_arm(self):
        decision=large.select([pair(0,1000,500),pair(208,1000,700,False)])
        self.assertEqual(decision['kind'],'none')
        self.assertEqual(large.confirmation_schedule(decision),[])

    def test_unpromising_primary_stops_regardless_of_other_percentiles(self):
        decision=large.select([pair(0,1000,1200),pair(208,1000,1250)])
        self.assertEqual(decision['kind'],'none')


if __name__=='__main__':unittest.main()
