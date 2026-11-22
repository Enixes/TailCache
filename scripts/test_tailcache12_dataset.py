import fcntl
import pathlib
import os
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import tailcache12_dataset as dataset


class DatasetArchiveTest(unittest.TestCase):
    def test_nested_dependencies_and_historical_raw_files_are_verified_once_with_bounded_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);reports=root/'reports';reports.mkdir();attempt=reports/'primary';attempt.mkdir()
            nested=attempt/'quiet';nested.mkdir();(nested/'host.csv').write_text('retained quiet')
            raw=reports/'historical-raw';raw.mkdir();(raw/'log.bin').write_bytes(b'archive fixture'*100000)
            os.link(raw/'log.bin',raw/'hardlink.bin')
            (reports/'native-benchmark.lock').touch()
            (reports/'outside-link').symlink_to(root/'secret');(root/'secret').write_text('outside')
            archive=root/'export.tar.gz';calls=[]
            real_digest=dataset.stream_digest
            def bounded(stream):
                class BoundedReader:
                    def read(self,size=-1):
                        self_outer.assertGreater(size,0);self_outer.assertLessEqual(size,1024*1024)
                        calls.append(size);return stream.read(size)
                return real_digest(BoundedReader())
            self_outer=self
            with patch.object(dataset.evidence,'ROOT',root),patch.object(dataset.evidence,'REPORTS',reports), \
                 patch.object(dataset,'stream_digest',side_effect=bounded):
                inventory,result=dataset.archive_reports(archive,{attempt,nested})
                self.assertEqual(3,result['verifiedMembers']);self.assertTrue(calls)
                with tarfile.open(archive) as saved:
                    names=saved.getnames();self.assertEqual(3,len(set(names)));self.assertEqual(3,len(names))
                    self.assertTrue(all(member.isfile() for member in saved.getmembers()))
                    self.assertIn('reports/historical-raw/log.bin',names)
                self.assertFalse(result['historicalEvidencePooled'])
                with self.assertRaises(FileExistsError):dataset.archive_reports(archive,{attempt})
                with self.assertRaises(ValueError):dataset.archive_reports(root/'bad.tar.gz',{root/'missing'})

    def test_export_refuses_existing_destination_and_active_benchmark_before_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);reports=root/'reports';reports.mkdir();destination=root/'dataset'
            with patch.object(dataset.evidence,'REPORTS',reports),patch.object(dataset,'export_locked') as run:
                destination.mkdir()
                with self.assertRaises(ValueError):dataset.export(reports/'primary',reports/'robustness',destination)
                destination.rmdir()
                with (reports/'native-benchmark.lock').open('a') as lock:
                    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    with self.assertRaises(ValueError):dataset.export(reports/'primary',reports/'robustness',destination)
                run.assert_not_called()


if __name__=='__main__':unittest.main()
