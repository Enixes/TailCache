import collections,unittest
import tailcache12_mechanism as c
class MechanismDesign(unittest.TestCase):
 def test_exact_fixed_stage_budgets(self):
  for k in ('logging','priming','hotset','transition','headroom','payload'):
   self.assertEqual(len(c.schedule(k)),8);self.assertTrue(c.validate_schedule(c.schedule(k)))
 def test_balance_within_each_logging_and_priming_treatment(self):
  for k,field in [('logging','logging'),('priming','primeCalls'),('hotset','hotset')]:
   d=collections.defaultdict(collections.Counter)
   for r in c.schedule(k)[::2]:d[r[field]][r['backend']]+=1
   for x in d.values():self.assertEqual(x['CAFFEINE'],x['CHRONICLE_IN_MEMORY'])
 def test_same_seed_repetitions_reverse_order(self):
  d=collections.defaultdict(list)
  for r in c.schedule('transition')[::2]:d[r['seed']].append(r['backend'])
  for arms in d.values():self.assertEqual(set(arms),set(c.core.BACKENDS))
 def test_hotset_repeat_reverses_each_seed_treatment(self):
  a={(r['seed'],r['hotset']):r['backend'] for r in c.schedule('hotset')[::2]};b={(r['seed'],r['hotset']):r['backend'] for r in c.schedule('hotset',confirmation=True)[::2]}
  self.assertEqual(set(a),set(b));self.assertTrue(all(a[k]!=b[k] for k in a))
 def test_heap_confirmation_fresh_seed_opposite_order(self):
  a=c.schedule('headroom')[::2];b=c.schedule('headroom',confirmation=True)[::2]
  self.assertTrue({r['seed'] for r in a}.isdisjoint({r['seed'] for r in b}));self.assertNotEqual(a[0]['backend'],b[0]['backend'])
 def test_broken_order_is_rejected(self):
  rows=c.schedule('logging')
  for i in range(0,len(rows),2):
   if rows[i]['backend']!='CAFFEINE':rows[i:i+2]=rows[i:i+2][::-1]
  with self.assertRaisesRegex(ValueError,'balance'):c.validate_schedule(rows)
if __name__=='__main__':unittest.main()
