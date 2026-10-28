import copy
import csv
import json
import pathlib
import tempfile
import tarfile
import unittest
from unittest.mock import patch

from tailcache12_calibration_retry import CPU_REASON, declare_policy, select
import tailcache12_calibrate as calibration
from tailcache12 import HOST_RULE_VERSION


class CalibrationRetryTest(unittest.TestCase):
    def manifest(self, count=2, retries=2, budget=8):
        slots = [dict(label=f"slot{i}", properties=dict(Seed=24301, Slot=i)) for i in range(count)]
        return dict(stage="calibrate", expectedBlocks=[s["label"] for s in slots],
                    logicalSlots=slots, calibrationHostCpuRetryPolicy=declare_policy(retries, budget))

    def row(self, slot, ordinal=1, host=None, other=None, latency=1):
        return dict(label=f"slot{slot}-q{ordinal}", inputs=dict(Seed=24301, Slot=slot),
                    rejectionReasons=other or [], hostRejectionReasons=host or [],
                    hostPass=not host, nativeHostVersions=[5], serviceP999Ns=latency)

    def test_first_pass_is_kept_regardless_of_latency_and_cannot_be_replaced(self):
        m = self.manifest(1)
        a = self.row(0, latency=10**12)
        result = select(m, [a])
        self.assertTrue(result["complete"])
        self.assertEqual(["slot0-q1"], result["selectedLabels"])
        with self.assertRaises(ValueError):
            select(m, [a, self.row(0, 2, latency=1)])

    def test_only_cpu_failure_advances_same_slot_then_preserves_original_order(self):
        m = self.manifest()
        bad = self.row(0, host=[CPU_REASON], latency=1)
        pending = select(m, [bad])
        self.assertTrue(pending["nextCandidate"]["requiresQuietPreflight"])
        self.assertEqual("slot0-q2", pending["nextCandidate"]["label"])
        result = select(m, [bad, self.row(0, 2, latency=999999), self.row(1)])
        self.assertTrue(result["complete"])
        self.assertEqual(["slot0-q2", "slot1-q1"], result["selectedLabels"])
        self.assertEqual(["slot0-q1"], result["excludedLabels"])
        self.assertEqual(1, result["extraJvms"])

    def test_per_slot_and_total_budgets_stop_incomplete_grids(self):
        m = self.manifest()
        rows = [self.row(0, n, host=[CPU_REASON]) for n in (1, 2, 3)]
        result = select(m, rows)
        self.assertIsNone(result["nextCandidate"])
        self.assertIn("per-slot", result["terminalRejectionReasons"][0])
        with self.assertRaises(ValueError):
            select(m, rows + [self.row(0, 4)])
        m = self.manifest(budget=1)
        result = select(m, [self.row(0, host=[CPU_REASON]), self.row(0, 2),
                            self.row(1, host=[CPU_REASON])])
        self.assertIsNone(result["nextCandidate"])
        self.assertIn("total", result["terminalRejectionReasons"][0])

    def test_other_quality_and_observer_failures_never_receive_retry(self):
        for row in (self.row(0, other=["compiler iteration exceeds 10 ms"]),
                    self.row(0, host=[CPU_REASON, "stale host samples"]),
                    self.row(0, host=["host paging"]),
                    dict(self.row(0, host=[CPU_REASON]), nativeHostVersions=[4])):
            result = select(self.manifest(), [row])
            self.assertIsNone(result["nextCandidate"])
            self.assertTrue(result["terminalRejectionReasons"])

    def test_changed_controls_order_and_policy_fail_closed(self):
        for row in (self.row(1), self.row(0, 2),
                    dict(self.row(0), inputs=dict(Seed=99, Slot=0))):
            with self.assertRaises(ValueError):
                select(self.manifest(), [row])
        for change in (dict(stage="pilot"), dict(expectedBlocks=["slot1", "slot0"])):
            with self.assertRaises(ValueError):
                select(dict(self.manifest(), **change), [])
        m = copy.deepcopy(self.manifest())
        m["calibrationHostCpuRetryPolicy"]["latencyEndpointsUsed"] = True
        with self.assertRaises(ValueError):
            select(m, [])
        for args in ((3, 8), (2, 9), (2, 0), (True, 8)):
            with self.assertRaises(ValueError):
                declare_policy(*args)
        self.assertIsNone(declare_policy(0))


class CalibrationRetryAuditTest(unittest.TestCase):
    def declaration(self, directory):
        policy = declare_policy(2)
        inputs = dict(liveBytes=[x*1024**2 for x in (0, 96, 208, 288)], payloads=[256, 4096],
                      warmups=60, measurements=8, residents=32768, heapMiB=512,
                      churnBytesPerSecond=33554432, seed=24301, repeats=2,
                      channels=list(calibration.CHANNELS), calibrationHostCpuRetryPolicy=policy)
        slots = [dict(label=label, properties=calibration.command_properties(props))
                 for label, props in calibration.calibration_grid(inputs)]
        m = dict(stage="calibrate", schemaVersion="tailcache12-calibration-v2-hostcpu-retry",
                 inputs=inputs, expectedBlocks=[s["label"] for s in slots], logicalSlots=slots,
                 calibrationHostCpuRetryPolicy=policy, sourceSha256="fixed", retryPreflights={},
                 measurementSourceSha256="measurement-fixture",
                 hostObservationDeclaration=dict(historyFile="/native/history.jsonl", monitorVersion=5,
                                                 powerScheme="fixed", cpuCounter="root"))
        data = {key: m[key] for key in ("calibrationHostCpuRetryPolicy", "logicalSlots",
                                      "sourceSha256", "measurementSourceSha256", "hostObservationDeclaration")}
        path = pathlib.Path(directory) / "retry-policy.json"
        path.write_text(json.dumps(data))
        m["retryPolicySha256"] = calibration.sha(path)
        return m

    def quiet(self, path):
        path.mkdir(parents=True)
        base = dict(monotonicNs=1, memoryFullAvg10=0, memoryFullTotalUs=0,
                    swapInPages=0, swapOutPages=0, governor="fixed", externalPower="AC=1",
                    windowsHostRequired=1, windowsMonitorVersion=5, windowsSampleAgeMs=100,
                    windowsAvailableMiB=8192, windowsCommitPercent=20,
                    windowsOtherCpuPercent=2, windowsPowerScheme="fixed", windowsCpuCounter="root")
        with (path / "host.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, list(base))
            writer.writeheader()
            writer.writerows(dict(base, monotonicNs=3*10**9+n*10**9) for n in range(61))
        (path / "quiet.json").write_text(json.dumps(dict(stage="quiet-preflight", sourceSha256="fixed",
            hostRuleVersion=HOST_RULE_VERSION, requiredQuietSeconds=60, timeoutSeconds=300,
            sampleCount=61, elapsedSeconds=60.1, quietPass=True, monitorFailure=None)))
        return dict(sha256={n: calibration.sha(path/n) for n in ("host.csv", "quiet.json")})

    def test_frozen_schedule_has_64_slots_and_replays_declared_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            p = pathlib.Path(directory)
            m = self.declaration(p)
            slots = m["logicalSlots"]
            self.assertEqual(64, len(slots))
            self.assertEqual([s["properties"] for s in slots[:32]],
                             [s["properties"] for s in reversed(slots[32:])])
            self.assertEqual(m["calibrationHostCpuRetryPolicy"], calibration.verify_retry_declaration(p, m))
            changed = copy.deepcopy(m)
            changed["logicalSlots"][0]["properties"]["Seed"] = 99
            with self.assertRaises(ValueError):
                calibration.verify_retry_declaration(p, changed)
            (p / "retry-policy.json").write_text("changed")
            with self.assertRaises(ValueError):
                calibration.verify_retry_declaration(p, m)

    def test_retry_requires_hashed_quiet_raw_before_its_own_block(self):
        with tempfile.TemporaryDirectory() as directory:
            p = pathlib.Path(directory)
            m = self.declaration(p)
            slot = m["logicalSlots"][0]
            base = dict(inputs=slot["properties"], rejectionReasons=[], nativeHostVersions=[5])
            rows = [dict(base, label=slot["label"]+"-q1", hostPass=False, hostRejectionReasons=[CPU_REASON], hostWindowEndNs=2*10**9),
                    dict(base, label=slot["label"]+"-q2", hostPass=True, hostRejectionReasons=[],
                         hostWindowStartNs=70*10**9)]
            label = rows[-1]["label"]
            selection = select(m, rows)
            with self.assertRaises(ValueError):
                calibration.verify_retry_preflights(p, m, rows, selection)
            path = p / "retry-preflights" / label
            m["retryPreflights"][label] = self.quiet(path)
            verified, errors = calibration.verify_retry_preflights(p, m, rows, selection)
            self.assertEqual([], errors)
            self.assertTrue(verified[label]["quietPass"])
            changed = copy.deepcopy(rows)
            changed[-1]["hostWindowStartNs"] = 500*10**9
            with self.assertRaises(ValueError):
                calibration.verify_retry_preflights(p, m, changed, selection)
            with (path / "host.csv").open("a") as stream:
                stream.write("tampered\n")
            with self.assertRaises(ValueError):
                calibration.verify_retry_preflights(p, m, rows, selection)

    def test_driver_checks_quiet_before_retry_and_never_launches_after_quiet_rejection(self):
        for quiet_pass in (True, False):
            with self.subTest(quiet_pass=quiet_pass), tempfile.TemporaryDirectory() as directory:
                p = pathlib.Path(directory)
                m = self.declaration(p)
                slot = m["logicalSlots"][0]
                candidate = dict(label=slot["label"]+"-q2", properties=slot["properties"],
                                 requiresQuietPreflight=True)
                pending = dict(hostCpuRetryState=dict(nextCandidate=candidate), retryPreflightRejectionReasons=[])
                checked = dict(pending, retryPreflightRejectionReasons=[] if quiet_pass else ["quiet rejected"],
                               replayedRetryPreflights={candidate["label"]: dict(quietPass=quiet_pass, lastMonotonicNs=0)})
                finished = dict(hostCpuRetryState=dict(nextCandidate=None), retryPreflightRejectionReasons=[])
                events = []
                def preflight(path, *_):
                    events.append("quiet")
                    path.mkdir(parents=True)
                    for name in ("host.csv", "quiet.json"):
                        (path / name).write_text("retained")
                native = dict(windowsMonitorVersion=5, windowsPowerScheme="fixed", windowsCpuCounter="root")
                env = dict(TAILCACHE_REQUIRE_WINDOWS_HOST="1", TAILCACHE_WINDOWS_HOST_FILE="/native/history.jsonl")
                with patch.dict(calibration.os.environ, env), \
                     patch.object(calibration, "replay", side_effect=[pending, checked, finished]), \
                     patch.object(calibration.evidence, "host_snapshot", return_value=native), \
                     patch.object(calibration, "run_preflight", side_effect=preflight), \
                     patch.object(calibration.time, "monotonic_ns", return_value=10**9), \
                     patch.object(calibration.evidence, "invoke", side_effect=lambda *_: events.append("JVM")):
                    calibration.run_retry_grid(p, m)
                self.assertEqual(["quiet", "JVM"] if quiet_pass else ["quiet"], events)

    def test_complete_grid_replay_keeps_invalid_attempt_and_uses_64_quality_passing_slots(self):
        # Parser contracts have separate tests. Exercise real artifact hashes, host
        # gates, preflight replay, slot selection and occupancy aggregation together.
        with tempfile.TemporaryDirectory() as directory:
            p = pathlib.Path(directory) / "calibration-fixture"
            p.mkdir()
            m = self.declaration(p)
            with tarfile.open(p / "source.tar.gz", "w:gz"):
                pass
            m.update(analysisVersion=calibration.VERSION, hostRuleVersion=HOST_RULE_VERSION,
                     sourceArchiveSha256=calibration.sha(p / "source.tar.gz"), invocations=[])
            trace = "1"*64
            for index, slot in enumerate(m["logicalSlots"]):
                for ordinal in ((1, 2) if index == 0 else (1,)):
                    label = slot["label"] + f"-q{ordinal}"
                    props = slot["properties"]
                    control = p / label
                    control.mkdir()
                    raw = pathlib.Path(directory) / ("raw-" + label)
                    raw.mkdir()
                    start = (1 if index == 0 and ordinal == 1 else 70 if index == 0 else 200+index*2)*10**9
                    channel = props["Channel"]
                    base = raw / channel
                    base.mkdir()
                    if channel == "every-operation":
                        worker = base / "worker"
                        worker.mkdir()
                        (worker / "configuration.txt").write_text(
                            f"backend={props['Backend']}\ntraceSha256={trace}\nvalueGenerator=xorshift-key-version-v1\n"
                            f"jdkVersion=21\njvmArgs=-Xms512m -Xmx512m\n"
                            f"config=Config[residentEntries=32768, payloadBytes={props['Payload']}, "
                            f"applicationLiveBytes={props['LiveBytes']}, seed=24301]\n")
                        timing = worker / "iterations.csv"
                    else:
                        (base / "results.json").write_text(json.dumps([dict(jmhVersion="1.37", jdkVersion="21",
                            vmName="Fixture VM", vmVersion="21")]))
                        (base / "jmh.txt").write_text("traceSha256=" + trace)
                        timing = base / "iterations-fixture.csv"
                    timing.write_text(f"phase,startNs,endNs\nMEASUREMENT,{start},{start+10**9}\n")
                    host = dict(monotonicNs=start, memoryFullAvg10=0, memoryFullTotalUs=0,
                        swapInPages=0, swapOutPages=0, governor="fixed", externalPower="AC=1",
                        windowsHostRequired=1, windowsMonitorVersion=5, windowsSampleAgeMs=100,
                        windowsAvailableMiB=8192, windowsCommitPercent=20,
                        windowsOtherCpuPercent=23 if index == 0 and ordinal == 1 else 2,
                        windowsPowerScheme="fixed", windowsCpuCounter="root", windowsIntervalMs=1000)
                    with (control / "host.csv").open("w", newline="") as stream:
                        writer = csv.DictWriter(stream, list(host))
                        writer.writeheader()
                        writer.writerows([host, dict(host, monotonicNs=start+10**9)])
                    (control / "gradle.log").write_text("fixture")
                    m["invocations"].append(dict(label=label, properties=props, rawDirectory=str(raw),
                        sourceUnchanged=True, exitCode=0, hostMonitorErrors=[],
                        rawSha256={f.relative_to(raw).as_posix(): calibration.sha(f) for f in raw.rglob("*") if f.is_file()},
                        controlSha256={f.name: calibration.sha(f) for f in control.iterdir()}))
            retry_label = m["logicalSlots"][0]["label"] + "-q2"
            m["retryPreflights"][retry_label] = self.quiet(p / "retry-preflights" / retry_label)
            (p / "manifest.json").write_text(json.dumps(m))
            def parsed(props):
                fraction = {0: .1, 96: .35, 208: .6, 288: .85}[props["LiveBytes"] // 1024**2]
                return dict(rejectionReasons=[], jdkVersion="21", postGcUsedHeapMedianFraction=fraction,
                    oldRegionsMedianHeapFraction=fraction, pauseCount=2, pauseOverlapMs=1, pausesPerSecond=.25,
                    servicePercentilesNs={"99": 100, "99.9": 200})
            with patch.object(calibration, "archive_measurement_source_hash", return_value="measurement-fixture"), \
                 patch.object(calibration, "every_operation_fork_summary", side_effect=lambda path, props: parsed(props)), \
                 patch.object(calibration, "jmh_fork_summary", side_effect=lambda raw, channel, props, *rest: dict(parsed(props), gc=parsed(props))):
                result = calibration.replay(p)
                self.assertTrue(result["calibrationReady"])
                self.assertEqual(64, result["completedBlocks"])
                self.assertEqual(65, result["recordedJvmAttempts"])
                self.assertEqual(1, len(result["rejectedCandidateAttempts"]))
                self.assertFalse(result["observations"][0]["selectedForCalibration"])
                self.assertTrue(result["observations"][1]["selectedForCalibration"])
                self.assertEqual(32, len(result["calibrationBands"]))
                # Removing the prospective policy does not make the invalid attempt
                # disappear under the unchanged legacy interpretation.
                del m["calibrationHostCpuRetryPolicy"]
                m["schemaVersion"] = "tailcache12-calibration-v1"
                (p / "manifest.json").write_text(json.dumps(m))
                self.assertFalse(calibration.replay(p)["calibrationReady"])


if __name__ == "__main__":
    unittest.main()
