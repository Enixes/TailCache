import unittest

import tailcache12 as evidence
import tailcache12_calibrate as calibration
import tailcache12_observer as observer
import tailcache12_pilot as pilot
from tailcache12_study_analysis import validate_lifecycle_preparation


class LifecyclePreparationTest(unittest.TestCase):
    def metadata(self):
        return ('lifecycleWarmupVersion=lifecycle-maintenance-v1 lifecycleWarmupTrials=3 '
                'lifecycleMaintenanceBatches=20000 lifecycleMaintenanceBatchOperations=128 '
                'lifecycleWarmupOperations=7680000 lifecycleWarmupWrites=384000')

    def test_declared_primitive_counts_and_actual_flag_are_required_with_legacy_replay_preserved(self):
        inputs=dict(LifecycleWarmupVersion=evidence.LIFECYCLE_WARMUP_VERSION)
        args=['-Dtailcache12.lifecycleWarmupVersion='+evidence.LIFECYCLE_WARMUP_VERSION]
        validate_lifecycle_preparation(inputs,self.metadata(),args)
        validate_lifecycle_preparation({},'',[])
        validate_lifecycle_preparation({},'lifecycleWarmupVersion=none',[])
        for text in ('',self.metadata().replace('20000','19999'),
                     self.metadata().replace('7680000','7680001'),
                     self.metadata().replace('384000','383999')):
            with self.assertRaises(ValueError): validate_lifecycle_preparation(inputs,text,args)
        with self.assertRaises(ValueError): validate_lifecycle_preparation(inputs,self.metadata(),[])
        with self.assertRaises(ValueError): validate_lifecycle_preparation({},self.metadata(),args)

    def test_explicit_control_is_frozen_in_both_channels_and_every_floor_pilot_slot(self):
        inputs=dict(liveBytes=[0,96,208,288],payloads=[256,4096],residents=32768,heapMiB=512,
            churnBytesPerSecond=33554432,seed=24301,warmups=120,conditioning=8,measurements=8,repeats=2,
            channels=list(calibration.CHANNELS),lifecycleWarmupVersion=evidence.LIFECYCLE_WARMUP_VERSION)
        plans=(calibration.calibration_grid(inputs),pilot.schedule(inputs),
               observer.floor_grid(120,8,None,evidence.LIFECYCLE_WARMUP_VERSION))
        self.assertEqual([64,160,10],[len(p) for p in plans])
        for plan in plans:
            self.assertTrue(all(p['LifecycleWarmupVersion']==evidence.LIFECYCLE_WARMUP_VERSION for _,p in plan))
        inputs.pop('lifecycleWarmupVersion')
        self.assertTrue(all('LifecycleWarmupVersion' not in p for _,p in calibration.calibration_grid(inputs)))


if __name__=='__main__': unittest.main()
