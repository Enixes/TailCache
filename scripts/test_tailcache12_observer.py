import csv
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import tailcache12_observer as observer

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

    def test_complete_floor_replay_combines_parser_fields_and_checks_exact_timer_vm(self):
        # Exercise assembly of all ten JVM summaries, including fields already
        # returned by the JMH parser and the actual timer metadata/histogram path.
        with tempfile.TemporaryDirectory() as directory:
            attempt=pathlib.Path(directory)/"floor-fixture"
            attempt.mkdir()
            (attempt/"source.tar.gz").write_bytes(b"source-fixture")
            runtime=dict(jmhVersion="1.37",jdkVersion="21.0.12.1",vmName="fixture-vm",vmVersion="exact-build")
            grid=floor_grid(12)
            invocations=[]
            timers=[]
            for label,props in grid:
                control=attempt/label
                control.mkdir()
                (control/"gradle.log").write_text("traceSha256="+"a"*64)
                (control/"host.csv").write_text("monotonicNs,nativeObserverReadDurationNs\n1,1000000\n2,1000000\n")
                if props["Channel"]=="floor":
                    raw=control/"floor"
                    raw.mkdir()
                    (raw/"results.json").write_text(json.dumps([runtime]))
                    (raw/"jmh.txt").write_text("traceSha256="+"a"*64)
                else:
                    worker=control/"every-operation/worker"
                    worker.mkdir(parents=True)
                    config=worker/"configuration.txt"
                    config.write_text("timerFloor=true\nvalidation=none\ncompilerXml=false\ncompilerCounters=true\n"
                        "jdkVersion=21.0.12.1\nvmName=fixture-vm\nvmVersion=exact-build\n"
                        "jvmArgs=[-Xms512m, -Xmx512m, -XX:+UseG1GC]\n"
                        "options={--warmup=12, --measure=8, --iteration-ms=1000}\n")
                    timers.append(config)
                    with (worker/"iterations.csv").open("w",newline="") as stream:
                        writer=csv.DictWriter(stream,["phase","iteration","startNs","endNs","operations","compilerMs"])
                        writer.writeheader()
                        for phase,count in (("WARMUP",12),("MEASUREMENT",8)):
                            for i in range(1,count+1):
                                writer.writerow(dict(phase=phase,iteration=i,startNs=0,endNs=10**9,operations=10,compilerMs=0))
                                if phase=="MEASUREMENT":
                                    (worker/f"iteration-{i}-service-bins.csv").write_text("upperEquivalentNs,count\n100,10\n")
                invocations.append(dict(label=label,properties=props))
            manifest=dict(stage="observer-floor",observerRules=RULES,sourceArchiveSha256=observer.calibration.sha(attempt/"source.tar.gz"),
                inputs=dict(warmups=12),expectedBlocks=[k for k,v in grid],invocations=invocations)
            (attempt/"manifest.json").write_text(json.dumps(manifest))
            def parsed(raw,kind,props,*_):
                return dict(inputs=props,accepted=True,rejectionReasons=[],servicePercentilesNs={"50":100})
            with patch.object(observer.calibration,"verify_invocation",side_effect=lambda a,i:a/i["label"]), \
                 patch.object(observer,"jmh_fork_summary",side_effect=parsed), \
                 patch.object(observer.evidence,"pause_audit",return_value=dict(pass_=True)), \
                 patch.object(observer.evidence,"replay_host_gate",return_value=([],0)):
                result=observer.replay_floors(attempt)
                self.assertTrue(result["floorDataPass"])
                self.assertEqual(10,result["completedBlocks"])
                self.assertEqual(runtime,result["runtimeIdentity"])
                timers[0].write_text(timers[0].read_text().replace("vmVersion=exact-build","vmVersion=other-build"))
                with self.assertRaises(ValueError): observer.replay_floors(attempt)


if __name__ == "__main__":
    unittest.main()
