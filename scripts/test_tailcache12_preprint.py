"""Paper guardrails: corrupted evidence and accidental cohort pooling must fail."""
import copy
import json
import pathlib
import subprocess
import sys
import tempfile
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
        for key in ('seed','runtimeGroup','measureMs','batch','qps'):
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
        with self.assertRaises(paper.EvidenceError):
            paper.verify(changed)

    def test_warning_removal_rejected(self):
        changed = copy.deepcopy(self.data)
        for r in changed['observations']:
            if r['dataset']=='midpoint': r['warnings']=[]
        with self.assertRaises(paper.EvidenceError):
            paper.verify(changed)

    def test_missing_curves_rejected(self):
        for curves in ([],self.data['curves'][:-1]):
            changed=copy.deepcopy(self.data);changed['curves']=curves
            with self.assertRaisesRegex(paper.EvidenceError,'primary response curve'):
                paper.verify(changed)

    def test_duplicate_curve_rejected(self):
        changed=copy.deepcopy(self.data);changed['curves'][-1]=changed['curves'][0]
        with self.assertRaisesRegex(paper.EvidenceError,'primary response curve'):
            paper.verify(changed)

    def test_no_direction_from_empty_or_nonfinite_data(self):
        for values in ([],[float('nan')],[float('inf')],[0],[-1]):
            with self.assertRaises(paper.EvidenceError):paper.direction(values)

    def test_counts_are_reported_from_actual_coverage(self):
        checks=paper.verify(self.data)
        self.assertEqual(checks['fullResponseCurvesChecked'],len(self.data['curves']))
        self.assertEqual(checks['histogramPercentileChecks'],len(self.data['curves'])*4)
        self.assertEqual(checks['primaryHistogramThresholdChecks'],len(self.data['curves'])*3)

    def test_wrong_fresh_channel_count_rejected(self):
        changed=copy.deepcopy(self.data)
        next(r for r in changed['observations'] if r['dataset']=='midpoint')['latency']['service']['count']-=1
        with self.assertRaisesRegex(paper.EvidenceError,'channel count'):paper.verify(changed)

    def test_false_threshold_probability_rejected(self):
        changed=copy.deepcopy(self.data)
        r=next(r for r in changed['observations'] if r['dataset']=='midpoint')
        r['stallRates']['response']['rates']['100000']['upperProbability']=.9
        with self.assertRaisesRegex(paper.EvidenceError,'probability/count'):paper.verify(changed)

    def test_false_threshold_count_rejected_against_histogram(self):
        changed=copy.deepcopy(self.data);curve=changed['curves'][0]
        rate=curve['response']['rates']['100000'];rate['upperCount']+=1
        rate['upperProbability']=rate['upperCount']/curve['response']['count']
        with self.assertRaisesRegex(paper.EvidenceError,'differs from histogram'):paper.verify(changed)

    def test_curve_hash_rejected(self):
        ch=copy.deepcopy(self.data['curves'][0]['response']);ch['curveSha256']='0'*64
        with self.assertRaisesRegex(paper.EvidenceError,'content hash'):paper.decode_curve(ch)

    def test_strict_threshold_straddling_bin_bounds(self):
        bins=[(99967,2),(100031,3),(100095,5)]
        self.assertEqual(paper.lower_equivalent(100031),99968)
        rates={'100000':dict(lowerCount=5,upperCount=8,lowerProbability=.5,upperProbability=.8)}
        for t in ('1000000','10000000'):
            rates[t]=dict(lowerCount=0,upperCount=0,lowerProbability=0,upperProbability=0)
        paper.verify_curve_rates(dict(count=10,rates=rates),bins)
        rates['100000'].update(lowerCount=8,lowerProbability=.8)
        with self.assertRaisesRegex(paper.EvidenceError,'Definite exceedance'):
            paper.verify_curve_rates(dict(count=10,rates=rates),bins)

    def test_hdr_ceiling_rank_boundary(self):
        self.assertEqual(paper.hdr_percentile([(1,99),(2,1)],'99'),1)
        self.assertEqual(paper.hdr_percentile([(1,99),(2,1)],'99.9'),2)

    def test_fixed_seed_schedule_cannot_change(self):
        changed=copy.deepcopy(self.data)
        for r in changed['observations']:
            if r['dataset']=='midpoint' and r['cohort']=='seed24302':r['seed']=99999
        with self.assertRaisesRegex(paper.EvidenceError,'schedule mismatch'):paper.verify(changed)

    def test_invalid_data_rejected_in_optimized_python(self):
        with tempfile.TemporaryDirectory() as folder:
            changed=copy.deepcopy(self.data);changed['curves']=[]
            pathlib.Path(folder,'paper-data.json').write_text(json.dumps(changed))
            run=subprocess.run([sys.executable,'-O',str(paper.ROOT/'scripts/tailcache12_preprint.py'),
                                'verify','--out',folder],capture_output=True,text=True)
            self.assertNotEqual(run.returncode,0)
            self.assertIn('primary response curve',run.stderr)


if __name__=='__main__':
    unittest.main()
