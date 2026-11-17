import copy,json,pathlib,unittest
import tailcache12_predictor_verify as verify
class PredictorArtifactTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.data=json.loads((pathlib.Path(__file__).resolve().parents[1]/'docs/predictor/predictor-data-20261118.json').read_text())
 def test_all_research_roles_and_zero_write_channels_reconcile(self):
  r=verify.verify(self.data);self.assertEqual(r['counts']['forks'],60);self.assertEqual(r['counts']['quantileEndpoints'],1420)
  zero=[r for r in self.data['forks'] if r['writeBps']==0];self.assertTrue(zero);self.assertTrue(all(r['latency']['update-service']['count']==0 for r in zero))
 def test_write_rate_relabelling_is_rejected(self):
  d=copy.deepcopy(self.data);d['pairs'][0]['writeBps']+=1
  with self.assertRaises(ValueError):verify.verify(d)
 def test_model_output_tampering_is_rejected(self):
  d=copy.deepcopy(self.data);d['forks'][0]['predictionNs']['M1']['99.9']+=1000
  with self.assertRaisesRegex(ValueError,'Reconstructed M1'):verify.verify(d)
 def test_numerical_error_tampering_is_rejected(self):
  d=copy.deepcopy(self.data);d['numerical']['confirmation']['all']['M2']['99.9']['medianAbsoluteNs']+=1000
  with self.assertRaisesRegex(ValueError,'numerical error'):verify.verify(d)
 def test_winner_accuracy_tampering_is_rejected(self):
  d=copy.deepcopy(self.data);d['winnerScores']['validation']['99.9']['M1']['correct']-=1
  with self.assertRaisesRegex(ValueError,'winner/baseline'):verify.verify(d)
 def test_contrary_fresh_pair_is_not_suppressed(self):
  ratios=[p['ratios']['response']['99.9'] for p in self.data['pairs'] if p['cohort']=='confirmation' and p['writeBps']==50]
  self.assertEqual(len(ratios),2);self.assertTrue(min(ratios)<1<max(ratios))
if __name__=='__main__':unittest.main()
