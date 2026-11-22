import unittest
from tailcache12_extreme_tails import extract


class ExtremeTailTest(unittest.TestCase):
    def test_one_in_one_hundred_thousand_boundary(self):
        bins=[dict(upperEquivalentNs=100,count=99999),dict(upperEquivalentNs=10000000,count=1)]
        values,support=extract(bins,100000)
        self.assertEqual(values['99.999'],100)
        self.assertEqual(support['99.999'],dict(rank=99999,selectedBinCount=99999,
            strictlyAboveSelectedBin=1,nominalUpperTailObservations=1.0))
        bins[0]['count']=99998;bins[1]['count']=2
        values,support=extract(bins,100000)
        self.assertEqual(values['99.999'],10000000)

    def test_empty_channel_is_missing_not_zero_latency(self):
        values,support=extract([],0)
        self.assertTrue(all(v is None for v in values.values()))
        self.assertIsNone(support['99.999']['rank'])

    def test_scheduled_windows_have_four_or_fifteen_nominal_observations(self):
        for count,tail in ((400000,4),(1500000,15)):
            _,support=extract([dict(upperEquivalentNs=100,count=count)],count)
            self.assertEqual(support['99.999']['nominalUpperTailObservations'],tail)

    def test_count_mismatch_is_rejected(self):
        with self.assertRaises(AssertionError):extract([dict(upperEquivalentNs=100,count=5)],6)

    def test_unsorted_or_duplicate_bins_are_rejected(self):
        for values in ((100,90),(100,100)):
            with self.assertRaises(AssertionError):extract([dict(upperEquivalentNs=v,count=1) for v in values],2)


if __name__=='__main__':unittest.main()
