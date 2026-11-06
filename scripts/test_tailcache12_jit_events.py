import pathlib
import tempfile
import unittest

from tailcache12_jit_events import grid,parse_events,worker_xml,worker_gc,TASKS,validate_logging_channels


class JitEventTest(unittest.TestCase):
    def test_floor_diagnostic_uses_real_task_and_same_controls_without_relaxing_logging(self):
        build=(pathlib.Path(__file__).resolve().parents[1]/'build.gradle.kts').read_text()
        self.assertIn('registerTailCache12Jmh("'+TASKS['floor']+'", "floor")',build)
        plan=grid(6,[4096],['floor'],'CAFFEINE',0,8,True,True)
        self.assertEqual(6,len(plan))
        for _,p in plan:
            self.assertEqual(('floor','CAFFEINE',4096,0,120,8,8),
                tuple(p[k] for k in ('Channel','Backend','Payload','LiveBytes','Warmups','Conditioning','Measurements')))
            self.assertEqual('lifecycle-maintenance-v1',p['LifecycleWarmupVersion'])
        for channel in ('floor','sample-calibration'):
            validate_logging_channels([channel],True,False)
            validate_logging_channels([channel],False,True)
        validate_logging_channels(['every-operation'],True,False)
        for channels,attach,xml in ((['floor'],True,True),
                (['floor','sample-calibration'],True,False),(['floor','floor'],False,False),
                (['unknown'],False,False),(['every-operation'],False,True)):
            with self.assertRaises(ValueError): validate_logging_channels(channels,attach,xml)

    def test_targeted_pressure_diagnostic_preserves_exact_preparation_controls(self):
        plan=grid(3,[4096],["sample-calibration"],"CHRONICLE_IN_MEMORY",208*1024**2,8,True)
        self.assertEqual(3,len(plan))
        for _,p in plan:
            self.assertEqual("CHRONICLE_IN_MEMORY",p["Backend"])
            self.assertEqual(p["Backend"],p["Backends"])
            self.assertEqual(218103808,p["LiveBytes"])
            self.assertEqual(8,p["Conditioning"])
            self.assertEqual("jmh-result-transport-v2",p["TransportWarmupVersion"])
            self.assertEqual((120,8),(p["Warmups"],p["Measurements"]))

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

    def test_diagnostic_gc_clock_selects_actual_worker_among_parent_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            for pid in (12,42,99): (root/f'diagnostic-gc-{pid}.log').write_text('clock')
            self.assertEqual(root/'diagnostic-gc-42.log',worker_gc(root,'42'))
            (root/'diagnostic-gc-42.log').unlink()
            with self.assertRaises(ValueError): worker_gc(root,'42')


if __name__=="__main__": unittest.main()
