import collections
import unittest
import pathlib
import tempfile
from unittest import mock
import tailcache12_service_policy as policy
import tailcache12_service_trace as trace
import tailcache12_service_campaign as core


def result(spec,ratio=1):
    row=dict(spec,status='OK',latencyVerified=True,warnings=[],trace={'traceSha256':'fixed'})
    row['latency']={c:dict(count=100,percentilesNs={p:100*(ratio if spec['backend']=='CHRONICLE_IN_MEMORY' else 1)
                                                for p in core.PERCENTILES}) for c in core.CHANNELS[:-1]}
    return row


class PolicyTraceTest(unittest.TestCase):
    def test_declared_phase_timing_is_enforced_and_failed_slots_are_retained(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary)
            for name in ('docs/preprint/paper-data.json','docs/TAILCACHE_12_FINAL_ACCEPTANCE.json',
                         'evidence-archives/focused-rq-p99999-20261108-001/study.json',
                         'evidence-archives/midpoint-results-20261110-001/study.json','qualification.json'):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
            classes=root/'classes';classes.mkdir();(classes/'dummy.class').write_bytes(b'fixture')
            cp=root/'cp.txt';cp.write_text(str(classes))
            ready=dict(nativeScopeQualified=1,memAvailableKiB=2*1024**2,externalPower='AC=1',
                       swapInPages=0,swapOutPages=0)
            design=dict(maxWorkloadJvms=8,warmupMs=60000,conditioningMs=4000,measureMs=30000,
                        processTimeoutSeconds=180,functionalValidationJvms=1,
                        functionalValidationReceipt='qualification.json')
            def failed_launch(directory,spec,*args,**kwargs):
                path=directory/spec['label'];path.mkdir()
                raw=path/'raw.txt';raw.write_text('retained failure fixture')
                return dict(spec,status='ERROR',warnings=['deliberate fixture failure'],
                            latencyVerified=False,rawSha256={'raw.txt':core.focus.sha(raw)})
            with mock.patch.object(core,'ROOT',root),mock.patch.object(core,'source_identity',return_value=('source',{})), \
                 mock.patch.object(core,'source_files',return_value=[]), \
                 mock.patch.object(core.focus,'environment_metadata',return_value={}), \
                 mock.patch.object(core.focus.evidence,'host_snapshot',return_value=ready), \
                 mock.patch.object(core.time,'sleep'),mock.patch.object(core.focus,'launch',side_effect=failed_launch) as launch:
                campaign=core.Campaign(root/'cohort',design=design,classpath_file=cp)
                spec=trace.schedule()[0]
                spec['extraArgs']=['--trace-pattern','repeated-short']
                campaign.execute([spec]);campaign.execute([spec])
                self.assertEqual(launch.call_count,1)
                kwargs=launch.call_args.kwargs
                self.assertEqual((kwargs['warmup'],kwargs['conditioning'],kwargs['measure'],kwargs['timeout_seconds']),
                                 (60000,4000,30000,180))
                self.assertIn(str(spec['traceOperations']),kwargs['extra_args'])
                self.assertEqual(kwargs['extra_args'][-2:],('--trace-pattern','repeated-short'))

    def test_policy_four_arm_budget_and_identity(self):
        slots=policy.schedule()
        self.assertEqual(slots,policy.schedule())
        self.assertEqual(len(slots),16)
        self.assertEqual(len({s['label'] for s in slots}),16)
        grouped=collections.defaultdict(list)
        for s in slots:
            self.assertEqual((s['regime'],s['qps'],s['seed'],s['liveMiB']),('closed',0,24301,0))
            grouped[s['payload'],s['block']].append(s)
        self.assertEqual(len(grouped),4)
        for arms in grouped.values():self.assertEqual({s['backend'] for s in arms},set(policy.ARMS))

    def test_shared_anchor_failure_invalidates_each_contrast(self):
        specs=policy.schedule();first=[s for s in specs if s['payload']==512 and s['block']==1]
        rows=[result(s,.5) for s in first]
        self.assertEqual(len(policy.comparisons(rows)),3)
        for row in rows:
            if row['backend']=='CHRONICLE_IN_MEMORY':row['status']='OOM_SETUP'
        self.assertFalse(any(p['valid'] for p in policy.comparisons(rows)))

    def test_failed_policy_is_not_replaced_by_another_reference(self):
        rows=[result(s,.5) for s in policy.schedule() if s['payload']==512 and s['block']==1]
        for r in rows:
            if r['backend']=='CAFFEINE_UNBOUNDED':r['status']='ERROR'
        pairs=policy.comparisons(rows)
        self.assertEqual(sum(p['valid'] for p in pairs),2)
        bad=next(p for p in pairs if p['referenceBackend']=='CAFFEINE_UNBOUNDED')
        self.assertFalse(bad['valid']);self.assertEqual(bad['ratios'],{})

    def test_trace_design_keeps_baseline_and_trace_factors_separate(self):
        slots=trace.schedule()
        self.assertEqual(len(slots),8)
        self.assertEqual(len({s['label'] for s in slots}),8)
        self.assertEqual(slots,trace.schedule())
        grouped=collections.defaultdict(list)
        for s in slots:
            self.assertEqual((s['payload'],s['liveMiB'],s['regime'],s['qps']),(4096,0,'arrival',50000))
            grouped[s['traceOperations'],s['block']].append(s)
        self.assertEqual(len(grouped),4)
        for pair in grouped.values():self.assertEqual({s['backend'] for s in pair},set(core.BACKENDS))


if __name__=='__main__':unittest.main()
