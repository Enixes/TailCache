import csv
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import tailcache12_native_host as host
import tailcache12_native_retry as retry


class NativeRetryTest(unittest.TestCase):
    def manifest(self, count=2, retries=2, budget=8):
        slots = [dict(label=f"s{i}", properties=dict(Backend="CAFFEINE", Payload=256, Slot=i)) for i in range(count)]
        return dict(stage="calibrate", nativeHostRetryPolicy=retry.declare_policy(retries, budget),
                    nativeLogicalSlots=slots, expectedBlocks=[s["label"] for s in slots],
                    sourceSha256="source-fixture", nativeRetryPreflights={})

    def row(self, manifest, slot, ordinal=1, reasons=(), quality=(), latency=100):
        entry = manifest["nativeLogicalSlots"][slot]
        return dict(label=retry.label_for(entry["label"], ordinal), inputs=entry["properties"],
            rejectionReasons=list(quality), hostRejectionReasons=list(reasons), hostPass=not reasons,
            nativeObserverVersions=[2], serviceP999Ns=latency,
            hostWindowStartNs=1, hostWindowEndNs=500_000_000)

    def samples(self, count=121):
        group = "/user.slice/tailcache12-retry.scope"
        controls = {group.lstrip("/")+"/cpu.max": "max 100000", group.lstrip("/")+"/memory.max": "max"}
        return [dict(monotonicNs=(i+1)*10**9, memAvailableKiB=6*1024**2, memTotalKiB=8*1024**2,
            memoryFullAvg10=0, memoryFullTotalUs=0, swapInPages=0, swapOutPages=0,
            governor="powersave", externalPower="AC=1", nativeObserverVersion=2,
            nativeScopeQualified=1, nativeCgroup=group, nativeScopeName="tailcache12-retry.scope",
            nativeCpuCounter="proc-stat-minus-cgroup-v2", nativeControls=json.dumps(controls),
            nativeBootId="boot-fixture", nativeKernelRelease="kernel-fixture",
            nativeSampleStartNs=(i+1)*10**9, nativeSampleEndNs=(i+1)*10**9+100000,
            nativeLogicalCpus=12, nativeAffinityCpus=12, nativeClockTicksPerSecond=100,
            nativeCpuTotalTicks=10000+i*1200, nativeCpuBusyTicks=1000+i*300,
            nativeCpuStealTicks=0, nativeScopeUsageUs=1000+i*2800000,
            nativeTemperatures="{}", nativeThrottleCounts="{}") for i in range(count)]

    def write_quiet(self, path, manifest, samples):
        path.mkdir(parents=True)
        with (path/"host.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, list(samples[0]))
            writer.writeheader()
            writer.writerows(samples)
        result = dict(stage="quiet-preflight", sourceSha256=manifest["sourceSha256"],
            hostRuleVersion=manifest["nativeHostRetryPolicy"]["hostRuleVersion"],
            requiredQuietSeconds=120, timeoutSeconds=300, sampleCount=len(samples), quietPass=True,
            elapsedSeconds=len(samples)-1+.1, monitorFailure=None)
        (path/"quiet.json").write_text(json.dumps(result))
        return {name: retry.sha(path/name) for name in ("host.csv", "quiet.json")}

    def test_first_pass_is_selected_in_fixed_order_without_endpoint_selection(self):
        m = self.manifest()
        rows = [self.row(m, 0, reasons=[retry.ELIGIBLE[0]], latency=1),
                self.row(m, 0, 2, latency=1000000), self.row(m, 1, latency=1)]
        state = retry.select(m, rows)
        self.assertEqual(["s0-n2", "s1"], state["selectedLabels"])
        self.assertEqual(["s0"], state["excludedLabels"])
        self.assertTrue(state["complete"])
        self.assertEqual(1, state["extraJvms"])
        changed = [dict(r, serviceP999Ns=10**12) for r in rows]
        self.assertEqual(state, retry.select(m, changed))
        with self.assertRaises(ValueError):
            retry.select(m, rows+[self.row(m, 1, 2)])
        with self.assertRaises(ValueError):
            retry.select(m, [rows[1]])

    def test_power_is_eligible_but_compiler_thermal_missing_observer_and_other_failures_stop(self):
        m = self.manifest()
        self.assertIsNotNone(retry.select(m, [self.row(m, 0, reasons=retry.ELIGIBLE[1:])])["nextCandidate"])
        rows = [self.row(m, 0, quality=["compiler iteration exceeds 10 ms"]),
                self.row(m, 0, reasons=["Native thermal-throttle counter increased"]),
                self.row(m, 0, reasons=[retry.ELIGIBLE[0]], quality=["missing measured occupancy"]),
                dict(self.row(m, 0), nativeObserverVersions=[1])]
        for row in rows:
            state = retry.select(m, [row])
            self.assertIsNone(state["nextCandidate"])
            self.assertTrue(state["terminalRejectionReasons"])
            with self.assertRaises(ValueError):
                retry.select(m, [row, self.row(m, 0, 2)])

    def test_per_slot_total_budgets_and_changed_controls_are_enforced(self):
        m = self.manifest(retries=1, budget=1)
        rows = [self.row(m, 0, reasons=[retry.ELIGIBLE[0]]), self.row(m, 0, 2),
                self.row(m, 1, reasons=[retry.ELIGIBLE[1]])]
        self.assertTrue(retry.select(m, rows)["terminalRejectionReasons"])
        self.assertIsNone(retry.select(m, rows)["nextCandidate"])
        bad = dict(rows[0], inputs=dict(rows[0]["inputs"], Payload=4096))
        with self.assertRaises(ValueError):
            retry.select(m, [bad])
        for retries, budget in ((3,8),(1,9),(True,8)):
            with self.assertRaises(ValueError):
                retry.declare_policy(retries,budget)

    def test_raw_quiet_hashes_timing_and_final_target_environment_are_required(self):
        m = self.manifest()
        samples = self.samples(123)
        samples[0]["externalPower"] = samples[1]["externalPower"] = "AC=0"
        m["nativeEnvironmentDeclaration"] = host.environment_declaration(samples[-1])
        failed = self.row(m,0,reasons=[retry.ELIGIBLE[1]])
        passed = dict(self.row(m,0,2),hostWindowStartNs=125*10**9,hostWindowEndNs=126*10**9)
        state = retry.select(m,[failed,passed])
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            q = root/"native-retry-preflights/s0-n2"
            m["nativeRetryPreflights"]["s0-n2"] = self.write_quiet(q,m,samples)
            checks, errors = retry.verify_preflights(root,m,[failed,passed],state)
            self.assertTrue(checks["s0-n2"]["quietPass"])
            self.assertEqual([],errors)
            expired = dict(passed,hostWindowStartNs=1000*10**9)
            with self.assertRaises(ValueError):
                retry.verify_preflights(root,m,[failed,expired],state)
            (q/"host.csv").write_text((q/"host.csv").read_text()+"\n")
            with self.assertRaises(ValueError):
                retry.verify_preflights(root,m,[failed,passed],state)

    def test_frozen_power_environment_failure_uses_only_existing_host_reasons(self):
        rows=self.samples(2)
        declaration=host.environment_declaration(rows[0])
        rows[-1]["externalPower"]="AC=0"
        self.assertEqual(["external power is disconnected"],host.environment_reasons(rows,declaration))
        rows[-1]["nativeBootId"]="changed"
        self.assertTrue(any("nativeBootId" in r for r in host.environment_reasons(rows,declaration)))

    def test_native_driver_requires_passing_quiet_before_replacement(self):
        for quiet_pass in (True,False):
            with self.subTest(quiet_pass=quiet_pass), tempfile.TemporaryDirectory() as directory:
                root=pathlib.Path(directory)
                m=self.manifest()
                label="s0-n2"
                candidate=dict(label=label,properties=m["nativeLogicalSlots"][0]["properties"],requiresQuietPreflight=True)
                pending=dict(nativeHostRetryState=dict(nextCandidate=candidate))
                complete=dict(nativeHostRetryState=dict(nextCandidate=None))
                events=[]
                def preflight(path,*_):
                    events.append("quiet")
                    path.mkdir(parents=True)
                    for name in ("host.csv","quiet.json"): (path/name).write_text("fixture")
                with patch("tailcache12_quiet.run_preflight",side_effect=preflight), \
                     patch.object(retry,"verify_quiet",return_value=dict(quietPass=quiet_pass,lastMonotonicNs=0)), \
                     patch.object(retry.time,"monotonic_ns",return_value=10**9), \
                     patch("tailcache12.invoke",side_effect=lambda *_:events.append("JVM")):
                    replay=__import__('unittest.mock').mock.Mock(side_effect=[pending,complete])
                    retry.run_grid(root,m,replay,lambda _:"task")
                self.assertEqual(["quiet","JVM"] if quiet_pass else ["quiet"],events)


if __name__ == "__main__":
    unittest.main()
