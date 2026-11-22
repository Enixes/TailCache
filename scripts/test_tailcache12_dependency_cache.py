import copy
import hashlib
import json
import os
import pathlib
import tempfile
import unittest
from contextlib import ExitStack
from unittest.mock import patch

import tailcache12_dependency_cache as dep


def pinned():
    text={'wrapper':dep.URL+'\n','jdkRelease':'JAVA_RUNTIME_VERSION="21.0.12.1+1"\nJAVA_VERSION="21.0.12.1"\n'}
    return {k:dict(text=v,sha256=hashlib.sha256(v.encode()).hexdigest()) for k,v in text.items()}


class DependencyCacheTest(unittest.TestCase):
    def fixture(self,root,stack):
        jdk=root/'jdk';gradle=root/'gradle';modules=root/'modules'
        paths=[jdk/'modules',jdk/'libjvm.so',gradle/'compiler.jar',modules/('g/a/1/'+40*'a'+'/a-1.jar')]
        for p in paths:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'immutable code')
        for name,value in (('EXACT',tuple(paths[:2])),('GRADLE',gradle),('MODULES',modules)):
            stack.enter_context(patch.object(dep,name,value))
        stack.enter_context(patch.object(dep,'declarations',return_value=pinned()))
        stack.enter_context(patch.object(dep,'active_java',return_value=[]))
        stack.enter_context(patch.object(dep.os,'getuid',return_value=os.getuid()))
        stack.enter_context(patch.object(dep.evidence,'source_hash',return_value='source'))
        # Temp files have the operator uid; production's two exact JDK files require root.
        original=dep.EXACT
        stack.enter_context(patch.object(dep,'EXACT',()))
        return paths,original

    def test_exact_policy_excludes_mutable_database_jdk_other_and_escape(self):
        for p in dep.EXACT:self.assertTrue(dep.allowed(str(p)))
        self.assertTrue(dep.allowed(str(dep.GRADLE/'plugins/compiler.jar')))
        self.assertTrue(dep.allowed(str(dep.MODULES/('g/a/1/'+40*'a'+'/a-1.jar'))))
        for p in (dep.GRADLE/'cache.bin',dep.MODULES/'modules-2.lock',dep.MODULES/'g/a/1/not-hash/a.jar',
                  dep.JDK/'lib/other.so',pathlib.Path('/etc/passwd'),dep.GRADLE/'../secret.jar'):
            self.assertFalse(dep.allowed(str(p)))

    def test_readonly_advice_preserves_files_replay_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            root=pathlib.Path(tmp);paths,_=self.fixture(root,stack);paths=paths[2:]
            with patch.object(dep,'targets',return_value=paths),patch.object(dep.os,'posix_fadvise') as advice:
                result=dep.prepare(root/'receipt.json');self.assertTrue(dep.verify(result,'source'))
                self.assertEqual(advice.call_count,2)
                with self.assertRaises(ValueError):dep.prepare(root/'receipt.json')
                for p in paths:self.assertEqual(p.read_bytes(),b'immutable code')
            for mutation in ('source','path','owner','mtime','size','advice','alias','process','declaration'):
                changed=copy.deepcopy(result)
                if mutation=='source':changed['sourceSha256']='other'
                elif mutation=='path':changed['files'][0]['path']='/etc/passwd'
                elif mutation=='owner':changed['files'][0]['uid']+=1
                elif mutation=='mtime':changed['files'][0]['mtimeAfterNs']+=1
                elif mutation=='size':changed['files'][0]['bytesAfter']+=1
                elif mutation=='advice':changed['files'][0]['advice']='GLOBAL_DROP'
                elif mutation=='alias':changed['files'][1].update(device=changed['files'][0]['device'],inode=changed['files'][0]['inode'])
                elif mutation=='process':changed['processChecks']=[[],[{'pid':1}]]
                else:changed['declarations']['wrapper']['text']='unreviewed'
                with self.assertRaises(ValueError):dep.verify(changed,'source')

    def test_java_at_either_inspection_prevents_all_advice(self):
        for checks in (([{'pid':1}],),([],[{'pid':2}])):
            with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
                root=pathlib.Path(tmp);paths,_=self.fixture(root,stack)
                with patch.object(dep,'targets',return_value=paths[2:]),patch.object(dep,'active_java',side_effect=checks), \
                     patch.object(dep.os,'posix_fadvise') as advice:
                    with self.assertRaises(ValueError):dep.prepare(root/'receipt.json')
                    advice.assert_not_called();self.assertFalse(json.loads((root/'receipt.json').read_text())['preparationPass'])

    def test_all_targets_validated_before_advice_and_symlinks_refused(self):
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            root=pathlib.Path(tmp);paths,_=self.fixture(root,stack)
            alias=dep.MODULES/('g/a/1/'+40*'b'+'/alias.jar');alias.parent.mkdir();os.link(paths[2],alias)
            with patch.object(dep,'targets',return_value=[paths[2],alias]),patch.object(dep.os,'posix_fadvise') as advice:
                with self.assertRaises(ValueError):dep.prepare(root/'alias.json')
                advice.assert_not_called()
            alias.unlink();alias.symlink_to(paths[2])
            with self.assertRaises(ValueError):dep.targets()

    def test_wrong_jdk_owner_is_rejected_before_any_advice(self):
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            root=pathlib.Path(tmp);paths,exact=self.fixture(root,stack)
            with patch.object(dep,'EXACT',exact),patch.object(dep,'targets',return_value=paths), \
                 patch.object(dep.os,'posix_fadvise') as advice:
                with self.assertRaises(ValueError):dep.prepare(root/'owner.json')
                advice.assert_not_called()

    def test_mtime_change_during_advice_is_retained_failure(self):
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            root=pathlib.Path(tmp);paths,_=self.fixture(root,stack);target=paths[2]
            def changed(*args):os.utime(target,ns=(target.stat().st_atime_ns,target.stat().st_mtime_ns+1))
            with patch.object(dep,'targets',return_value=[target]),patch.object(dep.os,'posix_fadvise',side_effect=changed):
                with self.assertRaises(ValueError):dep.prepare(root/'changed.json')
            record=json.loads((root/'changed.json').read_text());self.assertTrue(record['errors']);self.assertFalse(record['preparationPass'])

    def test_pinned_version_hash_and_duplicate_keys_rejected(self):
        for text in (dep.URL.replace('9.7.1','9.7.2'),dep.URL+'\ndistributionUrl=other'):
            values=pinned();values['wrapper']=dict(text=text,sha256=hashlib.sha256(text.encode()).hexdigest())
            with self.assertRaises(ValueError):dep.verify_declarations(values)


if __name__=='__main__':unittest.main()
