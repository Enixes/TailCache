import copy
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch
import tailcache12 as evidence

KEY='/sys/devices/system/cpu/cpu0/thermal_throttle/package_throttle_count'
TIME=KEY.removesuffix('_count')+'_total_time_ms'


def rows(change=5,count_delta=1,time_delta=5):
    return [dict(monotonicNs=n*10**9,nativeThermalSampleStartNs=n*10**9+100,
        nativeThermalSampleEndNs=n*10**9+10000,nativeThrottleCounts=json.dumps({KEY:10+(count_delta if n>=change else 0)}),
        nativeThrottleTimesMs=json.dumps({TIME:100+(time_delta if n>=change else 0)}),
        nativeTemperatures=json.dumps({'cpu':dict(milliC=65000,criticalMilliC=100000)})) for n in range(61)]


class StartupThermalTest(unittest.TestCase):
    def assess(self,samples,gate=None,**kwargs):
        if gate is None:gate=lambda *args:([],None)
        with patch.object(evidence,'replay_cold_launch'),patch.object(evidence,'measurement_windows',return_value=[(50*10**9,58*10**9)]), \
             patch.object(evidence,'replay_host_gate',side_effect=gate):
            return evidence.replay_settled_thermal({'sourceSha256':'source'},pathlib.Path('/raw'),samples,pathlib.Path('/cold'),**kwargs)

    def test_read_bracket_budget_is_explicit_bounded_and_preserves_raw(self):
        samples=rows();samples[20]['nativeThermalSampleEndNs']=samples[20]['nativeThermalSampleStartNs']+100_000_000
        original=copy.deepcopy(samples)
        with self.assertRaisesRegex(ValueError,'read bracket'):self.assess(samples)
        proof=self.assess(samples,read_bracket_ms=250)
        self.assertTrue(proof['wideThermalReadUsed']);self.assertEqual(proof['maximumThermalReadBracketMs'],100)
        self.assertEqual(proof['thermalReadBracketCeilingMs'],250);self.assertEqual(samples,original)
        for limit in (50,250):
            samples[20]['nativeThermalSampleEndNs']=samples[20]['nativeThermalSampleStartNs']+limit*1_000_000
            self.assess(samples,read_bracket_ms=limit)
            samples[20]['nativeThermalSampleEndNs']+=1
            with self.assertRaisesRegex(ValueError,'read bracket'):self.assess(samples,read_bracket_ms=limit)
        for invalid in (51,100,251,250.0,True):
            with self.assertRaisesRegex(ValueError,'policy'):self.assess(rows(),read_bracket_ms=invalid)

    def test_wider_bracket_never_moves_a_late_change_before_settling(self):
        samples=rows(change=29)
        samples[29]['nativeThermalSampleStartNs']=29_900_000_000
        samples[29]['nativeThermalSampleEndNs']=30_050_000_000
        with self.assertRaisesRegex(ValueError,'changed in settling'):
            self.assess(samples,read_bracket_ms=250)
        for change in (31,50):
            with self.assertRaisesRegex(ValueError,'changed in settling'):
                self.assess(rows(change=change),read_bracket_ms=250)

    def test_bounded_startup_exception_keeps_raw_and_exposes_masked_cpu_failure(self):
        samples=rows();original=copy.deepcopy(samples)
        def gate(manifest,directory,data):
            return (['Native thermal-throttle counter increased'] if len({r['nativeThrottleCounts'] for r in data})>1
                else ['Native CPU outside benchmark scope exceeded 10% upper bound']),None
        proof=self.assess(samples,gate)
        self.assertTrue(proof['startupExceptionUsed']);self.assertEqual(proof['maximumStartupDurationMs'],5)
        self.assertEqual(proof['effectiveReasons'],['Native CPU outside benchmark scope exceeded 10% upper bound'])
        self.assertEqual(samples,original)

    def test_settling_measurement_duration_only_and_no_window_changes_are_hard(self):
        for changed in (rows(31),rows(50),rows(40,count_delta=0,time_delta=1)):
            with self.assertRaises(ValueError):self.assess(changed)
        with patch.object(evidence,'replay_cold_launch'),patch.object(evidence,'measurement_windows',return_value=[]), \
             patch.object(evidence,'replay_host_gate',return_value=([],None)):
            with self.assertRaises(ValueError):evidence.replay_settled_thermal({'sourceSha256':'s'},pathlib.Path('/raw'),rows(),pathlib.Path('/cold'))

    def test_count_duration_sensor_reset_and_metadata_bounds_are_hard(self):
        for changed in (rows(count_delta=2),rows(time_delta=101),rows(count_delta=-1),rows(time_delta=-1)):
            with self.assertRaises(ValueError):self.assess(changed)
        for mutation in ('missing','bracket','temperature','reset'):
            samples=rows()
            if mutation=='missing':samples[20]['nativeThrottleTimesMs']='{}'
            elif mutation=='bracket':samples[20]['nativeThermalSampleEndNs']+=10**9
            elif mutation=='temperature':samples[40]['nativeTemperatures']=json.dumps({'cpu':dict(milliC=91000,criticalMilliC=100000)})
            else:samples[40]['nativeThrottleTimesMs']=json.dumps({TIME:104})
            with self.assertRaises(ValueError):self.assess(samples)

    def test_zero_duration_is_flagged_not_claimed_as_proven_inactivity_and_critical_gate_survives(self):
        proof=self.assess(rows(time_delta=0));self.assertTrue(proof['startupExceptionUsed'])
        self.assertIn('does not prove',proof['durationObservationLimit'])
        proof=self.assess(rows(),lambda *args:(['Native temperature reached its critical limit'],None))
        self.assertEqual(proof['effectiveReasons'],['Native temperature reached its critical limit'])

    def test_cold_window_needs_consecutive_temperature_and_counter_stability(self):
        samples=rows(change=100)[:6]
        with patch.object(evidence,'host_gate',return_value=([],None)):
            self.assertTrue(evidence.cold_window_pass(samples));self.assertFalse(evidence.cold_window_pass(samples[:5]))
            for field,value in (('nativeTemperatures',json.dumps({'cpu':dict(milliC=71000,criticalMilliC=100000)})),
                    ('nativeThrottleCounts',json.dumps({KEY:11})),('nativeThrottleTimesMs',json.dumps({TIME:101}))):
                bad=copy.deepcopy(samples);bad[-1][field]=value;self.assertFalse(evidence.cold_window_pass(bad))

    def test_cold_proof_source_age_and_forged_pass_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(evidence,'host_gate',return_value=([],None)):
            path=pathlib.Path(tmp)/'proof.json';samples=rows(change=100)[:16]
            record=dict(rule=evidence.THERMAL_STARTUP_RULE,sourceSha256='source',passed=True,failure=None,elapsedSeconds=15.1,samples=samples)
            path.write_text(json.dumps(record));evidence.replay_cold_launch(path,'source',dict(monotonicNs=16*10**9))
            with self.assertRaises(ValueError):evidence.replay_cold_launch(path,'other',dict(monotonicNs=16*10**9))
            with self.assertRaises(ValueError):evidence.replay_cold_launch(path,'source',dict(monotonicNs=30*10**9))
            record['samples'][-1]['nativeTemperatures']=json.dumps({'cpu':dict(milliC=80000,criticalMilliC=100000)})
            path.write_text(json.dumps(record))
            with self.assertRaises(ValueError):evidence.replay_cold_launch(path,'source',dict(monotonicNs=16*10**9))


if __name__=='__main__':unittest.main()
