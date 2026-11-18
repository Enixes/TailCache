import copy,json,pathlib,unittest
import tailcache12_mechanism_report as m
class MechanismPackage(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.data=json.loads((m.OUT/'mechanism-data-20261118.json').read_text())
 def test_full_package(self):
  r=m.verify(self.data);self.assertEqual(r['counts']['forks'],64);self.assertEqual(r['counts']['pairs'],32);self.assertEqual(r['counts']['quantiles'],1580)
 def bad(self,mutate,message):
  d=copy.deepcopy(self.data);mutate(d)
  with self.assertRaisesRegex(ValueError,message):m.verify(d)
 def test_quantile_corruption(self):self.bad(lambda d:d['forks'][0]['latency']['response']['percentilesNs'].__setitem__('50',1),'Rank')
 def test_count_corruption(self):self.bad(lambda d:d['forks'][0]['latency']['response'].__setitem__('count',1),'Count')
 def test_rate_corruption(self):self.bad(lambda d:d['forks'][0]['stallRates']['response'][0].__setitem__('countLower',-1),'Strict rate')
 def test_pair_contract_corruption(self):self.bad(lambda d:d['forks'][0].__setitem__('heapMiB',333),'Pair contract')
 def test_ratio_corruption(self):
  def change(d):
   d['pairs'][0]['ratios']['response']['99.9']*=2
   d['winnerScores']=m.winner_scores(d)
  self.bad(change,'Ratio')
 def test_winner_corruption(self):self.bad(lambda d:d['winnerScores']['headroom-confirm']['99.9']['M2'].__setitem__('correct',4),'Winner summaries')
if __name__=='__main__':unittest.main()
