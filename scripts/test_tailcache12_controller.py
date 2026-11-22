import unittest
from unittest.mock import patch

from tailcache12_controller import launch_delay, wait_for_launch


class ControllerScheduleTest(unittest.TestCase):
    def test_boundaries_wrap_and_negative_phase(self):
        for now, expected in ((1000, 120), (1119, 1), (1120, 0), (1719, 0),
                              (1720, 300), (1899, 121), (1900, 120), (999, 121)):
            self.assertEqual(launch_delay(now, 1000, 900, 180, 120), expected)

    def test_invalid_schedule_fails_closed(self):
        for values in ((0, 0, 900, 800, 100), (0, 0, 0, 0, 0),
                       (0, 0, 900, -1, 0), (float("nan"), 0, 900, 180, 120),
                       (0, float("inf"), 900, 180, 120)):
            with self.assertRaises(ValueError):
                launch_delay(*values)

    def test_disabled_schedule_and_multiple_fork_budget(self):
        self.assertIsNone(wait_for_launch({}, {}))
        with patch("tailcache12_controller.time.time", return_value=1400):
            result = wait_for_launch(dict(Warmups=60, Measurements=8, Forks=2,
                Backends="CAFFEINE,CHRONICLE_IN_MEMORY", Payloads="256"),
                {"TAILCACHE_CONTROLLER_ANCHOR_UNIX_SECONDS": "1000"})
        self.assertEqual(result["estimatedInvocationSeconds"], 362)
        self.assertEqual(result["beforeSeconds"], 362)

    def test_wait_finishes_before_returning_launch_metadata(self):
        with patch("tailcache12_controller.time.time", side_effect=[1119, 1120, 1120]), \
             patch("tailcache12_controller.time.monotonic", side_effect=[50, 51]), \
             patch("tailcache12_controller.time.sleep") as sleep:
            result = wait_for_launch(dict(Warmups=60, Measurements=8),
                {"TAILCACHE_CONTROLLER_ANCHOR_UNIX_SECONDS": "1000"})
        sleep.assert_called_once_with(1.0)
        self.assertEqual(result["waitedSeconds"], 1)
        self.assertEqual(result["launchUnixSeconds"], 1120)


if __name__ == "__main__":
    unittest.main()
