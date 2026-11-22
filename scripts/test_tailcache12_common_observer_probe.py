import copy
import unittest
import pathlib
import tempfile
from unittest.mock import patch
import tailcache12_common_observer_probe as probe
from tailcache12_common_observer_probe import grid,compare


class CommonObserverProbeTest(unittest.TestCase):
    def test_new_memory_rule_is_opt_in_frozen_and_legacy_replay_stays_legacy(self):
        probe.verify_preparation_declaration(dict(cachePreparationVersion=4),dict(version=4))
        valid=dict(cachePreparationVersion=5,initialMemoryReadinessRule=dict(probe.AVAILABLE_MEMORY_RULE),hdrVerifier={'proof':'present'})
        probe.verify_preparation_declaration(valid,dict(version=5))
        for changed in (dict(cachePreparationVersion=4,initialMemoryReadinessRule=probe.AVAILABLE_MEMORY_RULE),
                        dict(cachePreparationVersion=5),dict(valid,initialMemoryReadinessRule={}),dict(valid,hdrVerifier={})):
            with self.assertRaises(ValueError):probe.verify_preparation_declaration(changed,dict(version=changed['cachePreparationVersion']))
        with self.assertRaises(ValueError):probe.verify_preparation_declaration(valid,dict(version=4))

    def test_failed_preparation_never_reaches_quiet_or_cache_forks_and_default_is_unchanged(self):
        for available in (False,True):
            with tempfile.TemporaryDirectory() as tmp:
                argv=['probe','run','fresh','--quiet-id','fresh-quiet']+(['--available-memory-gate'] if available else [])
                with patch.object(probe.evidence,'REPORTS',pathlib.Path(tmp)),patch.object(probe.evidence,'source_hash',return_value='source'), \
                     patch.object(probe.evidence,'host_snapshot',return_value={'nativeScopeQualified':1}), \
                     patch.dict(probe.os.environ,{'TAILCACHE_REQUIRE_NATIVE_HOST':'1','JAVA_TOOL_OPTIONS':'','JDK_JAVA_OPTIONS':'','_JAVA_OPTIONS':''}), \
                     patch.object(probe,'prepare_file_cache',side_effect=ValueError('retained rejection')) as prepare, \
                     patch.object(probe,'run_preflight') as quiet,patch.object(probe.evidence,'invoke') as invoke, \
                     patch('tailcache12_exploratory.compile_verifier',return_value={'proof':'present'}) as helper, \
                     patch('sys.argv',argv):
                    with self.assertRaisesRegex(ValueError,'retained rejection'):probe.main()
                self.assertEqual(prepare.call_args.kwargs,dict(include_build_outputs=True,stream_inventory=True,**({'available_memory':True} if available else {})))
                self.assertEqual(helper.call_count,int(available));quiet.assert_not_called();invoke.assert_not_called()

    def rows(self):
        return [dict(label=label,inputs=p,observedOperationsPerSecond=1000000,
                     servicePercentilesNs={'50':100,'99':200,'99.9':300}) for label,p in grid()]

    def test_twelve_reversed_unprofiled_slots_and_only_common_has_extra_work(self):
        slots=grid();self.assertEqual(len(slots),12);self.assertEqual(len({k for k,p in slots}),12)
        self.assertEqual([p['ObservationMode'] for k,p in slots[:3]],['sparse','common','every'])
        self.assertEqual([p['ObservationMode'] for k,p in slots[6:9]],['every','common','sparse'])
        self.assertEqual(slots[0][1]['Backend'],slots[-1][1]['Backend'])
        for k,p in slots:
            self.assertNotIn('FlightRecorder',p)
            self.assertEqual(p.get('DenseObserver')=='true',p['ObservationMode']=='common')
            self.assertEqual(p.get('ObserverDiagnosticOnly')=='true',p['ObservationMode']=='common')

    def test_prospective_rate_tail_bounds_and_incomplete_comparison_are_not_waived(self):
        self.assertTrue(all(c['criteriaPass'] for c in compare(self.rows())))
        for field,value in (('observedOperationsPerSecond',1150001),('99',251),('99.9',376)):
            rows=self.rows();row=next(r for r in rows if r['inputs']['ObservationMode']=='common')
            if field=='observedOperationsPerSecond':row[field]=value
            else:row['servicePercentilesNs'][field]=value
            self.assertFalse(all(c['criteriaPass'] for c in compare(rows)))
        with self.assertRaises(ValueError):compare(self.rows()[:-1])


if __name__=='__main__':unittest.main()
