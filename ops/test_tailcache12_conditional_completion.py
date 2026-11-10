import copy
import sys
import pathlib
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import test_tailcache12_conditional as fixtures
import tailcache12_conditional_completion as supplement


class CompletionTest(unittest.TestCase):
    def setUp(self):self.fixtures=fixtures.ConditionalStudyTest()
    def rows(self,stage):return [supplement.mark(r,'original') for r in self.fixtures.rows(stage)]
    def analyse(self,rows):
        with patch.object(supplement.c.legacy_analysis,'hierarchical_ratio',side_effect=self.fixtures.bootstrap):
            return supplement.analyse(rows,supplement.c.pressure_bands(self.rows('calibration')),self.fixtures.floors(),self.rows('qualification'))

    def test_only_original_unattempted_suffix_is_allowed(self):
        slots=supplement.c.grid('campaign')[supplement.OFFSET:]
        self.assertEqual(len(slots),49)
        inv=[dict(label=k,properties=p) for k,p in slots]
        self.assertEqual(supplement.validate_suffix(inv,'campaign',supplement.OFFSET),slots)
        bad=copy.deepcopy(inv);bad[0]=copy.deepcopy(inv[1])
        with self.assertRaises(ValueError):supplement.validate_suffix(bad,'campaign',supplement.OFFSET)
        with self.assertRaises(ValueError):supplement.validate_suffix(inv+[inv[-1]],'campaign',supplement.OFFSET)
        bad=copy.deepcopy(inv);bad[0]['properties']['Seed']+=1
        with self.assertRaises(ValueError):supplement.validate_suffix(bad,'campaign',supplement.OFFSET)

    def test_cpu_rejection_is_never_reclassified_and_unknown_hard_reason_stops(self):
        row=dict(fatalReasons=[supplement.CPU_REJECTION],finalPolicyUsable=False)
        self.assertTrue(supplement.allowed_rejection(row));marked=supplement.mark(row,'completion')
        self.assertTrue(marked['excludedFromStatistics']);self.assertFalse(marked['finalPolicyUsable'])
        self.assertEqual(row,dict(fatalReasons=[supplement.CPU_REJECTION],finalPolicyUsable=False))
        for reasons in ([],['power disconnected'],[supplement.CPU_REJECTION,'recording incomplete']):
            self.assertFalse(supplement.allowed_rejection(dict(fatalReasons=reasons)))

    def test_original_source_and_fixed_evidence_mutation_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);p=root/'original-state.json';p.write_text('terminal')
            binding=dict(sourceSha256='source',fixedFiles={p.name:supplement.digest(p)},completedStageRefs={})
            with patch.object(supplement.c.evidence,'REPORTS',root),patch.object(supplement.c,'verify_refs'), \
                    patch.object(supplement.c.evidence,'source_hash',return_value='source'):
                supplement.verify_binding(binding);p.write_text('changed')
                with self.assertRaisesRegex(ValueError,'frozen evidence'):supplement.verify_binding(binding)
            with patch.object(supplement.c.evidence,'source_hash',return_value='different'):
                with self.assertRaisesRegex(ValueError,'Source changed'):supplement.verify_binding(binding)

    def test_rejected_tail_never_enters_bootstrap_variation_or_complete_ci(self):
        rows=self.rows('campaign');bad=rows[142];bad.update(finalPolicyUsable=False,fatalReasons=[supplement.CPU_REJECTION])
        bad['servicePercentilesNs']={'50':10**12,'99':10**12,'99.9':10**12}
        result=self.analyse(rows)
        self.assertNotIn(bad['label'],result['statisticsInputLabels']);self.assertIn(bad['label'],result['excludedLabels'])
        rejected=[c for c in result['comparisons'] if bad['label'] in c['rejectedInvocations']]
        self.assertEqual(len(rejected),1);cell=rejected[0]
        self.assertFalse(cell['complete']);self.assertFalse(cell['resolvedConditionalClaimAllowed']);self.assertEqual(cell['ratios'],{})
        stats=cell['runVariation'][bad['inputs']['Backend']]['99'];self.assertEqual(stats['forks'],5)
        self.assertLess(stats['maximumNs'],1000)
        self.assertEqual(sum(c['complete'] for c in result['comparisons']),15)

    def test_empty_valid_backend_is_explicit_incomplete_not_a_fabricated_statistic(self):
        rows=self.rows('campaign');key=rows[0]['inputs']
        for r in rows:
            p=r['inputs']
            if all(p[k]==key[k] for k in ('Backend','Channel','Payload','LiveBytes')):
                r.update(finalPolicyUsable=False,fatalReasons=[supplement.CPU_REJECTION])
        result=self.analyse(rows);cell=next(c for c in result['comparisons'] if c['rejectedInvocations'])
        stats=cell['runVariation'][key['Backend']]['99'];self.assertEqual(stats['forks'],0);self.assertIsNone(stats['medianNs'])
        self.assertFalse(cell['complete']);self.assertFalse(cell['ratios'])

    def test_within_pass_interruption_prevents_resolved_claim_and_retains_raw_interval(self):
        rows=self.rows('campaign');rows[0]['executionSegment']='completion'
        result=self.analyse(rows);affected=[c for c in result['comparisons'] if any('Interrupted' in x for x in c['claimLimitations'])]
        self.assertEqual(len(affected),1);self.assertTrue(affected[0]['complete'])
        self.assertFalse(affected[0]['resolvedConditionalClaimAllowed'])
        self.assertTrue(all(r['direction']=='unresolved' and r['rawBootstrapDirection']!='unresolved' for r in affected[0]['ratios'].values()))

    def test_rejected_robustness_pair_has_no_ratio_or_confidence_interval(self):
        rows=self.rows('robustness');rows[0].update(finalPolicyUsable=False,fatalReasons=[supplement.CPU_REJECTION])
        result=supplement.robustness(rows,self.rows('qualification'));bad=[r for r in result if not r['acceptedPair']]
        self.assertEqual(len(bad),1);self.assertIsNone(bad[0]['chronicleToCaffeine']);self.assertIsNone(bad[0]['confidenceInterval'])
        self.assertFalse(bad[0]['conditionalSensitivityUsable'])
        with self.assertRaises(ValueError):supplement.robustness(rows[1:],self.rows('qualification'))


if __name__=='__main__':unittest.main()
