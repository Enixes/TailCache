import unittest
import tailcache12_pause_model as m

class PauseModelTest(unittest.TestCase):
    def test_known_pause_budget(self):
        self.assertEqual(m.residual_quantile([(0,20_000_000)],0,1_000_000_000,'99.9'),19_000_000)
    def test_pause_below_budget_is_zero(self):
        self.assertEqual(m.residual_quantile([(0,100)],0,1_000_000,'99.9'),0)
    def test_window_end_keeps_actual_residual(self):
        self.assertEqual(m.residual_quantile([(90,120)],0,100,'99'),29)
    def test_overlapping_events_do_not_double_count(self):
        self.assertEqual(m.residual_quantile([(0,10),(5,20)],0,1000,'99'),10)
    def test_pause_before_window_is_clipped(self):
        self.assertEqual(m.residual_quantile([(-10,20)],0,100,'99'),19)
    def test_same_total_time_different_pause_shapes(self):
        self.assertGreater(m.residual_quantile([(0,40)],0,1000,'99'),m.residual_quantile([(i*10,i*10+1) for i in range(40)],0,1000,'99'))
    def test_bad_window_and_quantile_fail(self):
        for a,b,q in [(0,0,'99'),(0,1,'100'),(0,1,'0')]:
            with self.assertRaises(ValueError):m.residual_quantile([],a,b,q)

if __name__=='__main__':unittest.main()
