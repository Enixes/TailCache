import unittest
import csv
import json
import pathlib
import tempfile
from unittest.mock import patch

from tailcache12_study_analysis import (every_operation_fork_summary, hierarchical_ratio,
                                       jmh_fork_summary, merged_histograms, variance_reasons)


class StudyAnalysisTest(unittest.TestCase):
    def test_every_operation_controls_and_compiler_gate_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            worker = root / "worker"
            worker.mkdir()
            inputs = dict(Backend="CAFFEINE", Payload=256, Residents=8192, LiveBytes=0,
                          ChurnBytesPerSecond=1024, Seed=24301, Warmups=60, Measurements=8, HeapMiB=512)
            configuration = ("backend=CAFFEINE\nconfig=CrossoverConfig[residentEntries=8192, payloadBytes=256, "
                             "seed=24301, applicationLiveBytes=0, churnBytesPerSecond=1024]\n"
                             "jvmArgs=[-Xms512m, -Xmx512m, -XX:+UseG1GC]\ncompilerCounters=true\n"
                             "compilerXml=false\nvalueGenerator=xorshift-key-version-v1\ntraceSha256=abc\n"
                             "jdkVersion=21.0.12.1\noptions={--warmup=60, --measure=8, --iteration-ms=1000}\n")
            path = worker / "configuration.txt"
            path.write_text(configuration)
            (worker / "integrity.txt").write_text("contentChecksum=1\napplicationChecksum=2\nconsumed=3\noperations=680000\nwrites=34000\n")
            with (worker / "iterations.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["phase", "iteration", "startNs", "endNs", "operations", "writes"])
                writer.writeheader()
                writer.writerows(dict(phase=phase, iteration=i, startNs=1, endNs=1_000_000_001,
                                      operations=10000, writes=500)
                                 for phase, count in (("WARMUP", 60), ("MEASUREMENT", 8))
                                 for i in range(1, count + 1))
            def summary(compiler):
                return dict(rejectionReasons=[], compilerPerIterationMs=compiler, p999Adequate=True)
            with patch("tailcache12_study_analysis.every_operation_summary", return_value=summary([0] * 8)):
                self.assertTrue(every_operation_fork_summary(root, inputs, "abc", "21.0.12.1")["accepted"])
                with self.assertRaises(ValueError):
                    every_operation_fork_summary(root, inputs, "different-trace")
            with patch("tailcache12_study_analysis.every_operation_summary", return_value=summary([11] + [0] * 7)):
                result = every_operation_fork_summary(root, inputs)
                self.assertFalse(result["accepted"])
                self.assertIn("compiler iteration exceeds 10 ms", result["rejectionReasons"])
            path.write_text(configuration.replace("--warmup=60", "--warmup=12"))
            with self.assertRaises(ValueError):
                every_operation_fork_summary(root, inputs)
            path.write_text(configuration.replace("compilerXml=false", "compilerXml=true"))
            with self.assertRaises(ValueError):
                every_operation_fork_summary(root, inputs)
            path.write_text(configuration)
            (worker / "integrity.txt").write_text("contentChecksum=1\napplicationChecksum=2\nconsumed=3\noperations=1\nwrites=34000\n")
            with self.assertRaises(ValueError):
                every_operation_fork_summary(root, inputs)

    def test_primary_fork_requires_matching_runtime_inputs_and_unprofiled_data(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = pathlib.Path(directory)
            sample = raw / "sample"
            sample.mkdir()
            inputs = dict(Backend="CAFFEINE", Payload=256, Residents=8192, LiveBytes=0,
                          ChurnBytesPerSecond=1024, Seed=24301, Warmups=60, Measurements=8, HeapMiB=512)
            runtime = dict(jmhVersion="1.37", jdkVersion="21.0.12.1", vmName="OpenJDK", vmVersion="test-build")
            record = dict(runtime, forks=1, threads=1, mode="sample", warmupIterations=60,
                          measurementIterations=8, measurementTime="1 s", warmupTime="1 s",
                          jvmArgs=["-Xms512m", "-Xmx512m", "-XX:+UseG1GC"],
                          params=dict(backend="CAFFEINE", payloadBytes="256", residentEntries="8192",
                                      applicationLiveBytes="0", churnBytesPerSecond="1024", seed="24301"),
                          primaryMetric={"scoreUnit": "ns/op", "rawDataHistogram": [[[[100, 25000]] for _ in range(8)]],
                                         "scorePercentiles": {"99.0": 100}},
                          secondaryMetrics={"p0.99": {"score": 100, "scoreUnit": "ns/op"}})
            path = sample / "results.json"
            path.write_text(json.dumps([record]))
            trace = "a" * 64
            (sample / "jmh.txt").write_text(f"traceSha256={trace} valueGenerator=xorshift-key-version-v1\n[TailCache12][integrity] checksum=1\n")
            rows = [dict(phase="MEASUREMENT", envelopeStartNs=(i + 1) * 1_000_000_000,
                         envelopeEndNs=(i + 2) * 1_000_000_000, operations=100000,
                         workerEnvelopeCompilerMs=0, churnPayloadBytesPerSecond=1024,
                         churnDroppedBytes=0, churnJvmAllocatedBytes=1024, churnPayloadBytes=1024)
                    for i in range(8)]
            with (sample / "iterations-1.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            result = jmh_fork_summary(raw, "sample", inputs, trace, runtime)
            self.assertTrue(result["accepted"])
            self.assertEqual(200000, result["sampleCount"])
            record["secondaryMetrics"] = {"gc.alloc.rate": {"score": 1}}
            path.write_text(json.dumps([record]))
            with self.assertRaises(ValueError):
                jmh_fork_summary(raw, "sample", inputs, trace, runtime)
            record["secondaryMetrics"] = {}
            record["vmVersion"] = "changed-build"
            path.write_text(json.dumps([record]))
            with self.assertRaises(ValueError):
                jmh_fork_summary(raw, "sample", inputs, trace, runtime)

    def test_histogram_queries_preserve_counts_and_do_not_average_percentiles(self):
        result = merged_histograms([[(10, 99), (1000, 1)], [(20, 100)]], [1000, 1000])
        self.assertEqual(200, result["sampleCount"])
        self.assertEqual(20, result["servicePercentilesNs"]["99"])
        self.assertEqual(1000, result["servicePercentilesNs"]["99.9"])
        straddling = merged_histograms([[(999424, 1)]], [100])
        self.assertEqual({"lower": 0, "upper": 1}, straddling["sampledStallCountBounds"]["1000000"])
        for bins, operations in (([[(10, 101)]], [100]), ([[(10, 1), (9, 1)]], [100]),
                                 ([[(10, 0)]], [100]), ([[(10.5, 1)]], [100])):
            with self.assertRaises(ValueError):
                merged_histograms(bins, operations)

    def test_bootstrap_uses_forks_and_passes_as_replication_units(self):
        result = hierarchical_ratio([[(10, 20), (20, 40), (30, 60)],
                                     [(12, 24), (22, 44), (32, 64)]], resamples=1000)
        self.assertAlmostEqual(2, result["ratio"])
        self.assertAlmostEqual(2, result["lower95"])
        self.assertAlmostEqual(2, result["upper95"])
        self.assertEqual([3, 3], result["pairedForksPerPass"])
        with self.assertRaises(ValueError):
            hierarchical_ratio([[(1, 2)] * 3])
        with self.assertRaises(ValueError):
            hierarchical_ratio([[(0, 2)] * 3] * 2)

    def test_variance_gate_retains_instability_instead_of_removing_forks(self):
        blocks = {"CAFFEINE": [[{"99": 10, "99.9": 10}] * 3,
                               [{"99": 20, "99.9": 20}] * 3]}
        reasons = variance_reasons(blocks)
        self.assertTrue(any("p99 between-order" in reason for reason in reasons))
        self.assertTrue(any("p99.9 between-order" in reason for reason in reasons))
