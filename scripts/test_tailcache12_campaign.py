import unittest

import tailcache12_campaign as campaign
import tailcache12_pilot as pilot
import tailcache12_native_host as host


class CampaignTest(unittest.TestCase):
    def inputs(self):
        return dict(liveBytes=[0,96,208,288], payloads=[256,4096], warmups=96,
                    measurements=8, seed=24301, residents=32768, heapMiB=512, churnBytesPerSecond=32*1024**2)

    def test_primary_schedule_has_192_independent_jvms_and_counterbalanced_controls(self):
        grid = campaign.schedule(self.inputs(),24301)
        self.assertEqual(320,len(grid))
        primary = [(k,v) for k,v in grid if v["Channel"] in pilot.PRIMARY]
        self.assertEqual(192,len(primary))
        self.assertEqual(len(grid),len({k for k,v in grid}))
        for channel in pilot.PRIMARY:
            for payload in (256,4096):
                for live in (0,96,208,288):
                    rows = [p for _,p in primary if (p["Channel"],p["Payload"],p["LiveBytes"]) == (channel,payload,live)]
                    self.assertEqual(12,len(rows))
                    self.assertEqual({(b,f,backend) for b in (1,2) for f in (1,2,3) for backend in pilot.evidence.BACKENDS},
                                     {(r["Block"],r["ForkOrdinal"],r["Backend"]) for r in rows})
        self.assertEqual(grid,campaign.schedule(self.inputs(),24301))
        conditioned=campaign.schedule(dict(self.inputs(),conditioning=8),24301)
        self.assertTrue(all(p["Conditioning"]==8 for _,p in conditioned))

    def comparisons(self, ratios):
        return [dict(seed=24301,channel=c,payloadBytes=p,applicationLiveBytes=live,complete=True,
                     varianceRejectionReasons=[],ratios={e:dict(ratio=ratio, direction="caffeine-lower" if ratio>1 else "chronicle-lower")
                                                          for e in ("99","99.9")})
                for c in pilot.PRIMARY for p in (256,4096) for live,ratio in zip((0,96,208,288),ratios)]

    def test_seed_robustness_covers_crossing_neighbors_and_range_when_no_crossing(self):
        primary = dict(dataCompleteAndQualityPass=True,comparisons=self.comparisons([2,1.5,.8,.7]))
        selection = campaign.robustness_selection(primary,self.inputs())
        self.assertEqual({str(s) for s in campaign.RULES["robustnessSeeds"]},set(selection))
        self.assertTrue(all(levels == [0,96,208,288] for p in selection.values() for levels in p.values()))
        primary["comparisons"] = self.comparisons([2,2,2,2])
        selection = campaign.robustness_selection(primary,self.inputs())
        self.assertTrue(all(levels == [0,288] for p in selection.values() for levels in p.values()))
        primary["dataCompleteAndQualityPass"] = False
        with self.assertRaises(ValueError): campaign.robustness_selection(primary,self.inputs())

    def test_missing_or_unstable_coverage_cannot_support_no_crossover(self):
        rows = self.comparisons([2,2,.8,.7])
        regions = campaign.crossing_regions(rows,[0,96,208,288])
        self.assertTrue(all(r["supportedRegions"] == [[96,208]] for r in regions))
        rows[0]["varianceRejectionReasons"] = ["unstable"]
        regions = campaign.crossing_regions(rows,[0,96,208,288])
        affected = next(r for r in regions if r["channel"] == rows[0]["channel"] and r["payloadBytes"] == rows[0]["payloadBytes"])
        self.assertFalse(affected["fullTestedRangeCovered"])
        self.assertIn("unresolved",affected["interpretation"])
        regions = campaign.crossing_regions(rows[1:],[0,96,208,288])
        affected = next(r for r in regions if r["channel"] == rows[0]["channel"] and r["payloadBytes"] == rows[0]["payloadBytes"])
        self.assertFalse(affected["fullTestedRangeCovered"])

    def test_cross_stage_environment_normalizes_scope_but_retains_hardware_and_boot(self):
        def declaration(scope):
            group = "/user.slice/user-1000.slice/user@1000.service/app.slice/"+scope
            return dict(nativeCgroup=group,nativeScopeName=scope,nativeControls=__import__('json').dumps({
                group.lstrip('/')+"/cpu.max":"not-enabled", "cpu.max":"not-enabled"}),
                nativeBootId="boot",nativeKernelRelease="kernel",memTotalKiB=8000000)
        a,b=declaration("tailcache12-a.scope"),declaration("tailcache12-b.scope")
        self.assertEqual(host.normalized_environment(a),host.normalized_environment(b))
        pilot.verify_native_environments([dict(nativeEnvironmentVersion=1,nativeEnvironmentDeclaration=d) for d in (a,b)])
        b["nativeBootId"] = "different"
        with self.assertRaises(ValueError):
            pilot.verify_native_environments([dict(nativeEnvironmentVersion=1,nativeEnvironmentDeclaration=d) for d in (a,b)])


if __name__ == "__main__":
    unittest.main()
