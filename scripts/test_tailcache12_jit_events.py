import pathlib
import tempfile
import unittest

from tailcache12_jit_events import grid,parse_events,worker_xml


class JitEventTest(unittest.TestCase):
    def test_bounded_balanced_attribution_schedule_and_start_event_semantics(self):
        plan=grid()
        self.assertEqual(16,len(plan))
        for payload in (256,4096):
            for channel in ("every-operation","sample-calibration"):
                self.assertEqual(4,sum(p["Payload"]==payload and p["Channel"]==channel for _,p in plan))
        with tempfile.TemporaryDirectory() as directory:
            path=pathlib.Path(directory)/"events.log"
            path.write_text("[35448743427045ns][17581016ns][debug][jit,compilation]  1 n 0 Class::method (native)\n"
                            "[35448743571284ns][17725259ns][debug][jit,compilation] 2 3 Class::method (1 bytes) made not entrant\n")
            events=parse_events(path)
            self.assertEqual("native-wrapper-event",events[0]["kind"])
            self.assertEqual("invalidation",events[1]["kind"])
            self.assertEqual(35448743427045,events[0]["timestampNs"])
            path.write_text("[35448743427045ns][17581016ns][debug][jit,compilation]  1 4 Class::method (123 bytes)\n")
            self.assertEqual("compiler-task-start",parse_events(path)[0]["kind"])
            self.assertEqual(4,len(grid(4,[4096],["sample-calibration"])))
            path.write_text("unexpected format\n")
            with self.assertRaises(ValueError): parse_events(path)

    def test_actual_worker_xml_pid_expansion_is_unambiguous(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            legacy=root/"hotspot-compile-pid42.xml"
            legacy.write_text("actual-worker")
            (root/"hotspot-compile-pid99.xml").write_text("parent-is-not-worker")
            self.assertEqual(legacy,worker_xml(root,42))
            plain=root/"hotspot-compile-42.xml"
            plain.write_text("ambiguous")
            with self.assertRaises(ValueError): worker_xml(root,42)
            legacy.unlink()
            self.assertEqual(plain,worker_xml(root,42))
            plain.unlink()
            with self.assertRaises(ValueError): worker_xml(root,42)


if __name__=="__main__": unittest.main()
