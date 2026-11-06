import json
import pathlib
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch,Mock

import tailcache12_jit_events as diagnostic


class AttachmentTest(unittest.TestCase):
    def test_failed_cache_preparation_cannot_reach_quiet_or_worker_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(diagnostic.evidence,'REPORTS',pathlib.Path(directory)), \
                 patch.object(diagnostic.evidence,'source_hash',return_value='source'), \
                 patch.object(diagnostic,'prepare_file_cache',side_effect=ValueError('residual swap')), \
                 patch.object(diagnostic,'run_preflight') as quiet, \
                 patch.object(diagnostic.subprocess,'run') as launch, \
                 patch('sys.argv',['diagnostic','fresh','--attach-logs','--channels','every-operation']):
                with self.assertRaises(ValueError): diagnostic.main()
                quiet.assert_not_called();launch.assert_not_called()

    def test_actual_main_class_token_and_scope_are_bound_to_the_declared_channel(self):
        original=pathlib.Path
        with tempfile.TemporaryDirectory() as directory:
            root=original(directory);worker=root/'42';worker.mkdir()
            (worker/'stat').write_text('42 (java worker) '+' '.join(['S']+['0']*18+['100']))
            (worker/'cgroup').write_text('0::/user.slice/tailcache12-test.scope\n')
            with patch.object(diagnostic.pathlib,'Path',side_effect=lambda value:root if value=='/proc' else original(value)), \
                 patch.dict(diagnostic.os.environ,{'TAILCACHE_NATIVE_SCOPE':'tailcache12-test.scope'}):
                for channel in ('every-operation','sample-calibration','floor'):
                    main=diagnostic.worker_main_class(channel)
                    (worker/'cmdline').write_bytes(b'java\0-Xmx512m\0'+main.encode()+b'\0')
                    identity=diagnostic.worker_identity(42,channel)
                    self.assertEqual(main,identity['mainClass']);self.assertEqual('100',identity['startTicks'])
                    (worker/'cmdline').write_bytes(b'java\0-Ddecoy='+main.encode()+b'\0GradleMain\0')
                    with self.assertRaises(ValueError): diagnostic.worker_identity(42,channel)
                (worker/'cmdline').write_bytes(b'java\0org.openjdk.jmh.runner.ForkedMain\0')
                with self.assertRaises(ValueError): diagnostic.worker_identity(42,'every-operation')
                (worker/'cgroup').write_text('0::/other.scope\n')
                with self.assertRaises(ValueError): diagnostic.worker_identity(42,'sample-calibration')

    def test_attachment_targets_unique_worker_without_startup_options_and_retains_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory); raw=root/'raw'; raw.mkdir()
            control=root/'control'; control.mkdir()
            (raw/'worker-process-42.properties').write_text('pid=42\n')
            result={}; identity=dict(pid=42,startTicks='100',cgroup='scope')
            def command(args,**kwargs):
                self.assertEqual(['42','VM.log'],args[1:3]); self.assertEqual(30,kwargs['timeout'])
                (control/'hotspot-jit-42.log').write_text('retained-events')
                return Mock(returncode=0,stdout='42: command executed',stderr='')
            with patch.object(diagnostic,'worker_identity',return_value=identity), \
                 patch.object(diagnostic.subprocess,'run',side_effect=command), \
                 patch.dict(diagnostic.os.environ,{'JAVA_HOME':'/jdk'}):
                diagnostic.attach_worker_logging(raw,control,threading.Event(),result,delay=0)
            self.assertTrue(result['success'])
            self.assertEqual('/jdk/bin/jcmd',result['command'][0])
            self.assertEqual(result,json.loads((control/'attachment.json').read_text()))

    def test_missing_ambiguous_reused_or_timed_out_target_is_fatal(self):
        for mode in ('missing','ambiguous','reused','timeout'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as directory:
                root=pathlib.Path(directory)
                if mode!='missing': (root/'worker-process-42.properties').write_text('pid=42\n')
                if mode=='ambiguous': (root/'worker-process-43.properties').write_text('pid=43\n')
                identity=dict(pid=42,startTicks='100')
                values=[identity,dict(identity,startTicks='101')] if mode=='reused' else [identity]*3
                result={}
                with patch.object(diagnostic,'worker_identity',side_effect=values), \
                     patch.object(diagnostic.subprocess,'run',side_effect=subprocess.TimeoutExpired('jcmd',30)) as run, \
                     patch.dict(diagnostic.os.environ,{'JAVA_HOME':'/jdk'}):
                    diagnostic.attach_worker_logging(root,root,threading.Event(),result,delay=0,
                                                     marker_timeout=0 if mode=='missing' else 1)
                self.assertFalse(result['success']); self.assertIn('error',result)
                if mode!='timeout': run.assert_not_called()

    def test_late_attachment_and_changed_retained_artifacts_fail_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory); p=root/'attachment.json'
            record=dict(method='jcmd-VM.log-v1',success=True,pid=42,exitCode=0,startNs=10**9,endNs=2*10**9)
            p.write_text(json.dumps(record))
            diagnostic.verify_attachment(root,'42',[(63*10**9,64*10**9)])
            with self.assertRaises(ValueError): diagnostic.verify_attachment(root,'42',[(61*10**9,62*10**9)])
            with self.assertRaises(ValueError): diagnostic.verify_attachment(root,'43',[(63*10**9,64*10**9)])
            artifacts={'attachment.json':diagnostic.calibration.sha(p)}
            diagnostic.verify_artifacts(root,artifacts); p.write_text(p.read_text()+'\n')
            with self.assertRaises(ValueError): diagnostic.verify_artifacts(root,artifacts)

    def test_new_recorder_receipt_binds_channel_and_main_while_legacy_jmh_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);p=root/'attachment.json';windows=[(63*10**9,64*10**9)]
            record=dict(method='jcmd-VM.log-v2',success=True,pid=42,exitCode=0,startNs=10**9,endNs=2*10**9,
                channel='every-operation',identity=dict(mainClass=diagnostic.worker_main_class('every-operation')))
            p.write_text(json.dumps(record))
            diagnostic.verify_attachment(root,'42',windows,'every-operation')
            with self.assertRaises(ValueError): diagnostic.verify_attachment(root,'42',windows,'floor')
            record['identity']['mainClass']='GradleMain';p.write_text(json.dumps(record))
            with self.assertRaises(ValueError): diagnostic.verify_attachment(root,'42',windows,'every-operation')
            record['method']='jcmd-VM.log-v1';p.write_text(json.dumps(record))
            diagnostic.verify_attachment(root,'42',windows)
            with self.assertRaises(ValueError): diagnostic.verify_attachment(root,'42',windows,'every-operation')


if __name__=='__main__': unittest.main()
