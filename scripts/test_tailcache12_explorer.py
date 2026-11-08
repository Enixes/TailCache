import json
import pathlib
import tempfile
import unittest
from tailcache12_build_explorer import SOURCE,OUTPUT,build_data,classify,PERCENTILES,load_study


class ExplorerEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=json.loads(load_study());cls.data=build_data(SOURCE)

    def test_every_retained_fork_and_nonempty_channel_is_represented(self):
        data=self.data
        self.assertEqual(len(data['forks']),132)
        self.assertEqual(len(data['groups']),56)
        self.assertEqual(sum(g['primary'] for g in data['groups']),22)
        represented={p[k] for g in data['groups'] for p in g['pairs'] for k in ('c','h')}
        self.assertEqual(represented,set(range(132)))

    def test_all_primary_pair_ratios_match_independent_retained_analysis(self):
        for expected in self.raw['comparisons']:
            group=next(g for g in self.data['groups'] if (g['batch'],g['ballast'],g['regime'],g['channel'])==(expected['batch'],expected['ballastMiB'],expected['regime'],expected['channel']))
            for p in PERCENTILES:
                self.assertEqual(group['conclusions'][p]['ratios'],[pair['ratios'][p] for pair in expected['pairs']])

    def test_percentile_reversal_at_baseline_is_preserved(self):
        g=next(g for g in self.data['groups'] if g['batch']=='focused-rq1-response-long-20261108-001' and g['ballast']==0 and g['channel']=='response')
        self.assertEqual(g['conclusions']['99.9']['winner'],'caffeine')
        self.assertEqual(g['conclusions']['99.99']['winner'],'chronicle')

    def test_reuse_never_borrows_caffeine_from_the_ordinary_comparison(self):
        for g in self.data['groups']:
            if g['contract']=='reuse':
                for p in g['pairs']:
                    c,h=self.data['forks'][p['c']],self.data['forks'][p['h']]
                    self.assertEqual(c['batch'],h['batch'])
                    self.assertTrue(c['batch'].startswith('focused-reuse'))
        g=next(g for g in self.data['groups'] if g['payload']==256 and g['contract']=='reuse' and g['channel']=='service' and g['regime']=='closed')
        self.assertEqual(g['conclusions']['99.9']['winner'],'chronicle')
        self.assertEqual(g['conclusions']['99.99']['winner'],'caffeine')

    def test_median_advantage_does_not_reclassify_mixed_pairs(self):
        self.assertEqual(classify([100,100,100],[50,60,150])['winner'],'mixed')
        self.assertEqual(classify([100,100,100],[100,100,100])['winner'],'tie')
        self.assertEqual(classify([100,100,100],[50,50,100])['winner'],'mixed')

    def test_grouping_does_not_mutate_retained_records(self):
        path=SOURCE if SOURCE.exists() else OUTPUT
        before=path.read_bytes();build_data(SOURCE);self.assertEqual(path.read_bytes(),before)

    def test_fresh_checkout_can_recover_identical_input_from_committed_html(self):
        with tempfile.TemporaryDirectory() as directory:
            recovered=load_study(pathlib.Path(directory)/'missing-study.json')
        self.assertEqual(json.loads(recovered),self.raw)


if __name__=='__main__':unittest.main()
