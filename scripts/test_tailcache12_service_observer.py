import collections
import unittest
import tailcache12_service_observer as observer
import tailcache12_service_campaign as core


class ObserverTest(unittest.TestCase):
    def test_fixed_matrix_balances_two_forks_without_pooling(self):
        slots=observer.schedule()
        self.assertEqual(slots,observer.schedule())
        self.assertEqual(len(slots),24)
        self.assertEqual(len({s['label'] for s in slots}),24)
        grouped=collections.defaultdict(list)
        for s in slots:
            self.assertEqual((s['seed'],s['regime']),(24301,'JMH-SampleTime'))
            grouped[s['payload'],s['liveMiB'],s['block']].append(s)
        self.assertEqual(len(grouped),12)
        for pair in grouped.values():
            self.assertEqual({s['backend'] for s in pair},set(core.BACKENDS))

    def test_rank_uses_retained_samples_not_completed_operations(self):
        self.assertEqual(observer.rank({10:99900,20:100},99.9),10)
        self.assertEqual(observer.rank({10:99900,20:100},99.99),20)
        sampled=observer.sample_distribution([[10.,2],[20.,1]],1000000)
        self.assertEqual(sum(sampled.values()),3)
        self.assertEqual(observer.rank(sampled,99.9),20)

    def test_invalid_or_impossible_raw_samples_are_rejected(self):
        for bins,operations in (([],10),([[1.,11]],10),([[1.5,1]],10),
                                ([[1.,0]],10),([[-1.,1]],10),([[float('inf'),1]],10)):
            with self.assertRaises(ValueError):
                observer.sample_distribution(bins,operations)


if __name__=='__main__':unittest.main()
