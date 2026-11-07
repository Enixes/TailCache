import unittest
from tailcache12_profile_sites import Phases, thread_kind, summarize


class ProfileSitesTest(unittest.TestCase):
    def test_boundaries_gaps_overlap_and_uncertainty(self):
        phases=Phases([dict(phase='A',startNs=10,endNs=20),dict(phase='B',startNs=25,endNs=40)],2)
        self.assertEqual(phases.at(15),('A',False))
        self.assertEqual(phases.at(20),('BETWEEN_OR_SETUP_TEARDOWN',True))
        self.assertEqual(phases.at(25),('B',True))
        with self.assertRaises(ValueError):Phases([dict(phase='A',startNs=10,endNs=20),dict(phase='B',startNs=19,endNs=30)],0)

    def test_worker_requires_both_ids_and_name(self):
        worker=dict(javaThreadId='1',osThreadId='2',javaThreadName='main')
        self.assertEqual(thread_kind(dict(javaThreadId=1,osThreadId=2,javaName='main'),worker),'WORKER')
        self.assertEqual(thread_kind(dict(javaThreadId=3,osThreadId=4),worker),'OTHER_THREAD')
        for thread in (dict(javaThreadId=1,osThreadId=3),dict(javaThreadId=1,osThreadId=2,javaName='wrong')):
            with self.assertRaises(ValueError):thread_kind(thread,worker)

    def test_streamed_refill_counts_and_recursive_stacks_are_not_allocation_census(self):
        frame=dict(method=dict(type=dict(name='C'),name='m',descriptor='()V'),lineNumber=1,bytecodeIndex=0,type='JIT compiled')
        thread=dict(javaThreadId=1,osThreadId=2,javaName='main')
        row=dict(worker=dict(javaThreadId='1',osThreadId='2',javaThreadName='main'),
            phaseWindows=[dict(phase='MEASUREMENT',startNs=10,endNs=30)],
            profile=dict(wallOriginNs=0,monotonicOriginNs=0,slope=1,interceptNs=0,maximumAnchorResidualNs=0))
        event=dict(type='jdk.ObjectAllocationInNewTLAB',values=dict(startTime='1970-01-01T00:00:00.000000015Z',
            eventThread=thread,stackTrace=dict(frames=[frame,frame],truncated=True),objectClass=dict(name='[B'),allocationSize=272,tlabSize=1000))
        result=summarize(iter([event,event]),row)
        group=result['groups'][0]
        self.assertEqual(result['totalEvents'],2)
        self.assertEqual(group['inclusive'][0]['count'],2)
        self.assertEqual(group['stacks'][0]['count'],2)
        self.assertEqual(group['allocationSizeSum'],544)
        self.assertEqual(group['tlabSizeSum'],2000)
        self.assertEqual(group['truncatedStacks'],2)


if __name__=='__main__':unittest.main()
