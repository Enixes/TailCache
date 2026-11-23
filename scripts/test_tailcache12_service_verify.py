import copy
import json
import pathlib
import unittest
import tailcache12_service_verify as verify


class PortableResearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=json.loads((pathlib.Path(__file__).resolve().parents[1]/
            'docs/service-followup/followup-data-20261117.json').read_text())

    def test_complete_portable_package_reconciles(self):
        result=verify.verify(self.original)
        self.assertEqual(result['counts']['forks'],184)
        self.assertEqual(result['counts']['distributions'],704)
        self.assertEqual(result['counts']['quantileEndpoints'],3520)

    def test_empty_comparisons_cannot_pass(self):
        data=dict(self.original,pairs=[])
        with self.assertRaisesRegex(ValueError,'Empty research'):verify.verify(data)

    def test_missing_curve_channel_is_rejected(self):
        data=copy.deepcopy(self.original)
        channels=next(iter(data['curves']['directory'].values()))
        channels.pop(next(iter(channels)))
        with self.assertRaises(ValueError):verify.verify(data)

    def test_jmh_sample_count_cannot_be_relabelled_as_all_operations(self):
        data=copy.deepcopy(self.original)
        row=next(r for r in data['forks'] if r['cohort']=='observer')
        row['latency']['service']['count']=row['measurement']['operations']
        with self.assertRaises(ValueError):verify.verify(data)

    def test_changed_ratio_is_rejected(self):
        data=copy.deepcopy(self.original)
        next(iter(data['pairs'][0]['ratios'].values()))['99.9']*=2
        with self.assertRaisesRegex(ValueError,'Paired ratio'):verify.verify(data)

    def test_changed_stall_rate_is_rejected(self):
        data=copy.deepcopy(self.original)
        row=next(r for r in data['forks'] if 'mechanism' in r)
        row['mechanism']['serviceExceedance'][0]['countUpper']+=1
        with self.assertRaisesRegex(ValueError,'threshold bounds'):verify.verify(data)

    def test_point_cannot_be_relabelled_to_another_treatment(self):
        data=copy.deepcopy(self.original)
        data['points'][0]['liveMiB']+=1
        with self.assertRaisesRegex(ValueError,'Point label'):verify.verify(data)


if __name__=='__main__':unittest.main()
