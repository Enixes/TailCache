import csv
import pathlib
import tempfile
import unittest

from tailcache12_observer import RULES, floor_grid
from tailcache12_study_analysis import between_operation_fraction, hierarchical_ratio


class ObserverStudyTest(unittest.TestCase):
    def test_floor_schedule_has_independent_balanced_replicas_and_separate_timers(self):
        grid = floor_grid(96)
        self.assertEqual(10, len(grid))
        self.assertEqual(10, len({label for label, _ in grid}))
        floors = [p for _, p in grid if p["Channel"] == "floor"]
        for backend in ("CAFFEINE", "CHRONICLE_IN_MEMORY"):
            for payload in (256, 4096):
                selected = [p for p in floors if p["Backend"] == backend and p["Payload"] == payload]
                self.assertEqual([1, 2], [p["Block"] for p in selected])
                self.assertTrue(all(p["LiveBytes"] == 0 and p["Warmups"] == 96 for p in selected))
        timers = [p for _, p in grid if p["Channel"] == "timer"]
        self.assertEqual(2, len(timers))
        self.assertTrue(all(p["TimerFloor"] == "true" and p["ChurnBytesPerSecond"] == 0 for p in timers))
        self.assertIn("No opposite", RULES["coherence"])

    def test_between_call_fraction_is_bounded_and_not_mislabeled_observer_cpu_cost(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = pathlib.Path(directory) / "worker"
            worker.mkdir()
            (worker / "configuration.txt").write_text("histogramSignificantDigits=3\n")
            with (worker / "iterations.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=("phase", "iteration", "startNs", "endNs", "operations"))
                writer.writeheader()
                writer.writerow(dict(phase="MEASUREMENT", iteration=1, startNs=1, endNs=30001, operations=10))
            bins = worker / "iteration-1-service-bins.csv"
            bins.write_text("upperEquivalentNs,count\n2049,10\n")
            result = between_operation_fraction(pathlib.Path(directory))
            self.assertAlmostEqual((30000-20490)/30000, result["lower"])
            self.assertAlmostEqual((30000-20480)/30000, result["upper"])
            self.assertIn("between-call pauses", result["interpretation"])
            bins.write_text("upperEquivalentNs,count\n2048,10\n")
            with self.assertRaises(ValueError):
                between_operation_fraction(pathlib.Path(directory))
            bins.write_text("upperEquivalentNs,count\n2049,9\n")
            with self.assertRaises(ValueError):
                between_operation_fraction(pathlib.Path(directory))

    def test_high_confidence_intervals_are_labeled_and_need_enough_tail_draws(self):
        blocks = [[(10, 20), (20, 40), (30, 60)], [(12, 24), (22, 44), (32, 64)]]
        with self.assertRaises(ValueError):
            hierarchical_ratio(blocks, resamples=1000, confidence=0.999)
        result = hierarchical_ratio(blocks, resamples=5000, confidence=0.99)
        self.assertAlmostEqual(2, result["lower"])
        self.assertAlmostEqual(2, result["upper"])
        self.assertNotIn("lower95", result)
        self.assertEqual(0.99, result["confidenceLevel"])


if __name__ == "__main__":
    unittest.main()
