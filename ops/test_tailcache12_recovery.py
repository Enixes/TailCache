import importlib.util
import pathlib
import unittest

path = pathlib.Path(__file__).with_name("tailcache12_recovery.py")
spec = importlib.util.spec_from_file_location("recovery", path)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.thread = dict(status=dict(type="idle"))
        self.turn = dict(id="failed-turn", status="failed", error=dict(codexErrorInfo="usageLimitExceeded"))
        self.limits = dict(ordinaryUsageAllowed=True, rateLimits={})

    def test_only_actual_usage_interruption_can_wake(self):
        self.assertEqual("wake", recovery.decision({}, self.thread, self.turn, self.limits, {}, []))
        for status, code in (("completed", "usageLimitExceeded"), ("failed", "other"),
                             ("interrupted", None), ("failed", "unauthorized"), ("failed", "sessionBudgetExceeded")):
            turn = dict(self.turn, status=status, error=dict(codexErrorInfo=code))
            self.assertEqual("no_usage_interruption", recovery.decision({}, self.thread, turn, self.limits, {}, []))

    def test_no_wakeup_during_work_completion_pause_or_duplicate(self):
        self.assertEqual("benchmark_running", recovery.decision({}, self.thread, self.turn, self.limits, {}, [1]))
        self.assertEqual("thread_active", recovery.decision({}, dict(status=dict(type="active")), self.turn, self.limits, {}, []))
        self.assertEqual("complete", recovery.decision(dict(taskComplete=True), self.thread, self.turn, self.limits, {}, []))
        self.assertEqual("paused", recovery.decision(dict(recoveryPaused=True), self.thread, self.turn, self.limits, {}, []))
        self.assertEqual("already_queued", recovery.decision({}, self.thread, self.turn, self.limits,
                                                            dict(queuedForTurnId="failed-turn"), []))

    def test_reset_times_or_percentages_do_not_grant_permission(self):
        for allowed in (False, None):
            limits = dict(ordinaryUsageAllowed=allowed, rateLimits=dict(primary=dict(usedPercent=0, resetsAt=0)))
            self.assertEqual("waiting_for_usage_permission", recovery.decision({}, self.thread, self.turn, limits, {}, []))
        self.assertEqual("waiting_for_usage_permission", recovery.decision({}, self.thread, self.turn,
            dict(self.limits, rateLimits=dict(spendControlReached=True)), {}, []))
        self.assertLessEqual(len(recovery.PROMPT.encode()), 1000)


if __name__ == "__main__":
    unittest.main()
