"""Edge cases that can change campaign acceptance or GC causal claims."""
import pathlib
import tempfile
import unittest
import hashlib
import csv
import json
from unittest.mock import patch

from tailcache12_analysis import compiler_rejection_reasons, gc_summary, histogram, paired_bootstrap, parse_gc, validate_windows
from tailcache12 import decode_host_row, host_gate, pause_audit, windows_host_snapshot
from tailcache12_calibrate import verify_invocation


class GcAnalysisTest(unittest.TestCase):
    def test_cpu_settling_scope_does_not_waive_full_block_freshness_or_timed_disturbance(self):
        base = dict(memoryFullAvg10=0, memoryFullTotalUs=0, swapInPages=0, swapOutPages=0,
                    windowsHostRequired=1, windowsMonitorVersion=3, windowsSampleAgeMs=100,
                    windowsAvailableMiB=8000, windowsCommitPercent=50, windowsOtherCpuPercent=2,
                    windowsPowerScheme="balanced", windowsIntervalMs=1000)
        rows = [dict(base, monotonicNs=(i + 1) * 1_000_000_000) for i in range(31)]
        rows[1]["windowsOtherCpuPercent"] = 30
        windows = [(20_000_000_000, 28_000_000_000)]
        self.assertEqual([], host_gate(rows, cpu_windows=windows)[0])
        self.assertTrue(host_gate(rows)[0], "Historical full-block CPU rule must still reject")
        rows[24]["windowsOtherCpuPercent"] = 11
        self.assertTrue(any("settling/measurement" in r for r in host_gate(rows, cpu_windows=windows)[0]))
        rows[24]["windowsOtherCpuPercent"] = 2
        rows[1]["windowsSampleAgeMs"] = 6000
        self.assertTrue(any("stale" in r for r in host_gate(rows, cpu_windows=windows)[0]))

    def test_windows_append_reader_ignores_a_partial_last_record(self):
        with tempfile.TemporaryDirectory() as directory:
            history = pathlib.Path(directory) / "history.jsonl"
            row = dict(timestampUnixMs=1000, availableMiB=8000, commitPercent=50,
                       outsideGuestCpuPercent=2, powerScheme="balanced", pageReadsPerSecond=0,
                       pagesOutputPerSecond=0, totalCpuPercent=10, guestCpuPercent=8)
            history.write_text(json.dumps(row) + "\n" + '{"timestampUnixMs":')
            with patch("tailcache12.time.time", return_value=2):
                snapshot = windows_host_snapshot(history, required=True)
            self.assertEqual(1000, snapshot["windowsSampleAgeMs"])
            self.assertEqual(2, snapshot["windowsOtherCpuPercent"])
            self.assertEqual(8, snapshot["windowsGuestCpuPercent"])

    def test_wsl_host_supplement_is_required_fresh_and_quiet(self):
        with self.assertRaises(ValueError):
            windows_host_snapshot(None, required=True)
        before = dict(monotonicNs=1, memoryFullAvg10=0, memoryFullTotalUs=0,
                      swapInPages=0, swapOutPages=0, windowsHostRequired=1,
                      windowsMonitorVersion=3,
                      windowsSampleAgeMs=100, windowsAvailableMiB=8000, windowsCommitPercent=50,
                      windowsOtherCpuPercent=2, windowsPowerScheme="balanced")
        after = dict(before, monotonicNs=1_000_000_001)
        self.assertEqual([], host_gate([before, after])[0])
        for field, value, expected in (
                ("windowsSampleAgeMs", 6000, "stale"), ("windowsAvailableMiB", 4000, "4 GiB"),
                ("windowsCommitPercent", 90, "85%"), ("windowsOtherCpuPercent", 11, "10%"),
                ("windowsCommitPercent", float("nan"), "invalid"),
                ("windowsPowerScheme", "power saver", "power scheme changed")):
            reasons, _ = host_gate([before, dict(after, **{field: value})])
            self.assertTrue(any(expected in reason for reason in reasons), reasons)
        decoded = decode_host_row({k: str(v) for k, v in before.items()})
        self.assertEqual("balanced", decoded["windowsPowerScheme"])
        self.assertEqual(8000, decoded["windowsAvailableMiB"])

    def test_compiler_gate_fails_closed_and_keeps_both_limits(self):
        self.assertEqual([], compiler_rejection_reasons(80, [10] * 8))
        self.assertIn("compiler iteration exceeds 10 ms", compiler_rejection_reasons(11, [11] + [0] * 7))
        self.assertIn("compiler total exceeds 80 ms", compiler_rejection_reasons(81, [10] * 8))
        for total, values in ((0, []), (-1, [0] * 8), (0, [-1] * 8), (float("nan"), [0] * 8)):
            self.assertIn("missing or invalid compiler-time evidence", compiler_rejection_reasons(total, values))

    def test_pause_validation_matches_nanoclock_without_uptime_tolerance(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            worker = base / "every-operation/worker"
            worker.mkdir(parents=True)
            row = dict(phase="MEASUREMENT", iteration=1, operations=1, startNs=1_000_000,
                       endNs=50_000_000, uptimeStartMs=1000, serviceP50Ns=10,
                       serviceP99Ns=10, serviceMaxNs=10, completionGapMaxNs=12_000_000,
                       injectionStartNs=2_000_000, injectionEndNs=40_000_000)
            with (worker / "iterations.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)
            for channel in ("service", "completion-gap"):
                (worker / f"iteration-1-{channel}-bins.csv").write_text("upperEquivalentNs,count\n10,1\n")
            log = self.log([
                "[10ms][10000000ns][info][gc,start] GC(1) Pause Full (System.gc())",
                "[20ms][20000000ns][info][gc] GC(1) Pause Full (System.gc()) 100M->12M(512M) 10.000ms",
            ])
            (base / "every-operation/gc-test.log").write_text(log.read_text())
            events = worker / "iteration-1-stall-events.csv"
            events.write_text("previousCompletionNs,endNs,completionGapNs\n9000000,21000000,12000000\n")
            self.assertTrue(pause_audit(base, "gc")["pass"])
            # Close in uptime milliseconds is insufficient: these intervals do not overlap.
            events.write_text("previousCompletionNs,endNs,completionGapNs\n21000000,33000000,12000000\n")
            self.assertFalse(pause_audit(base, "gc")["pass"])

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

    def test_end_only_evacuation_failure_outcome_matches_actual_start(self):
        start = "[1479ms][1479000000ns][info][gc,start] GC(7) Pause Young (Normal) (G1 Evacuation Pause)"
        end = "[1494ms][1494536000ns][info][gc] GC(7) Pause Young (Normal) (G1 Evacuation Pause) (Evacuation Failure) 446M->345M(512M) 15.536ms"
        parsed = parse_gc(self.log([start, end]))
        pause = parsed["pauses"][0]
        self.assertFalse(pause["startDerivedFromDuration"])
        self.assertEqual(1479000000, pause["startNs"])
        self.assertTrue(pause["evacuationFailure"])
        self.assertTrue(pause["kind"].endswith("(Evacuation Failure)"))
        self.assertEqual(1, gc_summary(parsed, [(1478000000, 1496000000)], 1000)["evacuationFailureCount"])
        self.assertEqual(0, gc_summary(parsed, [(1500000000, 1600000000)], 1000)["evacuationFailureCount"])
        with self.assertRaises(ValueError):
            parse_gc(self.log([start, end.replace("Evacuation Failure", "Unknown Outcome")]))

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

    def test_version5_host_observer_keeps_freshness_and_version_gates(self):
        before = dict(monotonicNs=1, memoryFullAvg10=0, memoryFullTotalUs=0,
                      swapInPages=0, swapOutPages=0, governor="fixed", externalPower="AC=1",
                      windowsHostRequired=1, windowsMonitorVersion=5, windowsSampleAgeMs=100,
                      windowsAvailableMiB=8192, windowsCommitPercent=20,
                      windowsOtherCpuPercent=2, windowsPowerScheme="fixed")
        after = dict(before, monotonicNs=1_000_000_001)
        self.assertEqual([], host_gate([before, after])[0])
        reasons, _ = host_gate([before, dict(after, windowsMonitorVersion=6)])
        self.assertIn("unqualified Windows observer version", reasons)
        reasons, _ = host_gate([before, dict(after, windowsSampleAgeMs=6000)])
        self.assertIn("Windows host observations are stale or clocks disagree", reasons)

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
