import unittest
from tailcache12_midpoint_report import conclusions
from tailcache12_midpoint_explorer import attach,START,END


class FollowupInterpretationTest(unittest.TestCase):
    def rows(self):
        result=[]
        for block,ratio in enumerate((.4,.5,8),1):
            for backend in ('CAFFEINE','CHRONICLE_IN_MEMORY'):
                result.append(dict(batch='fresh',cohort='primary',seed=24301,liveMiB=104,block=block,backend=backend,
                    status='OK',latencyVerified=True,warnings=[],latency={channel:{'percentilesNs':{p:100 if backend=='CAFFEINE' else 100*ratio for p in ('99','99.9','99.99','99.999')}} for channel in ('response','service','gap')}))
        return result

    def test_majority_or_median_does_not_turn_mixed_pairs_into_a_crossover(self):
        result=conclusions(self.rows(),[dict(label='primary',attempt='fresh',seed=24301,levelsMiB=[104],passes=3)])
        self.assertTrue(all(r['direction']=='Mixed' for r in result))
        self.assertTrue(all(r['confidenceInterval'] is None for r in result))

    def test_missing_pair_keeps_block_identity_and_incomplete_coverage(self):
        data=self.rows();data[0]['status']='CENSORED'
        result=conclusions(data,[dict(label='primary',attempt='fresh',seed=24301,levelsMiB=[104],passes=3)])
        self.assertTrue(all(r['direction']=='incomplete' and r['pairedBlocks']==[2,3] for r in result))

    def test_embedded_followup_survives_rebuild_without_duplicate_panels(self):
        old='<main class="wrap"><h1>Historical</h1><footer class="footer">End</footer></main>'
        component=START+'<section>Fresh</section>'+END
        once=attach(old,component);twice=attach(once,component)
        self.assertEqual(once,twice)
        self.assertEqual(twice.count(START),1)
        self.assertEqual(twice.count('id="midpoint-jump"'),1)
        self.assertIn('<h1>Historical</h1>',twice)


if __name__=='__main__':unittest.main()
