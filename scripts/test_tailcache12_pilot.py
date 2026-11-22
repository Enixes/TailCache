import json
import pathlib
import tempfile
import unittest
from collections import Counter
from unittest.mock import patch

from tailcache12_pilot import PRIMARY,TASKS,qualification_refs,schedule,pilot_inputs,declare_native_preparation


class PilotPlanTest(unittest.TestCase):
    def test_stage_inputs_strip_preparation_and_keep_identical_timed_schedule(self):
        calibrated=dict(self.inputs(),initialQuietAttempt='old',qualificationPrefix='old',highFirst=True,
            nativeHostRetryPolicy={'stage':'calibrate'},channels=['sample-calibration','every-operation'],
            conditioning=8,transportWarmupVersion='jmh-result-transport-v2')
        inputs=pilot_inputs(calibrated)
        self.assertEqual(list(TASKS),inputs['channels'])
        self.assertFalse(set(('initialQuietAttempt','qualificationPrefix','highFirst','nativeHostRetryPolicy')) & set(inputs))
        self.assertEqual(schedule(calibrated),schedule(inputs))

    def test_native_pilot_requires_fresh_initial_quiet_before_policy_freeze(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt=pathlib.Path(directory)/'pilot'; host={'nativeScopeQualified':1}
            with patch('tailcache12_pilot.native_retry.initialize') as initialize, \
                 patch('tailcache12_pilot.native_retry.initial_quiet_reference',return_value={'attempt':'quiet'}) as quiet:
                for retries,initial in ((0,None),(2,None),(2,'../bad')):
                    with self.assertRaises(ValueError): declare_native_preparation(attempt,{},[],host,retries,8,initial)
                initialize.assert_not_called(); quiet.assert_not_called()
                manifest={}; declare_native_preparation(attempt,manifest,[],host,2,8,'quiet')
                self.assertEqual({'attempt':'quiet'},manifest['initialQuietRef'])
                self.assertEqual(attempt.parent/'quiet',quiet.call_args.args[0])
                initialize.assert_called_once()

    def inputs(self):
        return dict(liveBytes=[0, 96, 208, 288], payloads=[256, 4096], warmups=60,
                    measurements=8, residents=32768, heapMiB=512,
                    churnBytesPerSecond=33554432, seed=24301)

    def test_paired_counterbalanced_schedule_preserves_replication_and_inputs(self):
        plan = schedule(self.inputs())
        self.assertEqual(160, len(plan))
        self.assertEqual(160, len({label for label, _ in plan}))
        counts = Counter((p["Block"], p["Channel"], p["Backend"], p["Payload"], p["LiveBytes"])
                         for _, p in plan)
        self.assertTrue(all(n == (3 if key[1] in PRIMARY else 1) for key, n in counts.items()))
        for offset in range(0, len(plan), 2):
            a, b = (plan[offset + n][1] for n in (0, 1))
            self.assertNotEqual(a["Backend"], b["Backend"])
            for key in ("LiveBytes", "Payload", "Channel", "ForkOrdinal", "Block", "Seed", "HeapMiB"):
                self.assertEqual(a[key], b[key])
        for channel in PRIMARY:
            for payload in (256, 4096):
                for live in (0, 288):
                    for fork in (1, 2, 3):
                        orders = [[p["Backend"] for _, p in plan if p["Channel"] == channel
                                   and p["Payload"] == payload and p["LiveBytes"] == live
                                   and p["ForkOrdinal"] == fork and p["Block"] == block] for block in (1, 2)]
                        self.assertEqual(orders[0], list(reversed(orders[1])))
        self.assertEqual(plan, schedule(self.inputs()))
        self.assertNotEqual(plan, schedule(self.inputs(), order_seed=17))

    def test_unqualified_or_changed_source_cannot_start_pilot(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = pathlib.Path(directory)
            (attempt / "manifest.json").write_text(json.dumps(dict(stage="validate", sourceSha256="old")))
            with patch("tailcache12_pilot.measurement_source_hash", return_value="current"), \
                 patch("tailcache12_pilot.archive_measurement_source_hash", return_value="old"), \
                 patch("tailcache12_pilot.evidence.replay") as replay:
                with self.assertRaises(ValueError):
                    qualification_refs(attempt, attempt, attempt, attempt)
                replay.assert_not_called()
        for change in (dict(measurements=3), dict(warmups=3), dict(liveBytes=[0, 96])):
            with self.assertRaises(ValueError):
                schedule(dict(self.inputs(), **change))
