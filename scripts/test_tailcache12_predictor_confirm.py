import unittest
import tailcache12_predictor_confirm as c
class SecondaryTest(unittest.TestCase):
    def test_fresh12_have_new_seeds_and_fixed_treatments(self):
        rows=c.schedule()
        self.assertEqual(len(rows),12)
        self.assertEqual({r['seed'] for r in rows},{44811,44812})
        self.assertEqual({r['writeBps'] for r in rows},{0,50,500})
        self.assertEqual(len({r['label'] for r in rows}),12)
        for i in range(0,12,2):
            a,b=rows[i:i+2]
            self.assertNotEqual(a['backend'],b['backend'])
            self.assertEqual((a['writeBps'],a['seed']),(b['writeBps'],b['seed']))
            self.assertEqual(a['warmupMs'],120000)
if __name__=='__main__':unittest.main()
