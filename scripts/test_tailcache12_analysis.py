"""Edge cases that can change campaign acceptance or GC causal claims."""
import pathlib
import tempfile
import unittest
import hashlib

from tailcache12_analysis import gc_summary, histogram, paired_bootstrap, parse_gc, validate_windows
from tailcache12 import host_gate
from tailcache12_calibrate import verify_invocation


class GcAnalysisTest(unittest.TestCase):
    def log(self, lines):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = pathlib.Path(directory.name) / "gc.log"
        prefix = ["[1ms][1000000ns][info][gc] Using G1",
                  "[1ms][1000000ns][info][gc,init] Heap Region Size: 1M",
                  "[1ms][1000000ns][info][gc,init] Heap Max Capacity: 512M"]
        path.write_text("\n".join(prefix + lines) + "\n")
        return path

    def test_pause_crossing_window_edge_is_counted_and_clipped(self):
        parsed = parse_gc(self.log([
            "[10ms][10000000ns][info][gc,start] GC(1) Pause Young (Normal) (G1 Evacuation Pause)",
            "[20ms][20000000ns][info][gc,heap] GC(1) Old regions: 2->10",
            "[20ms][20000000ns][info][gc,heap] GC(1) Humongous regions: 0->0",
            "[20ms][20000000ns][info][gc] GC(1) Pause Young (Normal) (G1 Evacuation Pause) 100M->12M(512M) 10.000ms",
            "[22ms][22000000ns][info][gc] GC(2) Concurrent Mark Cycle",
            "[24ms][24000000ns][info][gc] GC(2) Concurrent Mark Cycle 2.000ms",
        ]))
        result = gc_summary(parsed, [(15_000_000, 25_000_000)], 1000)
        self.assertEqual(1, result["pauseCount"])
        self.assertEqual(10, result["pauseTotalWholeMs"])
        self.assertEqual(5, result["pauseOverlapMs"])
        self.assertEqual(1, result["completedConcurrentCycles"])
        self.assertEqual(12 / 512, result["postGcUsedHeapMedianFraction"])
        self.assertEqual(10 / 512, result["oldRegionsMedianHeapFraction"])

    def test_missing_and_truncated_evidence_fails_closed(self):
        for text in ("[1ms][info][gc] Using G1\n", ""):
            path = self.log([])
            path.write_text(text)
            with self.assertRaises(ValueError):
                parse_gc(path)
        with self.assertRaises(ValueError):
            parse_gc(self.log(["[5ms][5000000ns][info][gc,start] GC(0) Pause Full (System.gc())"]))

    def test_no_gc_is_missing_occupancy_not_zero_live_heap(self):
        result = gc_summary(parse_gc(self.log([])), [(2_000_000, 5_000_000)], 100)
        self.assertEqual(0, result["pauseCount"])
        self.assertIsNone(result["postGcUsedHeapMedianFraction"])

    def test_setup_pauses_are_excluded_and_region_snapshot_is_not_overwritten(self):
        parsed = parse_gc(self.log([
            "[2ms][2000000ns][info][gc,heap] GC(0) Old regions: 1->3",
            "[3ms][3000000ns][info][gc] GC(0) Pause Full (System.gc()) 10M->4M(512M) 1.000ms",
            "[4ms][4000000ns][info][gc,heap] GC(0) Old regions: 3->99",
        ]))
        self.assertEqual(3, parsed["pauses"][0]["regionsAfter"]["old"])
        result = gc_summary(parsed, [(4_000_000, 5_000_000)], 10)
        self.assertEqual(0, result["pauseCount"])

    def test_overlapping_windows_and_histogram_loss_reject(self):
        with self.assertRaises(ValueError):
            validate_windows([(0, 10), (9, 20)])
        path = self.log([])
        path.write_text("upperEquivalentNs,count\n10,99\n")
        with self.assertRaises(ValueError):
            histogram(path, 100)

    def test_statistics_use_independent_block_pairs(self):
        estimate = paired_bootstrap([(100, 50), (200, 100)])
        self.assertEqual(0.5, estimate["ratio"])
        self.assertEqual(2, estimate["independentBlocks"])
        with self.assertRaises(ValueError):
            paired_bootstrap([(1, 2)])

    def test_zswap_reads_and_power_changes_reject_an_apparently_quiet_host(self):
        before = dict(monotonicNs=1, memoryFullAvg10=0, memoryFullTotalUs=0,
                      swapInPages=0, swapOutPages=0, zswpin=10, zswpout=20, oom_kill=0,
                      governor="powersave", externalPower="AC=1")
        after = dict(before, monotonicNs=1_000_000_001, zswpin=11)
        reasons, _ = host_gate([before, after])
        self.assertIn("zswpin counter changed", reasons)
        reasons, _ = host_gate([before, dict(after, zswpin=10, externalPower="AC=0")])
        self.assertIn("externalPower changed during block", reasons)
        self.assertIn("external power is disconnected", reasons)

    def test_copied_evidence_resolves_siblings_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = pathlib.Path(directory) / "calibration"
            raw = pathlib.Path(directory) / "calibration-cell"
            attempt.mkdir()
            raw.mkdir()
            (raw / "log.txt").write_text("raw log\n")
            invocation = dict(label="cell", rawDirectory="/unavailable-original-host/cell", exitCode=0,
                              sourceUnchanged=True, controlSha256={},
                              rawSha256={"log.txt": hashlib.sha256((raw / "log.txt").read_bytes()).hexdigest()})
            self.assertEqual(raw, verify_invocation(attempt, invocation))
            (raw / "log.txt").write_text("changed\n")
            with self.assertRaises(ValueError):
                verify_invocation(attempt, invocation)


if __name__ == "__main__":
    unittest.main()
