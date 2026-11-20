"""Behavioral checks for the portable collector, without performance JVMs."""
import contextlib
import copy
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import tailcache_portable as p

ROOT = pathlib.Path(__file__).resolve().parents[1]


class PortableTests(unittest.TestCase):
    def setUp(self):
        self.config=p.load(ROOT/'experiments/portable/locality.json')
        self.temp=tempfile.TemporaryDirectory()
        self.root=pathlib.Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def invalid(self, change):
        value=copy.deepcopy(self.config);change(value)
        with self.assertRaises(ValueError):p.validate(value)

    def test_profiles_and_counts(self):
        for name,count in [('locality',8),('write-ratio',20),('rq-matrix',64),('smoke',4)]:
            config=p.validate(p.load(ROOT/f'experiments/portable/{name}.json'))
            self.assertEqual(len(p.schedule(config)),count)
            self.assertEqual(p.plan(config)['workloadJvms'],count if name!='smoke' else 0)

    def test_reproduction_suite_uses_one_baseline_for_three_views(self):
        design = p.suite_plan(ROOT/'experiments/portable', 'all')
        self.assertEqual(design['researchJvms'], 84)
        self.assertEqual(design['diagnosticJvms'], 4)
        research = design['phases']['research']
        self.assertEqual(len(research['config']['cells']), 21)
        self.assertEqual(research['config']['primeCalls'], 0)
        views = design['researchViews']
        baseline, = set.intersection(*(set(cells) for cells in views.values()))
        self.assertEqual(research['config']['cells'][baseline-1], {
            'payloadBytes': 4096, 'liveMiB': 0, 'writeBps': 500, 'updateHotset': 32768, 'qps': 50000,
        })
        for profile, cell_ids in views.items():
            original = p.load(ROOT/'experiments/portable'/f'{profile}.json')
            self.assertEqual(original['cells'], [research['config']['cells'][i-1] for i in cell_ids])
        self.assertEqual(len({(r['cell'], r['seed'], r['backend']) for r in research['schedule']}), 84)

    def test_individual_gradle_suites_preserve_their_named_profile(self):
        configs = ROOT/'experiments/portable'
        for name, forks in [('write-ratio', 20), ('locality-long', 16), ('rq-matrix', 64),
                            ('saturated-write-pressure', 96), ('write-transition', 48)]:
            with self.subTest(suite=name):
                profile = p.load(configs/f'{name}.json')
                design = p.suite_plan(configs, name)
                self.assertEqual(design['researchJvms'], forks)
                self.assertEqual(design['phases']['research']['schedule'], p.schedule(profile))
                self.assertEqual(list(design['researchViews']), [name])
        short = p.load(configs/'locality.json')
        long = p.load(configs/'locality-long.json')
        self.assertEqual(long['cells'], short['cells'])
        self.assertTrue(set(short['seeds']).isdisjoint(long['seeds']))
        self.assertEqual(len(long['seeds']), 4)
        self.assertEqual(long['measureMs'], 90_000)

    def test_reproduction_suite_rejects_different_seed_sets(self):
        configs = ROOT/'experiments/portable'
        for name in ('smoke', 'locality', 'write-ratio', 'rq-matrix'):
            cfg = p.load(configs/f'{name}.json')
            if name=='write-ratio':
                cfg['seeds'] = [924, 925]
            p.save_new(self.root/f'{name}.json', cfg)
        with self.assertRaisesRegex(ValueError, 'must share JVM, timing, seed'):
            p.suite_plan(self.root, 'all')

    def test_rejects_typo(self): self.invalid(lambda c:c.update(warmup=12))
    def test_rejects_nonobject_root(self):
        with self.assertRaisesRegex(ValueError,'JSON object'):p.validate(None)
    def test_rejects_nonobject_cell(self): self.invalid(lambda c:c.update(cells=[None]))
    def test_rejects_bool_integer(self): self.invalid(lambda c:c.update(heapMiB=True))
    def test_rejects_odd_seeds(self): self.invalid(lambda c:c.update(seeds=[1,2,3]))
    def test_rejects_duplicate_seed(self): self.invalid(lambda c:c.update(seeds=[1,1]))
    def test_rejects_duplicate_cell(self): self.invalid(lambda c:c['cells'].append(dict(c['cells'][0])))
    def test_rejects_impossible_hotset(self): self.invalid(lambda c:c['cells'][0].update(updateHotset=32769))
    def test_rejects_fractional_arrival(self): self.invalid(lambda c:c['cells'][0].update(qps=123))
    def test_rejects_phase_fractional_arrivals(self):
        self.invalid(lambda c:(c.update(measureMs=1),c['cells'][0].update(qps=1)))
    def test_rejects_nonfinite_quality(self): self.invalid(lambda c:c['quality'].update(maxOutsideCpuFraction=float('nan')))
    def test_rejects_excess_retry_budget(self): self.invalid(lambda c:c.update(maxExternalRetryPairs=9))
    def test_rejects_excess_priming(self):
        self.invalid(lambda c:c.update(warmupMs=100, primeCalls=1))

    def test_duplicate_json_keys(self):
        file=self.root/'bad.json';file.write_text('{"seed":1,"seed":2}')
        with self.assertRaisesRegex(ValueError,'Duplicate'):p.load(file)

    def test_schedule_is_paired_and_balanced(self):
        rows=p.schedule(self.config)
        self.assertEqual(rows,p.schedule(self.config))
        self.assertEqual(len({r['label'] for r in rows}),len(rows))
        for a,b in zip(rows[::2],rows[1::2]):
            self.assertEqual({a['backend'],b['backend']},set(p.BACKENDS))
            self.assertEqual({k:v for k,v in a.items() if k not in ('label','backend')},
                             {k:v for k,v in b.items() if k not in ('label','backend')})
        for cell in (1,2):
            first=[a['backend'] for a in rows[::2] if a['cell']==cell]
            self.assertEqual(first.count(p.BACKENDS[0]),first.count(p.BACKENDS[1]))

    def test_exclusive_json_preserves_original(self):
        file=self.root/'proof.json';p.save_new(file,{'a':1})
        with self.assertRaises(FileExistsError):p.save_new(file,{'a':2})
        self.assertEqual(p.load(file),{'a':1})

    def test_safe_inventory(self):
        with self.assertRaisesRegex(ValueError,'Unsafe'):p.verify_inventory(self.root,{'../secret':'x'})

    def test_hdr_rank_at_binary_float_boundary(self):
        self.assertEqual(p.quantile([(1,999),(2,1)],99.9),1)
        self.assertEqual(p.quantile([],99.999),None)

    def test_histogram_conservation(self):
        file=self.root/'bins.csv';file.write_text('upperEquivalentNs,count\n1,10\n2,1\n')
        self.assertEqual(p.histogram(file,11),[(1,10),(2,1)])
        with self.assertRaises(ValueError):p.histogram(file,12)
        file.write_text('upperEquivalentNs,count\n2,1\n1,10\n')
        with self.assertRaises(ValueError):p.histogram(file,11)

    def test_tail_support_and_threshold_bounds(self):
        stats=p.hist_stats([(99999,10),(100031,5),(100095,2)],self.config)
        self.assertEqual(stats['exceedance']['100000']['lowerCount'],2)
        self.assertEqual(stats['exceedance']['100000']['upperCount'],7)
        self.assertTrue(stats['percentiles']['99.999']['tailSupportWarning'])
        stats=p.hist_stats([(1,1500000)],self.config)
        self.assertTrue(stats['percentiles']['99.999']['tailSupportWarning'])
        self.assertFalse(stats['percentiles']['99.99']['tailSupportWarning'])

    def samples(self):
        return [dict(startNs=i*10**9,endNs=i*10**9+1000,pswpin=0,pswpout=0,zswpin=0,zswpout=0,
                     cpuTotal=i*100,cpuBusy=i*50,processTicks=i*49,MemAvailableKiB=2*1024**2,
                     externalPower={},throttle={'core':'0'}) for i in range(6)]

    def test_startup_zswap_is_separate_from_protected_window(self):
        samples=self.samples()
        for s in samples[1:]:s['zswpin']=1
        q=p.quality_screen(samples,2*10**9+2000,4*10**9,self.config,'linux-proc')
        self.assertFalse(any('zswpin' in w for w in q['warnings']))
        self.assertTrue(any('zswpin' in w for w in q['lifetimeDiagnostics']))

    def test_measurement_zswap_warns(self):
        samples=self.samples()
        for s in samples[3:]:s['zswpin']=1
        q=p.quality_screen(samples,2*10**9+2000,4*10**9,self.config,'linux-proc')
        self.assertTrue(any('zswpin' in w for w in q['warnings']))

    def test_missing_counters_do_not_pass_clean(self):
        samples=self.samples()
        for s in samples:s['zswpin']=None
        q=p.quality_screen(samples,2*10**9+2000,4*10**9,self.config,'diagnostic')
        self.assertTrue(any('Missing host counter' in w for w in q['warnings']))
        self.assertTrue(any('diagnostic' in w for w in q['warnings']))

    def test_outside_cpu_screen(self):
        samples=self.samples()
        for s in samples:s['processTicks']=0
        q=p.quality_screen(samples,2*10**9+2000,4*10**9,self.config,'linux-proc')
        self.assertTrue(any('CPU' in w for w in q['warnings']))

    def test_outside_cpu_marks_unattributed_final_bracket_separately(self):
        samples = self.samples()
        del samples[-1]['processTicks']
        q = p.quality_screen(samples, 2*10**9+2000, 4*10**9+2000, self.config, 'linux-proc')
        self.assertEqual(q['outsideCpuUnattributedIntervals'], 1)
        self.assertGreaterEqual(q['outsideCpuUnattributedMaxUpperFraction'], 0.5)
        self.assertLess(q['outsideCpuMaxUpperFraction'], 0.1)
        self.assertIn('Outside-process CPU attribution incomplete', q['warnings'])
        self.assertNotIn('Outside-process CPU upper bound exceeded frozen ceiling', q['warnings'])
        del samples[-1]['cpuBusy']
        q = p.quality_screen(samples, 2*10**9+2000, 4*10**9+2000, self.config, 'linux-proc')
        self.assertEqual(q['outsideCpuMissingIntervals'], 1)
        self.assertIn('Missing outside-process CPU evidence', q['warnings'])

    def test_observer_receipt_requires_sample_after_measurement_with_worker_counters(self):
        worker = self.root/'worker'
        worker.mkdir()
        sample = self.samples()[-1]
        p.save_new(worker/'observer-ack.json', sample)
        self.assertTrue(p.observer_handoff_complete(self.root, [sample], sample['startNs']-1))
        self.assertFalse(p.observer_handoff_complete(self.root, [], sample['startNs']-1))
        self.assertFalse(p.observer_handoff_complete(self.root, [sample], sample['startNs']+1))

    def test_power_and_thermal_screen(self):
        samples=self.samples();samples[3]['externalPower']={'AC':'0'};samples[3]['throttle']['core']='1'
        q=p.quality_screen(samples,2*10**9+2000,4*10**9,self.config,'linux-proc')
        self.assertTrue(any('power disconnected' in w for w in q['warnings']))
        self.assertTrue(any('throttle' in w for w in q['warnings']))

    def test_inactive_alternate_power_input_does_not_mean_disconnected(self):
        self.assertFalse(p.power_disconnected({'AC': '1', 'USB-C': '0'}))
        self.assertTrue(p.power_disconnected({'AC': '0', 'USB-C': '0'}))
        self.assertFalse(p.power_disconnected({'AC': None}))

    def test_capped_stall_detail_has_a_verifiable_count(self):
        path = self.root/'stalls.csv'
        path.write_text('operationIndex\n3\n5\n')
        measurement = dict(stallEvents='5',unexportedStallEvents='3',operations='10')
        self.assertEqual(p.stall_export(self.root, measurement, 2),dict(total=5,exported=2,omitted=3))
        path.write_text('operationIndex\n3\n')
        with self.assertRaisesRegex(ValueError, 'row count'):
            p.stall_export(self.root, measurement, 2)

    def fake_result(self,path,spec,warning=False,failure=False):
        # These report fixtures model already-verified forks; real-bin reconstruction
        # is exercised separately and by the extracted-bundle integration smoke.
        if not hasattr(self,'derivative_mock'):
            patch=mock.patch.object(p,'verify_derivatives');self.derivative_mock=patch.start();self.addCleanup(patch.stop)
        path.mkdir(parents=True)
        (path/'raw.txt').write_text('retained evidence')
        result=dict(spec=spec,status='FAILED' if failure else 'COMPLETE',warnings=['host event'] if warning else [],
                    windows=[dict(phase='MEASUREMENT',operations='1000',writes='50')],
                    integrity=dict(mutationVersionSha256='same'),latency={ch:p.hist_stats([(100 if spec['backend']==p.BACKENDS[0] else 200,1000)],self.config) for ch in p.CHANNELS},
                    rawSha256=p.inventory(path))
        p.save_new(path/'result.json',result);p.save_new(path/'seal.json',dict(resultSha256=p.sha(path/'result.json')))
        return result

    def test_raw_and_result_tampering_fail(self):
        spec=p.schedule(self.config)[0];path=self.root/'slot';self.fake_result(path,spec)
        self.assertEqual(p.retained(path,spec)['status'],'COMPLETE')
        (path/'raw.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError,'Evidence changed'):p.retained(path,spec)
        (path/'raw.txt').write_text('retained evidence')
        (path/'result.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'result changed'):p.retained(path,spec)

    def test_unexpected_raw_file_fails(self):
        spec=p.schedule(self.config)[0];path=self.root/'slot';self.fake_result(path,spec)
        (path/'extra.txt').write_text('x')
        with self.assertRaisesRegex(ValueError,'Unexpected'):p.retained(path,spec)

    def frozen_run(self):
        p.save_new(self.root/'run.json',dict(config=self.config,schedule=p.schedule(self.config),bundleId='bundle',host={'id':'host'}))

    def test_report_preserves_pair_warnings_and_missing(self):
        self.frozen_run();rows=p.schedule(self.config)
        for spec in rows[:2]:self.fake_result(self.root/'slots'/spec['label'],spec,warning=spec==rows[0])
        result=p.report(self.root,self.root/'report')
        self.assertFalse(result['collectionComplete'])
        self.assertEqual(len(result['missing']),6)
        s=next(s for s in result['summaries'] if s['cell']==rows[0]['cell'] and s['channel']=='response')
        self.assertEqual(s['allUsablePairs']['medianRatio'],2)
        self.assertEqual(s['warningFreePairs']['n'],0)

    def test_retries_are_capped_and_exclude_endogenous_warnings(self):
        rows = p.schedule(self.config)
        observations = {spec['label']:dict(status='COMPLETE', warnings=[]) for spec in rows}
        cpu = 'Outside-process CPU upper bound exceeded frozen ceiling'
        observations[rows[0]['label']]['warnings'] = [cpu, 'Churn demand dropped']
        observations[rows[2]['label']]['warnings'] = [cpu]
        observations[rows[4]['label']]['warnings'] = ['Outside-process CPU attribution incomplete']
        observations[rows[6]['label']]['warnings'] = [cpu]
        observations[rows[7]['label']]['status'] = 'FAILED'
        plan = p.retry_plan(rows,observations,1)
        self.assertEqual(plan['eligiblePairs'], 2)
        self.assertEqual([x['slots'] for x in plan['selected']], [rows[2:4]])

    def test_clean_retry_is_a_separate_sensitivity_observation(self):
        self.config['maxExternalRetryPairs'] = 1
        self.frozen_run()
        rows = p.schedule(self.config)
        for spec in rows[:2]:
            self.fake_result(self.root/'slots'/spec['label'],spec)
            self.fake_result(self.root/'external-retry'/spec['label'],spec)
        original = {s['label']:p.load(self.root/'slots'/s['label']/'result.json') for s in rows[:2]}
        original[rows[0]['label']]['warnings'] = ['Outside-process CPU attribution incomplete']
        slot = self.root/'slots'/rows[0]['label']
        (slot/'result.json').write_text(json.dumps(original[rows[0]['label']]))
        (slot/'seal.json').write_text(json.dumps(dict(resultSha256=p.sha(slot/'result.json'))))
        p.save_new(self.root/'external-retry-plan.json', p.retry_plan(rows,original,1))
        report = p.report(self.root,self.root/'report')
        self.assertFalse(report['pairs'][0]['warningFree'])
        self.assertEqual(len(report['observations']), 2)
        self.assertEqual(report['retryReview']['recoveredCleanPairs'], 1)
        self.assertEqual(report['retryReview']['cleanSensitivityPairs'][0]['source'], 'external-retry')

    def test_failed_slot_is_not_replaced_or_included(self):
        self.frozen_run()
        for spec in p.schedule(self.config):self.fake_result(self.root/'slots'/spec['label'],spec,failure=True)
        result=p.report(self.root,self.root/'report')
        self.assertTrue(result['collectionComplete']);self.assertFalse(result['allSlotsSuccessful'])
        self.assertEqual(result['failed'],8);self.assertTrue(all(not p['usable'] for p in result['pairs']))

    def test_zero_timer_quantile_does_not_divide_or_create_a_winner(self):
        self.frozen_run()
        for spec in p.schedule(self.config):
            path=self.root/'slots'/spec['label'];self.fake_result(path,spec)
            r=p.load(path/'result.json');r['latency']={ch:p.hist_stats([(0,1000)],self.config) for ch in p.CHANNELS}
            (path/'result.json').write_text(json.dumps(r));(path/'seal.json').write_text(json.dumps(dict(resultSha256=p.sha(path/'result.json'))))
        result=p.report(self.root,self.root/'report')
        self.assertTrue(all(s['allUsablePairs']['n']==0 for s in result['summaries']))
        self.assertTrue(all(point['completePairDirectionsFavor']=='UNRESOLVED' for point in result['pointConclusions']))

    def test_paired_stream_mismatch_excluded(self):
        self.frozen_run();rows=p.schedule(self.config)
        for spec in rows[:2]:self.fake_result(self.root/'slots'/spec['label'],spec)
        path=self.root/'slots'/rows[0]['label'];r=p.load(path/'result.json');r['integrity']['mutationVersionSha256']='wrong'
        (path/'result.json').write_text(json.dumps(r));(path/'seal.json').write_text(json.dumps(dict(resultSha256=p.sha(path/'result.json'))))
        result=p.report(self.root,self.root/'report')
        self.assertFalse(result['pairs'][0]['usable'])
        self.assertIn('stream differs',result['pairs'][0]['invalidReason'])

    def test_small_n_does_not_offer_bootstrap_certainty(self):
        self.assertIsNone(p.paired_summary([.5,.7])['exploratoryPairedBootstrap95'])
        self.assertAlmostEqual(p.paired_summary([.5,.5])['unadjustedTwoSidedSignP'],.5)
        self.assertEqual(p.paired_summary([1,1])['unadjustedTwoSidedSignP'],1)
        self.assertIsNotNone(p.paired_summary([.5,.6,.7,.8])['exploratoryPairedBootstrap95'])

    def test_point_conclusions_keep_partial_pairs_unresolved(self):
        self.frozen_run();rows=p.schedule(self.config)
        for spec in rows[:2]:self.fake_result(self.root/'slots'/spec['label'],spec)
        result=p.report(self.root,self.root/'report')
        self.assertTrue(all(point['completePairDirectionsFavor']=='UNRESOLVED' for point in result['pointConclusions']))
        self.assertTrue(all(not contrast['observedRankingReversalBrackets'] for contrast in result['contrasts']))

    def test_full_point_and_matched_axis_contrast(self):
        self.frozen_run()
        for spec in p.schedule(self.config):self.fake_result(self.root/'slots'/spec['label'],spec)
        result=p.report(self.root,self.root/'report')
        self.assertTrue(all(point['completePairDirectionsFavor']=='CAFFEINE' for point in result['pointConclusions']))
        self.assertTrue(any(c['axis']=='updateHotset' for c in result['contrasts']))
        self.assertTrue(all(not c['observedRankingReversalBrackets'] for c in result['contrasts']))
        summary=result['summaries'][0]['backendForkVariationNs']['CAFFEINE']
        self.assertEqual(summary['n'],2);self.assertEqual(summary['sampleSd'],0)

    def test_reversal_bracket_requires_matched_other_inputs(self):
        self.frozen_run()
        for spec in p.schedule(self.config):
            path=self.root/'slots'/spec['label'];self.fake_result(path,spec)
            if spec['cell']==2 and spec['backend']=='CHRONICLE_IN_MEMORY':
                r=p.load(path/'result.json')
                r['latency']={ch:p.hist_stats([(50,1000)],self.config) for ch in p.CHANNELS}
                (path/'result.json').write_text(json.dumps(r))
                (path/'seal.json').write_text(json.dumps(dict(resultSha256=p.sha(path/'result.json'))))
        result=p.report(self.root,self.root/'report')
        contrast=next(c for c in result['contrasts'] if c['axis']=='updateHotset' and c['channel']=='response' and c['quantile']==99.9)
        bracket=contrast['observedRankingReversalBrackets'][0]
        self.assertEqual((bracket['fromValue'],bracket['toValue']),(2048,32768))
        self.assertEqual((bracket['fromBackend'],bracket['toBackend']),('CAFFEINE','CHRONICLE_IN_MEMORY'))

    def test_java_option_injection_rejected(self):
        with mock.patch.dict(p.os.environ,{'JAVA_TOOL_OPTIONS':'-Xmx2g'}):
            with self.assertRaisesRegex(ValueError,'Unset'):p.java_identity('/unused/java')

    def test_trace_age_logging_does_not_change_gc_parser_format(self):
        command=p.worker_command('/java',self.config,p.schedule(self.config)[0],self.root)
        gc=next(arg for arg in command if ':file=gc.log:' in arg)
        self.assertNotIn('trace',gc)
        self.assertTrue(any('gc+age=trace:file=age.log' in arg for arg in command))
        self.assertIn('-XX:ActiveProcessorCount=12',command)

    def test_offline_reconstruction_rejects_wrong_cached_quantile(self):
        path=self.root/'slot';worker=path/'worker';worker.mkdir(parents=True)
        windows=[dict(phase='MEASUREMENT',operations='10',writes='2',startNs='0',endNs='1000')]
        with (worker/'windows.csv').open('w') as stream:
            stream.write('phase,operations,writes,startNs,endNs\nMEASUREMENT,10,2,0,1000\n')
        counts=dict(service=10,gap=10,response=10,**{'read-service':8,'update-service':2})
        latency={}
        for ch,count in counts.items():
            (worker/(ch+'-bins.csv')).write_text(f'upperEquivalentNs,count\n1,{count}\n')
            latency[ch]=p.hist_stats([(1,count)],self.config)
        latency['response']['percentiles']['99.9']['ns']=999
        r=dict(status='COMPLETE',windows=windows,spec={'qps':50000},latency=latency)
        with self.assertRaisesRegex(ValueError,'Cached histogram statistics differ'):p.verify_derivatives(path,r,self.config)

    def test_second_host_lock_rejected(self):
        if p.os.name=='nt':self.skipTest('same-process Windows lock semantics differ')
        with p.host_lock():
            with self.assertRaisesRegex(ValueError,'host lock'):
                with p.host_lock():pass

    def test_resume_rejects_changed_config_before_launch(self):
        self.frozen_run()
        with mock.patch.object(p,'host_lock',contextlib.nullcontext),mock.patch.object(p,'bundle_identity',return_value='bundle'),\
             mock.patch.object(p,'java_identity',return_value={'id':'jdk'}),mock.patch.object(p,'host_identity',return_value={'id':'host'}),\
             mock.patch.object(p,'launch') as launch:
            c=copy.deepcopy(self.config);c['measureMs']+=1000
            with self.assertRaisesRegex(ValueError,'configuration changed'):p.run(c,self.root)
            launch.assert_not_called()

    def ready_fixture(self):
        host=dict(id='host',cgroupLimits={},cpuPolicy={},clocksource='clock',capability='linux-proc')
        java=dict(id='jdk',executable='/java')
        p.save_new(self.root/'run.json',dict(config=self.config,schedule=p.schedule(self.config),bundleId='bundle',jdk=java,host=host))
        p.save_new(self.root/'functional.json',{'exitCode':0})
        p.save_new(self.root/'jvm-ergonomics.json',{'exitCode':0})
        digests={}
        for backend in p.BACKENDS:
            for inject in (0,20):
                spec=dict(p.schedule(self.config)[0],label=backend+'-'+str(inject),backend=backend)
                path=self.root/'controls'/spec['label'];self.fake_result(path,spec)
                digests[spec['label']]=p.sha(path/'result.json')
        p.save_new(self.root/'qualification.json',dict(passed=True,functionalSha256=p.sha(self.root/'functional.json'),
            ergonomicsSha256=p.sha(self.root/'jvm-ergonomics.json'),controlResultSha256=digests))
        for spec in p.schedule(self.config):self.fake_result(self.root/'slots'/spec['label'],spec)
        return host,java

    def test_resume_completed_run_launches_no_workers(self):
        host,java=self.ready_fixture()
        before={str(f):p.sha(f) for f in (self.root/'slots').rglob('*') if f.is_file()}
        with mock.patch.object(p,'bundle_identity',return_value='bundle'),mock.patch.object(p,'java_identity',return_value=java),\
             mock.patch.object(p,'host_identity',return_value=host),mock.patch.object(p,'readiness'),mock.patch.object(p,'launch') as launch,\
             mock.patch.object(p,'report'):
            p.run(self.config,self.root)
            launch.assert_not_called()
        self.assertEqual(before,{str(f):p.sha(f) for f in (self.root/'slots').rglob('*') if f.is_file()})

    def test_resume_changed_jdk_blocks_before_launch(self):
        host,java=self.ready_fixture();java=dict(java,id='different')
        with mock.patch.object(p,'bundle_identity',return_value='bundle'),mock.patch.object(p,'java_identity',return_value=java),\
             mock.patch.object(p,'host_identity',return_value=host),mock.patch.object(p,'launch') as launch:
            with self.assertRaisesRegex(ValueError,'JDK changed'):p.run(self.config,self.root)
            launch.assert_not_called()

    def test_resume_interrupted_slot_is_not_replaced(self):
        host,java=self.ready_fixture()
        path=self.root/'slots'/p.schedule(self.config)[0]['label'];(path/'result.json').unlink()
        with mock.patch.object(p,'bundle_identity',return_value='bundle'),mock.patch.object(p,'java_identity',return_value=java),\
             mock.patch.object(p,'host_identity',return_value=host),mock.patch.object(p,'readiness'),mock.patch.object(p,'launch') as launch:
            with self.assertRaisesRegex(ValueError,'Interrupted slot retained'):p.run(self.config,self.root)
            launch.assert_not_called()


if __name__=='__main__':unittest.main()
