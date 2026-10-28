import csv
import json
import pathlib
import tempfile
import unittest

from tailcache12 import HOST_RULE_VERSION
from tailcache12_quiet import replay_preflight


class QuietReplayTest(unittest.TestCase):
    def write(self, directory, cpu=2, version=5, times=range(61)):
        base = dict(monotonicNs=1, memoryFullAvg10=0, memoryFullTotalUs=0,
                    swapInPages=0, swapOutPages=0, governor="fixed", externalPower="AC=1",
                    windowsHostRequired=1, windowsMonitorVersion=version, windowsSampleAgeMs=100,
                    windowsAvailableMiB=8192, windowsCommitPercent=20,
                    windowsOtherCpuPercent=2, windowsPowerScheme="fixed", windowsCpuCounter="root")
        rows = [dict(base, monotonicNs=1+t*10**9,
                     windowsOtherCpuPercent=cpu if i == 1 else 2) for i, t in enumerate(times)]
        path = pathlib.Path(directory)
        with (path / "host.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, list(base))
            writer.writeheader()
            writer.writerows(rows)
        (path / "quiet.json").write_text(json.dumps(dict(stage="quiet-preflight", sourceSha256="fixed",
            hostRuleVersion=HOST_RULE_VERSION, requiredQuietSeconds=60, timeoutSeconds=300,
            sampleCount=len(rows), elapsedSeconds=times[-1], quietPass=True, monitorFailure=None)))
        return path

    def test_quiet_is_reconstructed_and_cannot_be_forced_by_summary_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(directory)
            self.assertTrue(replay_preflight(path, "fixed")["quietPass"])
            self.write(directory, cpu=23)
            with self.assertRaises(ValueError):
                replay_preflight(path, "fixed")
            self.write(directory, cpu=23, times=range(63))
            self.assertTrue(replay_preflight(path, "fixed")["quietPass"])

    def test_changed_source_version_and_nonadvancing_clock_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(directory)
            with self.assertRaises(ValueError):
                replay_preflight(path, "different")
            self.write(directory, version=4)
            with self.assertRaises(ValueError):
                replay_preflight(path, "fixed")
            self.write(directory, times=(0, 30, 30))
            with self.assertRaises(ValueError):
                replay_preflight(path, "fixed")
            self.write(directory, times=(0, 60))
            with self.assertRaises(ValueError):
                replay_preflight(path, "fixed")


if __name__ == "__main__":
    unittest.main()
