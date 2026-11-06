import copy
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch,Mock
from contextlib import ExitStack
import hashlib
import threading

import tailcache12_perfdata as perf


class PerfDataTest(unittest.TestCase):
    def test_sampler_failure_is_retained_and_cannot_be_reported_as_nonreproduction(self):
        import tailcache12_jit_events as driver
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);raw=root/'raw';raw.mkdir();control=root/'control';control.mkdir()
            (raw/'worker-process-42.properties').write_text('pid=42\n')
            process=Mock(pid=99);process.poll.return_value=1;process.wait.return_value=1
            with patch.object(driver,'worker_identity',return_value={'pid':42}), \
                 patch.object(perf,'helper_command',return_value=['read-only-helper']), \
                 patch.object(perf.subprocess,'Popen',return_value=process):
                result={};perf.sample_worker(raw,control,threading.Event(),result,{})
            self.assertFalse(result['success']);self.assertEqual(1,result['exitCode'])
            self.assertIn('error',result)
            self.assertEqual(result,json.loads((control/'perfdata-receipt.json').read_text()))

    def test_frozen_helper_hashes_replay_after_relocation_and_reject_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);original=root/'original';original.mkdir();attempt=root/'attempt';attempt.mkdir()
            name='TailCacheCompilerPerfSampler.class';data=b'compiled-helper';(original/name).write_bytes(data)
            build=dict(directory=str(original),classSha256={name:hashlib.sha256(data).hexdigest()})
            frozen=perf.freeze_build(build,attempt);frozen['directory']='/old/machine/path'
            perf.verify_build(frozen,attempt/'perfdata-helper')
            with self.assertRaises(FileExistsError): perf.freeze_build(build,attempt)
            (attempt/'perfdata-helper'/name).write_bytes(b'changed')
            with self.assertRaises(ValueError): perf.verify_build(frozen,attempt/'perfdata-helper')

    def test_sampler_replay_requires_bound_main_pid_and_early_start_with_dense_coverage(self):
        import tailcache12_jit_events as driver
        rows=self.fixture();template=rows[1];samples=[]
        for i in range(650):
            sample=copy.deepcopy(template);sample.update(startNs=10**9+i*10**8,endNs=10**9+i*10**8+10);samples.append(sample)
        rows=[rows[0],*samples,dict(kind='end',endNs=67*10**9,targetAlive=False,stopRequested=False)]
        receipt=dict(method='shared-perfdata-v1',success=True,pid=42,samplerPid=43,exitCode=0,
            channel='every-operation',identity=dict(mainClass=driver.worker_main_class('every-operation')),
            startNs=500000000,endNs=68*10**9)
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);file=root/'perfdata-receipt.json'
            (root/'perfdata.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            file.write_text(json.dumps(receipt));windows=[(62*10**9,63*10**9)]
            self.assertEqual(650,perf.verify_sampler(root,'42',windows,'every-operation')['sampleCount'])
            for change in (dict(pid=99),dict(success=False),dict(startNs=3*10**9),
                           dict(identity=dict(mainClass='GradleMain'))):
                file.write_text(json.dumps(dict(receipt,**change)))
                with self.assertRaises(ValueError): perf.verify_sampler(root,'42',windows,'every-operation')

    def test_passive_driver_compiles_before_quiet_and_never_sets_target_logging_or_attaches(self):
        import tailcache12_jit_events as driver
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);events=[]
            def quiet(path,*args):path.mkdir();events.append('quiet');return {'quietPass':True}
            def prepare(attempt,*args):attempt.mkdir();return {'invocations':[]}
            def sample(raw,control,stop,result,**kwargs):
                control.mkdir(exist_ok=True)
                for name in ('perfdata-receipt.json','perfdata.jsonl','perfdata.stdout','perfdata.stderr'):
                    (control/name).write_text('retained fixture')
                result.update(success=True,pid=42)
            def invoke(attempt,manifest,label,task,props):
                self.assertNotIn('JAVA_TOOL_OPTIONS',driver.os.environ)
                self.assertEqual('false',props['CompilerDiagnostics'])
                self.assertEqual('tailCache12EveryOperation',task)
                events.append('worker');manifest['invocations'].append({'label':label,'properties':props})
            row=dict(rejectionReasons=[],compilerPerIterationMs=[0]*8,compilerViolation=False)
            with ExitStack() as stack:
                stack.enter_context(patch.dict(driver.os.environ,{},clear=True))
                for target,name,options in (
                    (driver.evidence,'REPORTS',dict(new=root)),
                    (driver.evidence,'source_hash',dict(return_value='source')),
                    (driver.evidence,'host_snapshot',dict(return_value={})),
                    (driver.evidence.native_host,'environment_declaration',dict(return_value={})),
                    (driver.perfdata,'compile_helper',dict(side_effect=lambda:events.append('compile') or {})),
                    (driver.perfdata,'freeze_build',dict(return_value={})),
                    (driver.perfdata,'sample_worker',dict(side_effect=sample)),
                    (driver,'attach_worker_logging',dict(side_effect=AssertionError('Target attachment forbidden'))),
                    (driver,'prepare_file_cache',dict(return_value={})),
                    (driver,'run_preflight',dict(side_effect=quiet)),
                    (driver.retry,'initial_quiet_reference',dict(return_value={})),
                    (driver.retry,'verify_initial_quiet',dict()),
                    (driver.calibration,'prepare',dict(side_effect=prepare)),
                    (driver.evidence,'invoke',dict(side_effect=invoke)),
                    (driver,'analyze',dict(return_value=row)),
                ):stack.enter_context(patch.object(target,name,**options))
                stack.enter_context(patch('sys.argv',['diagnostic','passive','--perfdata','--repeats','1',
                                                      '--payloads','4096','--channels','every-operation']))
                self.assertEqual(0,driver.main())
            self.assertEqual(['compile','quiet','worker'],events)
            manifest=json.loads((root/'passive/manifest.json').read_text())
            self.assertTrue(manifest['passivePerfdata'])
            self.assertEqual('none; external shared PerfData only',next(iter(manifest['diagnosticJvmOptions'].values())))

    def fixture(self):
        def sample(start,total,method):
            return dict(kind='sample',startNs=start,endNs=start+10,values={
                'java.ci.totalTime':total,'sun.ci.totalCompiles':total//2000000,
                'sun.ci.lastMethod':method,'sun.os.hrt.frequency':1000000000})
        return [dict(kind='metadata',version=1,intervalMs=10,targetPid=42,samplerPid=43,
                     counters=[dict(name=n,units=u) for n,u in {'java.ci.totalTime':'Ticks',
                         'sun.ci.totalCompiles':'Events','sun.ci.lastMethod':'String','sun.os.hrt.frequency':'Hertz'}.items()]),
                sample(100,0,'before'),sample(200,2000000,'candidate'),
                dict(kind='end',endNs=220,targetAlive=False,stopRequested=False)]

    def parse(self,rows,windows=(),pid=42):
        with tempfile.TemporaryDirectory() as directory:
            path=pathlib.Path(directory)/'perf.jsonl'
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            return perf.read_samples(path,windows,pid)

    def test_shared_counter_delta_is_only_a_candidate_and_worker_coverage_is_required(self):
        result=self.parse(self.fixture(),[(120,190)])
        self.assertEqual(2,result['sampleCount'])
        candidate=result['compilerCounterCandidates'][0]
        self.assertEqual(2,candidate['compilationDeltaMs'])
        self.assertEqual('candidate',candidate['lastMethodAfter'])
        self.assertTrue(any('non-atomic' in limit for limit in result['limits']))
        with self.assertRaises(ValueError): self.parse(self.fixture(),[(90,190)])
        with self.assertRaises(ValueError): self.parse(self.fixture(),[(120,220)])

    def test_partial_wrong_pid_and_counter_clock_corruption_never_become_nonreproduction(self):
        original=self.fixture();bad=[]
        bad.append(original[:-1]);bad.append(original[1:])
        for mutate in (
            lambda x:x[0].update(targetPid=43),
            lambda x:x[0].update(counters=[]),
            lambda x:x[1]['values'].update({'java.ci.totalTime':3000000}),
            lambda x:x[2]['values'].update({'sun.os.hrt.frequency':0}),
            lambda x:x[2]['values'].update({'sun.os.hrt.frequency':'invalid'}),
            lambda x:x[2].update(startNs=100),
            lambda x:x[-1].update(endNs=1),
            lambda x:x[-1].update(targetAlive=True),
        ):
            rows=copy.deepcopy(original);mutate(rows);bad.append(rows)
        for rows in bad:
            with self.subTest(rows=rows),self.assertRaises(ValueError): self.parse(rows)
        with self.assertRaises(ValueError): self.parse(original,pid=99)

    def test_sparse_or_slow_reads_cannot_supply_valid_worker_attribution(self):
        rows=self.fixture();rows[2].update(startNs=300000000,endNs=300000010)
        rows[-1]['endNs']=300000020
        with self.assertRaises(ValueError):self.parse(rows,[(1000,2000)])
        rows=self.fixture();rows[1]['endNs']=60000000
        rows[2].update(startNs=100000000,endNs=100000010);rows[-1]['endNs']=100000020
        with self.assertRaises(ValueError):self.parse(rows,[(70000000,80000000)])


if __name__=='__main__':unittest.main()
