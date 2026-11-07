import unittest
from tailcache12_tlab import parse, summarize


class TlabObservationTest(unittest.TestCase):
    def line(self, clock=100, pid=7, gc=1):
        return (f'[{clock}ns][{pid}][15][debug][gc,tlab] GC({gc}) TLAB totals: thrds: 5 '
                'refills: 67 max: 63 slow allocs: 4 max 4 waste: 5.1% gc: 1130408B '
                'max: 482208B slow: 71792B max: 71792B')

    def test_worker_pid_gc_and_clock_linkage_without_duplicate_pooling(self):
        records = parse('\n'.join([self.line(),self.line(),self.line(pid=8)]),7)
        self.assertEqual(len(records),1)
        event=dict(gcId='1',kind='Pause Young (Normal)',startNs=90,endNs=110)
        result=summarize(records,[event])
        self.assertEqual(result['collections'],1)
        self.assertEqual(result['perCollection']['refills']['median'],67)
        for changed in (dict(event,gcId='2'),dict(event,startNs=30_000_000,endNs=40_000_000)):
            with self.assertRaises(ValueError):summarize(records,[changed])
        with self.assertRaises(ValueError):parse(self.line(pid=8),7)

    def test_conflicting_missing_or_nonmonotone_observations_fail(self):
        for text in (self.line()+'\n'+self.line(clock=101),
                     self.line(gc=1,clock=200)+'\n'+self.line(gc=2,clock=100),
                     self.line().replace('[7]',''),self.line().replace('max: 63','max: 90')):
            with self.assertRaises(ValueError):parse(text,7)


if __name__ == '__main__':unittest.main()
