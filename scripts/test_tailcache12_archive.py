import fcntl
import hashlib
import json
import pathlib
import tempfile
import unittest

from tailcache12_archive import create_archive,CHUNK


class ArchiveTest(unittest.TestCase):
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
