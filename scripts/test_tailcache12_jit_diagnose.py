import pathlib
import tempfile
import unittest

from tailcache12_jit_diagnose import classify_tasks


class JitDiagnosisTest(unittest.TestCase):
    def test_worker_and_cleanup_events_are_kept_separate_with_clock_uncertainty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            gc = root / "gc.log"
            gc.write_text("[0ms][100000000000ns][info][gc] Using G1\n")
            xml = root / "jit.xml"
            xml.write_text('''<hotspot_log><compilation_log>
                <task method="hot" compile_id="1" stamp="1.010"><task_done stamp="1.012" success="1"/></task>
                <task method="cleanup" compile_id="2" stamp="1.030"><task_done stamp="1.050" success="1"/></task>
                <task method="startup" compile_id="3" stamp="0.010"><task_done stamp="0.020" success="1"/></task>
                <task method="unfinished" compile_id="4" stamp="2.0"/>
                </compilation_log><tty><deoptimized compile_id="1" stamp="1.015"/></tty></hotspot_log>''')
            result = classify_tasks(xml, gc, [(101_000_000_000, 101_020_000_000)])
            where = {t["method"]: t["location"] for t in result["tasks"]}
            self.assertEqual("possible-worker-overlap", where["hot"])
            self.assertEqual("after-worker-windows", where["cleanup"])
            self.assertEqual("outside-worker-windows", where["startup"])
            self.assertEqual(1, result["alignmentUncertaintyMs"])
            self.assertEqual(1, result["incompleteCompilerTasks"])
            self.assertEqual(1, len(result["deoptimizationEvents"]))
            gc.write_text("[info][gc] Using G1\n")
            with self.assertRaises(ValueError):
                classify_tasks(xml, gc, [(101_000_000_000, 101_020_000_000)])


if __name__ == "__main__":
    unittest.main()
