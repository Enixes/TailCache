import copy
import unittest
from tailcache12_common_observer_probe import grid,compare


class CommonObserverProbeTest(unittest.TestCase):
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
