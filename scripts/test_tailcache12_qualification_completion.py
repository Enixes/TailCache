import copy
import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import tailcache12_calibration_start as start
import tailcache12_complete_qualification as complete


class CompleteRecorderReferenceTest(unittest.TestCase):
    def test_failed_initial_quiet_or_source_change_never_starts_completion_jvms(self):
        for quiet_pass in (False,True):
            with self.subTest(quiet_pass=quiet_pass),tempfile.TemporaryDirectory() as directory:
                root=pathlib.Path(directory)
                def quiet(path,*args):
                    path.mkdir(); return dict(quietPass=quiet_pass)
                with patch.object(complete.evidence,'REPORTS',root), \
                     patch.object(complete,'validate_completed',return_value={}), \
                     patch.object(complete,'measurement_source_hash',return_value='measurement'), \
                     patch.object(complete.evidence,'source_hash',side_effect=['original','changed']), \
                     patch.object(complete,'prepare_file_cache',return_value={}), \
                     patch.object(complete,'run_preflight',side_effect=quiet), \
                     patch.object(complete.subprocess,'run') as launch, \
                     patch.object(complete.sys,'argv',['completion','new','--prefix','old','--everyop-reference','new-recorder']):
                    with self.assertRaises(ValueError): complete.main()
                    launch.assert_not_called()

    def manifest(self):
        props=dict(Residents=32768,HeapMiB=512,LiveBytes=0,ChurnBytesPerSecond=33554432,Seed=24301,
            Warmups=120,Conditioning=8,TransportWarmupVersion=start.evidence.TRANSPORT_WARMUP_VERSION,
            LifecycleWarmupVersion=start.evidence.LIFECYCLE_WARMUP_VERSION)
        return dict(stage='everyop-jit',invocations=[dict(properties=dict(props,Backend=b,Payload=p))
            for _ in range(2) for b in start.evidence.BACKENDS for p in (256,4096)])

    def test_only_a_complete_matching_actual_recorder_screen_is_eligible(self):
        m=self.manifest(); result=dict(qualityPass=True,compilerXml=False)
        start.validate_actual_recorder(m,result)
        for changed in (dict(m,invocations=m['invocations'][:7]),dict(m,stage='probe')):
            with self.assertRaises(ValueError): start.validate_actual_recorder(changed,result)
        for field,value in (('LiveBytes',96),('Seed',17),('Backend','CAFFEINE')):
            bad=copy.deepcopy(m)
            for v in bad['invocations']: v['properties'][field]=value
            with self.assertRaises(ValueError): start.validate_actual_recorder(bad,result)
        for bad in (dict(result,qualityPass=False),dict(result,compilerXml=True)):
            with self.assertRaises(ValueError): start.validate_actual_recorder(m,bad)

    def test_explicit_reference_binds_whole_new_screen_without_using_failed_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            for name,report,flag in (('functional','replayed-audit.json','functionalPass'),
                    ('pause','replayed-audit.json','functionalPass'),('jit','replayed-audit.json','functionalPass'),
                    ('everyop','everyop-jit.json','qualityPass'),('pressure96','everyop-jit.json','qualityPass'),
                    ('floors','floors.json','floorDataPass'),('new-recorder','everyop-jit.json','qualityPass')):
                path=root/('new-recorder' if name=='new-recorder' else 'original-'+name); path.mkdir()
                (path/'source.tar.gz').write_bytes(b'source')
                m=self.manifest(); m['sourceArchiveSha256']=hashlib.sha256(b'source').hexdigest()
                (path/'manifest.json').write_text(json.dumps(m))
                (path/report).write_text(json.dumps({flag:name!='everyop','compilerXml':False}))
            with patch.object(start.evidence,'REPORTS',root),patch.object(start.evidence,'host_snapshot'), \
                 patch.object(start,'measurement_source_hash',return_value='current'), \
                 patch.object(start,'archive_measurement_source_hash',return_value='current'), \
                 patch('tailcache12_pilot.verify_native_environments'):
                with self.assertRaises(ValueError): start.qualification_bindings('original')
                refs=start.qualification_bindings('original','new-recorder')
                self.assertEqual('new-recorder',refs['everyop']['attempt'])
                self.assertEqual('original-jit',refs['jit']['attempt'])
                self.assertEqual(6,len(refs))
                for file in root.glob('*/manifest.json'):
                    m=json.loads(file.read_text())
                    for v in m['invocations']: v['properties']['Conditioning']=16
                    file.write_text(json.dumps(m))
                with self.assertRaises(ValueError): start.qualification_bindings('original','new-recorder')
                updated=start.qualification_bindings('original','new-recorder',16)
                self.assertEqual('new-recorder',updated['everyop']['attempt'])
                self.assertNotEqual(refs['everyop']['manifestSha256'],updated['everyop']['manifestSha256'])

    def test_new_calibration_forwards_declared_conditioning_after_matching_binding(self):
        for conditioning in (8,16):
            with self.subTest(conditioning=conditioning),tempfile.TemporaryDirectory() as directory:
                root=pathlib.Path(directory)
                def quiet(path,*args): path.mkdir(); return dict(quietPass=True)
                from unittest.mock import Mock
                with patch.object(start.evidence,'REPORTS',root), \
                     patch.object(start.evidence,'source_hash',return_value='source'), \
                     patch.object(start,'prepare_file_cache',return_value={}), \
                     patch.object(start,'qualification_bindings',return_value={}) as bindings, \
                     patch.object(start,'run_preflight',side_effect=quiet), \
                     patch.object(start.subprocess,'run',return_value=Mock(returncode=0)) as launch, \
                     patch.object(start.sys,'argv',['start','calibration','quiet','--qualification-prefix','qualified',
                                                  '--conditioning',str(conditioning)]):
                    self.assertEqual(0,start.main())
                    bindings.assert_called_once_with('qualified',None,conditioning)
                    command=launch.call_args.args[0]
                    self.assertEqual(str(conditioning),command[command.index('--conditioning')+1])


if __name__=='__main__': unittest.main()
