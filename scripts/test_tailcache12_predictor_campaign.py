import unittest
import tailcache12_predictor_campaign as c
class PredictorCampaignTest(unittest.TestCase):
    def test_exact_fixed_validation_budget_and_pairs(self):
        rows=c.schedule('validation',60000,3)
        self.assertEqual(len(rows),30)
        self.assertEqual({r['writeBps'] for r in rows},{0,50,100,200,500})
        self.assertEqual(len({r['label'] for r in rows}),30)
        for i in range(0,len(rows),2):
            x,y=rows[i:i+2]
            self.assertNotEqual(x['backend'],y['backend'])
            for k in ('seed','writeBps','warmupMs','measureMs','stage','block'):self.assertEqual(x[k],y[k])
    def test_qualification_keeps_low_write_case_and_is_separate(self):
        rows=c.schedule('qualification',12000)
        self.assertEqual(len(rows),6);self.assertEqual({r['writeBps'] for r in rows},{0,50,500})
        self.assertTrue(all(r['stage'].startswith('qualification') for r in rows))
    def test_zero_update_channel_does_not_invalidate_readonly_fork(self):
        self.assertTrue(c.usable(dict(status='OK',latencyVerified=True,latency={'response':{'count':1500000},'update-service':{'count':0}})))
    def test_failed_and_censored_outcomes_never_become_valid(self):
        for status in ('ERROR','TIMEOUT','CENSORED','OOM_MEASUREMENT'):
            self.assertFalse(c.usable(dict(status=status,latencyVerified=True,latency={'response':{'count':1500000}})))
if __name__=='__main__':unittest.main()
