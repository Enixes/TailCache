import copy
import unittest
import tempfile
import pathlib
import tailcache12_focused as focus

class FocusedTest(unittest.TestCase):
    def test_pinned_hdr_ceiling_rank_is_not_old_rounded_rank(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'bins.csv'
            p.write_text('upperEquivalentNs,count\n'+''.join(f'{i},1\n' for i in range(1,200)))
            self.assertEqual(focus.rank(p,99),198)
            self.assertEqual(focus.rank(p,50),100)
    def test_finite_schedule_has_complete_independent_pairs_without_duplicates(self):
        slots=focus.schedule(4096,[328,352],3,['closed','arrival'])
        self.assertEqual(len(slots),24);self.assertEqual(len({s['label'] for s in slots}),24)
        for block in (1,2,3):
            for live in (328,352):
                for regime in ('closed','arrival'):
                    pair=[s for s in slots if (s['block'],s['liveMiB'],s['regime'])==(block,live,regime)]
                    self.assertEqual({s['backend'] for s in pair},set(focus.evidence.BACKENDS))
                    self.assertEqual({s['qps'] for s in pair},{50000 if regime=='arrival' else 0})
    def test_pressure_oom_is_retained_without_latency_ratio_and_without_poisoning_other_pairs(self):
        rows=[]
        for s in focus.schedule(4096,[328,352],3,['closed']):
            latency={'service':{'percentilesNs':{'99':100,'99.9':200}}}
            if s['backend']=='CHRONICLE_IN_MEMORY':latency={'service':{'percentilesNs':{'99':80,'99.9':160}}}
            rows.append(dict(s,status='OK',latencyVerified=True,latency=latency,warnings=[]))
        rows[0]['status']='OOM_SETUP';rows[0].pop('latency')
        result=focus.summaries(rows)
        affected=next(r for r in result if r['liveMiB']==rows[0]['liveMiB'])
        self.assertEqual(len(affected['ratios']['service']['99.9']['pairedRatios']),2)
        self.assertTrue(any(not p['usable'] for p in affected['passes']))
        self.assertIsNone(affected['ratios']['service']['99.9']['confidenceInterval'])
    def test_noisy_observations_are_visible_and_source_rows_are_not_reclassified(self):
        data=[]
        for s in focus.schedule(4096,[328],1,['closed']):
            data.append(dict(s,status='OK',latencyVerified=True,latency={'service':{'percentilesNs':{'99':100,'99.9':200}}},warnings=['external CPU']))
        original=copy.deepcopy(data);summary=focus.summaries(data)
        self.assertTrue(all(summary[0]['passes'][0]['warnings'].values()));self.assertEqual(data,original)

if __name__=='__main__':unittest.main()
