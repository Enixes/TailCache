import copy,hashlib,json,pathlib,tempfile,unittest
from unittest import mock
import tailcache12_mechanism_reproduce as replay
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
 def test_count_corruption(self):self.bad(lambda d:d['forks'][0]['latency']['response'].__setitem__('count',1),'Channel request conservation')
 def test_rate_corruption(self):self.bad(lambda d:d['forks'][0]['stallRates']['response'][0].__setitem__('countLower',-1),'Strict rate')
 def test_pair_contract_corruption(self):self.bad(lambda d:d['forks'][0].__setitem__('heapMiB',333),'slot contract')
 def test_ratio_corruption(self):
  def change(d):
   d['pairs'][0]['ratios']['response']['99.9']*=2
   d['winnerScores']=m.winner_scores(d)
  self.bad(change,'Ratio')
 def test_winner_corruption(self):self.bad(lambda d:d['winnerScores']['headroom-confirm']['99.9']['M2'].__setitem__('correct',4),'Winner summaries')
 def test_empty_completed_scope_rejected(self):
  def change(d):
   for k in ('forks','pairs','controls'):d[k]=[]
   d['cohorts']={};d['winnerScores']={}
  self.bad(change,'cohort coverage')
 def test_missing_pair_rejected(self):
  def change(d):d['pairs'].pop();d['winnerScores']=m.winner_scores(d)
  self.bad(change,'pair coverage')
 def test_missing_response_histograms_rejected(self):
  def change(d):
   for r in d['forks']:r['distributions'].pop('response');r['stallRates'].pop('response')
  self.bad(change,'channel coverage')
 def test_missing_threshold_rates_rejected(self):
  def change(d):
   for r in d['forks']:
    for ch in r['stallRates']:r['stallRates'][ch]=[]
  self.bad(change,'Threshold coverage')
 def test_duplicate_pair_membership_rejected(self):
  def change(d):
   d['pairs'][1]['c']=d['pairs'][0]['c'];d['winnerScores']=m.winner_scores(d)
  self.bad(change,'pair membership')
 def test_missing_winner_scores_rejected(self):self.bad(lambda d:d.pop('winnerScores'),'Winner score coverage')
 def test_fake_calibration_exclusion_rejected(self):self.bad(lambda d:d['forks'][0].__setitem__('predictionOutsideCalibration',True),'Calibration contract')
 def test_coordinated_histogram_count_change_rejected(self):
  def change(d):
   r=d['forks'][0]
   for ch,bins in r['distributions'].items():
    for b in bins:b[1]*=2
    r['latency'][ch]['count']*=2
    for rate in r['stallRates'][ch]:
     for k in ('operations','countLower','countUpper'):rate[k]*=2
  self.bad(change,'Channel request conservation')
 def test_log_error_summary_corruption_rejected(self):
  self.bad(lambda d:d['cohorts']['logging']['score']['numerical']['all']['M2']['99.9'].__setitem__('medianAbsoluteLog2Error',999),'Numerical summary')
 def test_missing_archives_cannot_replace_package(self):
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);out=root/'docs/mechanism';out.mkdir(parents=True);f=out/'mechanism-data-20261118.json';f.write_bytes(b'retained evidence')
   with mock.patch.object(m,'ROOT',root),mock.patch.object(m,'OUT',out):
    with self.assertRaisesRegex(ValueError,'Missing completed raw cohort'):m.package()
   self.assertEqual(f.read_bytes(),b'retained evidence')
 def test_frozen_output_refuses_replacement(self):
  with tempfile.TemporaryDirectory() as td:
   f=pathlib.Path(td)/'artifact.json';m.save_frozen(f,dict(retained=1));raw=f.read_bytes();stamp=f.stat().st_mtime_ns;m.save_frozen(f,dict(retained=1));self.assertEqual(f.stat().st_mtime_ns,stamp)
   with self.assertRaisesRegex(ValueError,'Refuse changed frozen output'):m.save_frozen(f,dict(retained=2))
   self.assertEqual(f.read_bytes(),raw)
 def test_replay_rejects_self_consistent_changed_code(self):
  d=copy.deepcopy(self.data);key='docs/predictor/drain_candidate.py.txt';d['frozenModelFiles'][key]['text']='raise RuntimeError("review sentinel")';d['frozenModelFiles'][key]['sha256']=hashlib.sha256(d['frozenModelFiles'][key]['text'].encode()).hexdigest()
  with self.assertRaisesRegex(ValueError,'Unrecognized frozen source'):replay.validate_frozen_sources(d)
 def test_invalid_report_does_not_replace_presentation(self):
  with tempfile.TemporaryDirectory() as td:
   out=pathlib.Path(td);p=out/'RESULTS.md';p.write_text('retained reviewed conclusions')
   with mock.patch.object(m,'OUT',out):
    with self.assertRaisesRegex(ValueError,'cohort coverage'):m.reports(dict(version='tailcache-mechanism-portable-v1',cohorts={}))
   self.assertEqual(p.read_text(),'retained reviewed conclusions')
 def test_incorrect_setup_scope_rejected(self):self.bad(lambda d:d['scope'].__setitem__('functionalJvms',6),'Scope accounting')
 def test_missing_warmup_window_rejected(self):self.bad(lambda d:d['forks'][0]['windows'].pop(0),'Phase coverage')
 def test_replay_accepts_original_frozen_sources(self):replay.validate_frozen_sources(self.data)
if __name__=='__main__':unittest.main()
