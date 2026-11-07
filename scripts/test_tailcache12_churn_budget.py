import pathlib
import unittest
from unittest.mock import patch
from tailcache12_analysis import CHURN_DROP_BUDGET_VERSION,churn_drop_valid,churn_drop_summary
import tailcache12_conditional as study


def row(payload=33554432,dropped=0,phase='MEASUREMENT'):
    return dict(phase=phase,churnPayloadBytes=str(payload),churnDroppedBytes=str(dropped))


class ChurnBudgetTest(unittest.TestCase):
    def test_exact_zero_default_and_explicit_fraction_byte_boundaries(self):
        self.assertFalse(churn_drop_valid(row(dropped=8192)))
        self.assertTrue(churn_drop_valid(row(dropped=8192),CHURN_DROP_BUDGET_VERSION))
        self.assertTrue(churn_drop_valid(row(dropped=32768),CHURN_DROP_BUDGET_VERSION))
        self.assertFalse(churn_drop_valid(row(dropped=32769),CHURN_DROP_BUDGET_VERSION))
        self.assertTrue(churn_drop_valid(row(payload=999,dropped=1),CHURN_DROP_BUDGET_VERSION))
        self.assertFalse(churn_drop_valid(row(payload=998,dropped=1),CHURN_DROP_BUDGET_VERSION))
        self.assertFalse(churn_drop_valid(row(payload=0,dropped=1),CHURN_DROP_BUDGET_VERSION))
        self.assertTrue(churn_drop_valid(row(payload=0,dropped=0),CHURN_DROP_BUDGET_VERSION))
        for bad in (row(payload=-1),row(dropped=-1)):
            self.assertFalse(churn_drop_valid(bad,CHURN_DROP_BUDGET_VERSION))
        with self.assertRaises(ValueError):churn_drop_valid(row(),'unknown')
        for bad in (dict(row(),churnDroppedBytes='nan'),dict(row(),churnPayloadBytes='3.5')):
            with self.assertRaises(ValueError):churn_drop_valid(bad,CHURN_DROP_BUDGET_VERSION)

    def test_summary_conserves_phases_and_excludes_warmup_without_laundering(self):
        rows=[row(dropped=8192,phase='CONDITIONING'),row(dropped=16384),row(dropped=9999999,phase='WARMUP')]
        result=churn_drop_summary(rows,CHURN_DROP_BUDGET_VERSION)
        self.assertTrue(result['allWithinBudget']);self.assertEqual(result['totalDroppedBytes'],24576)
        self.assertEqual(result['conditioningDroppedBytes'],8192);self.assertEqual(result['measurementDroppedBytes'],16384)
        self.assertEqual(result['totalPayloadBytes'],2*33554432)
        self.assertIsNone(churn_drop_summary(rows))
        self.assertFalse(churn_drop_summary([row(dropped=65536)],CHURN_DROP_BUDGET_VERSION)['allWithinBudget'])

    def test_final_row_keeps_original_zero_drop_failure_and_new_warning(self):
        inv=dict(label='slot',properties={'Channel':'sample-calibration'})
        summary=dict(rejectionReasons=[],strictReasons=[],churnDropBudgetSummary=dict(totalDroppedBytes=8192,conditioningDroppedBytes=8192,measurementDroppedBytes=0))
        host=dict(strictReasons=[],effectiveReasons=[],outsideCpuUpperPercent=0,thermalReview={'startupExceptionUsed':False})
        with patch.object(study.facts,'audit_row',return_value=(summary,None,None)),patch.object(study,'host_facts',return_value=host):
            result,_,_=study.read_row(pathlib.Path('/unused'),{},inv,None,None,{})
        self.assertIn(study.CHURN_DROP_WARNING,result['warnings']);self.assertFalse(result['strictQualityPass'])
        self.assertTrue(result['originalExactZeroDropReasons']);self.assertFalse(result['fatalReasons'])

    def test_new_version_is_frozen_in_all_new_workload_floor_diagnostic_slots(self):
        for stage in study.STAGES:
            for label,p in study.grid(stage):
                if p is not None:self.assertEqual(p['ChurnDropBudgetVersion'],CHURN_DROP_BUDGET_VERSION)


if __name__=='__main__':unittest.main()
