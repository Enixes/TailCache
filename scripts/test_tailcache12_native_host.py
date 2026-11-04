import json
import pathlib
import tempfile
import unittest

import tailcache12_native_host as native
from tailcache12 import HOST_RULE_VERSION, replay_host_gate


class NativeHostTest(unittest.TestCase):
    def rows(self, count=32):
        group = "/user.slice/tailcache12-fixture.scope"
        controls = {group.lstrip("/") + "/cpu.max": "max 100000",
                    group.lstrip("/") + "/memory.max": "max"}
        return [dict(monotonicNs=(i + 1) * 10**9, memAvailableKiB=6 * 1024**2,
                     memoryFullAvg10=0, memoryFullTotalUs=0, swapInPages=0, swapOutPages=0,
                     governor="powersave", externalPower="AC=1", nativeObserverVersion=2,
                     nativeScopeQualified=1, nativeCgroup=group, nativeScopeName="tailcache12-fixture.scope",
                     nativeCpuCounter="proc-stat-minus-cgroup-v2", nativeControls=json.dumps(controls),
                     nativeSampleStartNs=(i + 1) * 10**9, nativeSampleEndNs=(i + 1) * 10**9 + 100_000,
                     nativeLogicalCpus=12, nativeAffinityCpus=12, nativeClockTicksPerSecond=100,
                     nativeCpuTotalTicks=10000 + i * 1200, nativeCpuBusyTicks=1000 + i * 300,
                     nativeCpuStealTicks=0, nativeScopeUsageUs=1000 + i * 2_800_000,
                     nativeTemperatures=json.dumps({"core": {"milliC": 45000, "criticalMilliC": 100000}}),
                     nativeThrottleCounts=json.dumps({"core": 0})) for i in range(count)]

    def test_own_scope_cpu_is_not_competing_work_but_outside_burst_rejects(self):
        rows = self.rows()
        self.assertEqual([], native.gate(rows))
        interval = native.cpu_intervals(rows)[0]
        self.assertGreater(interval["outsideUpperPercent"], interval["outsidePercent"])
        self.assertLess(interval["outsideUpperPercent"], 10)
        # Extra two seconds of outside CPU distributed across 12 cores exceeds the ceiling.
        for row in rows[23:]:
            row["nativeCpuBusyTicks"] += 200
        self.assertTrue(any("10%" in r for r in native.gate(rows, [(20 * 10**9, 28 * 10**9)])))

    def test_startup_cpu_exclusion_does_not_exclude_power_or_observer_faults(self):
        rows = self.rows()
        for row in rows[2:]:
            row["nativeCpuBusyTicks"] += 200
        windows = [(20 * 10**9, 28 * 10**9)]
        self.assertEqual([], native.gate(rows, windows))
        self.assertTrue(native.gate(rows))
        rows[1]["nativeScopeUsageUs"] = float("nan")
        self.assertTrue(native.gate(rows, windows))

    def test_missing_reset_stale_restricted_or_escaping_counters_fail_closed(self):
        mutations = [lambda r: r[4].pop("nativeScopeUsageUs"),
                     lambda r: r[4].update(nativeScopeUsageUs=0),
                     lambda r: r[4].update(nativeSampleStartNs=0),
                     lambda r: r[4].update(nativeSampleEndNs=r[4]["nativeSampleStartNs"] + 200_000_000),
                     lambda r: r[4].update(nativeAffinityCpus=1),
                     lambda r: r[4].update(nativeScopeQualified=0),
                     lambda r: r[4].update(nativeCpuTotalTicks=1),
                     lambda r: r[4].update(nativeCgroup="/unrelated.scope"),
                     lambda r: r[4].update(nativeCpuStealTicks=1),
                     lambda r: r[4].update(memAvailableKiB=512 * 1024),
                     lambda r: r[4].update(nativeControls="{}"),
                     lambda r: r[4].update(nativeCpuBusyTicks=1_000_000)]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                rows = self.rows()
                mutate(rows)
                self.assertTrue(native.gate(rows))
        rows = self.rows()
        for row in rows:
            controls = json.loads(row["nativeControls"])
            controls["user.slice/cpu.max"] = "100000 100000"
            row["nativeControls"] = json.dumps(controls)
        self.assertTrue(any("resource limit" in r for r in native.gate(rows)))

    def test_disabled_leaf_controller_does_not_hide_inherited_quota(self):
        rows = self.rows()
        for row in rows:
            controls = json.loads(row["nativeControls"])
            controls[row["nativeCgroup"].lstrip("/") + "/cpu.max"] = "not-enabled"
            controls["user.slice/cpu.max"] = "max 100000"
            row["nativeControls"] = json.dumps(controls)
        self.assertEqual([], native.gate(rows))
        for row in rows:
            controls = json.loads(row["nativeControls"])
            controls["user.slice/cpu.max"] = "100000 100000"
            row["nativeControls"] = json.dumps(controls)
        self.assertTrue(any("resource limit" in r for r in native.gate(rows)))

    def test_thermal_events_reject_and_missing_optional_sensors_are_explicit(self):
        rows = self.rows()
        for row in rows:
            row["nativeTemperatures"] = "{}"
            row["nativeThrottleCounts"] = "{}"
        self.assertEqual([], native.gate(rows))
        rows[5]["nativeTemperatures"] = json.dumps({"core": {"milliC": 100000, "criticalMilliC": 100000}})
        self.assertTrue(any("critical" in r for r in native.gate(rows)))
        rows = self.rows()
        rows[5]["nativeThrottleCounts"] = json.dumps({"core": 1})
        self.assertTrue(any("throttle" in r for r in native.gate(rows)))

    def test_new_host_rule_requires_real_worker_containment_and_old_rule_replays(self):
        rows = self.rows()
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            self.assertTrue(replay_host_gate({"hostRuleVersion": HOST_RULE_VERSION}, root, rows)[0])
            worker = root / "worker-process-123.properties"
            worker.write_text("pid=123\ncgroup=/wrong.scope\n")
            self.assertTrue(native.worker_reasons(root, rows))
            worker.write_text("pid=123\ncgroup=" + rows[0]["nativeCgroup"]
                              + "\nbackend=CAFFEINE\npayloadBytes=256\nmode=workload\nworkerAllocationCounters=true\n")
            (root / "iterations-123.csv").write_text("phase,operations,writes,workerJvmAllocatedBytes\nMEASUREMENT,100,5,1280\n")
            self.assertEqual([], replay_host_gate({"hostRuleVersion": HOST_RULE_VERSION}, root, rows)[0])
            old = [{k: v for k, v in row.items() if not k.startswith("native")} for row in rows]
            self.assertEqual([], replay_host_gate({"hostRuleVersion": "tailcache12-host-v2-settling"}, root, old)[0])
            self.assertTrue(replay_host_gate({"hostRuleVersion": HOST_RULE_VERSION}, root, old)[0])

    def test_final_fragment_is_merged_without_hiding_raw_resets_or_rewriting_legacy(self):
        rows = self.rows(4)
        tail = dict(rows[-1], monotonicNs=4_100_000_000, nativeSampleStartNs=4_100_000_000,
                    nativeSampleEndNs=4_100_100_000, nativeCpuTotalTicks=rows[-1]["nativeCpuTotalTicks"]+120,
                    nativeCpuBusyTicks=rows[-1]["nativeCpuBusyTicks"]+30,
                    nativeScopeUsageUs=rows[-1]["nativeScopeUsageUs"]+280000)
        rows.append(tail)
        self.assertEqual([], native.gate(rows))
        self.assertEqual(3, len(native.cpu_intervals(rows)))
        self.assertEqual(tail["nativeSampleEndNs"], native.cpu_intervals(rows)[-1]["endNs"])
        legacy = [dict(r, nativeObserverVersion=1) for r in rows]
        self.assertTrue(any("10%" in r for r in native.gate(legacy)))
        rows[-2]["nativeScopeUsageUs"] = 0
        self.assertTrue(native.gate(rows))

    def test_worker_allocation_bound_detects_missing_materialization_and_wrong_mode(self):
        rows = self.rows()
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            marker = root / "worker-process-123.properties"
            marker.write_text("pid=123\ncgroup=" + rows[0]["nativeCgroup"]
                              + "\nbackend=CHRONICLE_IN_MEMORY\npayloadBytes=4096\nmode=workload\nworkerAllocationCounters=true\n")
            csv_path = root / "iterations-123.csv"
            csv_path.write_text("phase,operations,writes,workerJvmAllocatedBytes\nMEASUREMENT,100,5,409600\n")
            self.assertEqual([], native.worker_reasons(root, rows, True))
            csv_path.write_text("phase,operations,writes,workerJvmAllocatedBytes\nMEASUREMENT,100,5,20480\n")
            self.assertTrue(any("allocation" in r for r in native.worker_reasons(root, rows, True)))
            marker.write_text(marker.read_text().replace("mode=workload", "mode=supply-floor"))
            self.assertEqual([], native.worker_reasons(root, rows, True))
            csv_path.write_text("phase,operations,writes\nMEASUREMENT,100,5\n")
            self.assertTrue(native.worker_reasons(root, rows, True))

    def test_cgroup_membership_parser_rejects_ambiguous_or_relative_paths(self):
        self.assertEqual("/user.slice/demo.scope", native.process_cgroup("0::/user.slice/demo.scope\n"))
        for text in ("0::relative", "0::/a\n0::/b", "0::/a/../b", ""):
            with self.assertRaises(ValueError):
                native.process_cgroup(text)


if __name__ == "__main__":
    unittest.main()
