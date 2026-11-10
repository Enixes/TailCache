"""Paper guardrails: corrupted evidence and accidental cohort pooling must fail."""
import copy
import json
import pathlib
import unittest
import tailcache12_preprint as paper


class PaperEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((paper.DEFAULT/'paper-data.json').read_text())

    def test_frozen_claims_and_counts(self):
        self.assertTrue(paper.verify(self.data)['passed'])

    def test_duplicate_backend_rejected(self):
        rows = [r for r in self.data['observations'] if r['dataset']=='midpoint']
        with self.assertRaisesRegex(ValueError, 'Duplicate backend'):
            paper.pair_rows(rows + [rows[0]])

    def test_runtime_and_seed_mismatch_cannot_pair(self):
        rows = [r for r in self.data['observations'] if r['dataset']=='midpoint']
        for key in ('seed','runtimeGroup','measureMs','batch'):
            changed = copy.deepcopy(rows)
            value = changed[0][key]
            changed[0][key] = value + 1 if isinstance(value,int) else value + '-different-cohort'
            with self.assertRaisesRegex(ValueError, 'Incomplete pair'):
                paper.pair_rows(changed)

    def test_curve_count_corruption_rejected(self):
        ch = dict(self.data['curves'][0]['response'])
        ch['count'] += 1
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            paper.decode_curve(ch)

    def test_mixed_midpoint_cannot_be_silently_changed(self):
        changed = copy.deepcopy(self.data)
        for r in changed['observations']:
            if r['dataset']=='midpoint' and r['cohort']=='primary' and r['liveMiB']==104 and r['backend']=='CHRONICLE_IN_MEMORY':
                r['latency']['response']['percentilesNs']['99.9'] = 1
        with self.assertRaises(AssertionError):
            paper.verify(changed)

    def test_warning_removal_rejected(self):
        changed = copy.deepcopy(self.data)
        for r in changed['observations']:
            if r['dataset']=='midpoint': r['warnings']=[]
        with self.assertRaises(AssertionError):
            paper.verify(changed)


if __name__=='__main__':
    unittest.main()
