import base64,gzip,json,unittest
from tailcache12_tail_curves import summarize,lower_equivalent,classify_rates


class TailCurveTest(unittest.TestCase):
    def test_hdr_equivalence_width_and_strict_exceedance(self):
        self.assertEqual(lower_equivalent(100031),99968)
        tail=summarize([dict(upperEquivalentNs=100000-33,count=7),dict(upperEquivalentNs=100031,count=3),dict(upperEquivalentNs=100095,count=2)],12)
        rate=tail['rates']['100000']
        self.assertEqual((rate['lowerCount'],rate['upperCount']),(2,5))

    def test_curve_roundtrip_conserves_every_bin_and_count(self):
        tail=summarize([dict(upperEquivalentNs=99967,count=7),dict(upperEquivalentNs=100031,count=3)],10)
        self.assertEqual(json.loads(gzip.decompress(base64.b64decode(tail['curve']))),[99967,7,100031,3])
        self.assertEqual(tail['rates']['100000']['lowerCount'],0)
        self.assertEqual(tail['rates']['100000']['upperCount'],3)

    def test_zero_and_empty_are_different(self):
        nonempty=summarize([dict(upperEquivalentNs=100,count=1000)],1000)
        empty=summarize([],0)
        self.assertEqual(nonempty['rates']['100000']['upperProbability'],0)
        self.assertEqual(nonempty['empiricalResolution'],.001)
        self.assertIsNone(empty['rates']['100000']['upperProbability'])
        self.assertIsNone(empty['empiricalResolution'])

    def test_unequal_counts_compare_probabilities_not_raw_counts(self):
        c=dict(lowerCount=10,upperCount=10,count=100)
        h=dict(lowerCount=20,upperCount=20,count=1000)
        self.assertEqual(classify_rates([(c,h)]*3)['winner'],'chronicle')

    def test_overlapping_bounds_are_unresolved(self):
        c=dict(lowerCount=10,upperCount=20,count=1000)
        h=dict(lowerCount=15,upperCount=25,count=1000)
        self.assertEqual(classify_rates([(c,h)]*3)['winner'],'unresolved')

    def test_zero_events_are_equal_observed_rates_not_a_winner(self):
        c=dict(lowerCount=0,upperCount=0,count=100)
        h=dict(lowerCount=0,upperCount=0,count=1000)
        self.assertEqual(classify_rates([(c,h)]*3)['winner'],'tie')

    def test_mixed_pairs_are_not_replaced_by_a_pooled_average(self):
        c=dict(lowerCount=10,upperCount=10,count=100)
        h=dict(lowerCount=5,upperCount=5,count=100)
        self.assertEqual(classify_rates([(c,h),(c,h),(h,c)])['winner'],'mixed')


if __name__=='__main__':unittest.main()
