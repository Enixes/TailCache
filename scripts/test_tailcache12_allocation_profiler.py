import copy
import unittest

from tailcache12_study_analysis import allocation_profiler_vectors


class AllocationProfilerTest(unittest.TestCase):
    def fixture(self):
        metrics={n:dict(rawData=[v]) for n,v in (
            ('gc.alloc.rate',[10]*4),('gc.alloc.rate.norm',[20]*4),
            ('gc.count',[1,0,0,2]),('gc.time',[2,1,3]))}
        # Time-only change at index3 proves nonzero-count zipping is incorrect.
        text=('Iteration   1: 100 ops/s\n gc.count: 1.000 counts\n gc.time: 2.000 ms\n\n'
              'Iteration   2: 100 ops/s\n gc.count: ≈ 0 counts\n\n'
              'Iteration   3: 100 ops/s\n gc.count: ≈ 0 counts\n gc.time: 1.000 ms\n\n'
              'Iteration   4: 100 ops/s\n gc.count: 2.000 counts\n gc.time: 3.000 ms\n\n')
        return metrics,text

    def test_optional_gc_time_uses_original_indices_and_keeps_time_only_changes(self):
        metrics,text=self.fixture(); original=copy.deepcopy(metrics)
        vectors,zeros=allocation_profiler_vectors(metrics,4,text,'1.37')
        self.assertEqual([2,0,1,3],vectors['gc.time'])
        self.assertEqual([2],zeros)
        self.assertEqual(metrics,original)

    def test_incomplete_ambiguous_or_changed_evidence_fails_closed(self):
        metrics,text=self.fixture()
        for bad in (text.replace('Iteration   3:','Iteration   2:'),
                    text.replace(' gc.time: 2.000 ms\n',''),
                    text.replace('gc.count: 1.000','gc.count: 0.000'),
                    text.replace('gc.time: 3.000','gc.time: 4.000'),
                    text.replace(' gc.time: 1.000 ms\n','')):
            with self.assertRaises(ValueError): allocation_profiler_vectors(metrics,4,bad,'1.37')
        with self.assertRaises(ValueError): allocation_profiler_vectors(metrics,4,text,'unknown')
        for name in metrics:
            bad=copy.deepcopy(metrics); bad[name]['rawData'][0][0]=float('nan')
            with self.assertRaises(ValueError): allocation_profiler_vectors(bad,4,text,'1.37')

    def test_complete_vectors_preserve_legacy_positions(self):
        metrics,_=self.fixture(); metrics['gc.time']['rawData']=[[2,0,1,3]]
        vectors,zeros=allocation_profiler_vectors(metrics,4,'','1.37')
        self.assertEqual([2,0,1,3],vectors['gc.time']); self.assertEqual([],zeros)


if __name__=='__main__': unittest.main()
