import fcntl
import hashlib
import json
import pathlib
import tempfile
import unittest

from tailcache12_archive import create_archive,CHUNK


class ArchiveTest(unittest.TestCase):
    def test_incremental_archive_binds_parent_and_includes_every_declared_prefix_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);reports=root/'build/reports/tailcache12';reports.mkdir(parents=True)
            (reports/'native-final-old').write_bytes(b'old evidence')
            parent=create_archive(root,'native-final-parent.tar.gz');before=pathlib.Path(parent['path']).read_bytes()
            (reports/'native-final-new').write_bytes(b'new evidence')
            result=create_archive(root,'native-final-increment.tar.gz',include_prefixes=['native-final-new'],
                parent=('native-final-parent.tar.gz',parent['sha256']))
            self.assertEqual(result['verifiedMembers'],1)
            self.assertEqual(result['parentArchive']['sha256'],parent['sha256'])
            self.assertEqual(before,pathlib.Path(parent['path']).read_bytes())
            prepared=create_archive(root,'native-final-with-prep.tar.gz',
                cache_prepare=lambda path:path.write_text('unit-test preparation proof'),
                include_prefixes=['native-final-new'],parent=('native-final-parent.tar.gz',parent['sha256']))
            self.assertEqual(prepared['verifiedMembers'],2)
            self.assertTrue(any('with-prep-cache-preparation.json' in name for name in prepared['members']))
            for name,prefixes,ref in (
                    ('missing-parent',['native-final-new'],None),
                    ('wrong-parent',['native-final-new'],('native-final-parent.tar.gz','0'*64)),
                    ('missing-prefix',['native-final-new','native-final-absent'],('native-final-parent.tar.gz',parent['sha256']))):
                with self.assertRaises(ValueError):create_archive(root,'native-final-'+name+'.tar.gz',include_prefixes=prefixes,parent=ref)
                self.assertFalse((root/'evidence-archives'/('native-final-'+name+'.tar.gz')).exists())
            pathlib.Path(parent['path']).write_bytes(before+b'changed')
            with self.assertRaises(ValueError):create_archive(root,'native-final-tampered.tar.gz',include_prefixes=['native-final-new'],parent=('native-final-parent.tar.gz',parent['sha256']))

    def test_streamed_members_verify_and_existing_evidence_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory); reports=root/'build/reports/tailcache12'
            data=reports/'native-final-fixture'/'raw.bin'; data.parent.mkdir(parents=True)
            payload=b'bounded-stream'*200000; data.write_bytes(payload)
            (reports/'user-file').write_text('exclude')
            result=create_archive(root,'native-final-test.tar.gz')
            self.assertEqual(CHUNK,result['hashChunkBytes']); self.assertEqual(1,result['verifiedMembers'])
            self.assertEqual(hashlib.sha256(payload).hexdigest(),result['members'][data.relative_to(root).as_posix()])
            out=pathlib.Path(result['path']); before=out.read_bytes()
            with self.assertRaises(ValueError): create_archive(root,'native-final-test.tar.gz')
            self.assertEqual(before,out.read_bytes()); self.assertEqual(payload,data.read_bytes())
            self.assertTrue(json.loads(out.with_suffix('.json').read_text())['verifiedMembers'])

    def test_benchmark_lock_prevents_archiving_and_external_output_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory); reports=root/'build/reports/tailcache12'; reports.mkdir(parents=True)
            with (reports/'native-benchmark.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaises(ValueError): create_archive(root,'native-final-test.tar.gz')
            self.assertFalse((root/'evidence-archives/native-final-test.tar.gz').exists())
            with self.assertRaises(ValueError): create_archive(root,'../outside.tar.gz')


if __name__=='__main__': unittest.main()
