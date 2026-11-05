import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import tailcache12_calibration_start as start


class CachePreparationTest(unittest.TestCase):
    def test_task_only_advice_preserves_bytes_and_retains_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            reports=root/'build/reports/tailcache12'; reports.mkdir(parents=True)
            archives=root/'evidence-archives'; archives.mkdir()
            raw=reports/'retained.log'; raw.write_bytes(b'raw evidence')
            archive=archives/'retained.tar.gz'; archive.write_bytes(b'archive evidence')
            foreign=root/'user-file'; foreign.write_bytes(b'preserve')
            (reports/'link').symlink_to(foreign)
            report=reports/'preparation.json'
            with patch.object(start.evidence,'ROOT',root), patch.object(start.evidence,'REPORTS',reports), \
                 patch.object(start.evidence,'source_hash',return_value='source'), \
                 patch.object(start,'memory_snapshot',return_value={'MemFreeKiB':4*1024**2,'SwapUsedKiB':0}), \
                 patch.object(start.os,'posix_fadvise') as advice:
                result=start.prepare_file_cache(report)
            self.assertEqual(2,advice.call_count)
            self.assertEqual({'build/reports/tailcache12/retained.log','evidence-archives/retained.tar.gz'},
                             {r['path'] for r in result['files']})
            self.assertTrue(json.loads(report.read_text())['preparationPass'])
            self.assertEqual(b'raw evidence',raw.read_bytes())
            self.assertEqual(b'archive evidence',archive.read_bytes())
            self.assertEqual(b'preserve',foreign.read_bytes())

    def test_insufficient_free_ram_and_advice_failure_stop_and_retain_reason(self):
        for free,error in ((2*1024**2,None),(4*1024**2,OSError('advice failed'))):
            with self.subTest(free=free),tempfile.TemporaryDirectory() as directory:
                root=pathlib.Path(directory); raw=root/'raw'; raw.write_bytes(b'evidence')
                report=root/'preparation.json'
                with patch.object(start.evidence,'ROOT',root),patch.object(start.evidence,'REPORTS',root), \
                     patch.object(start.evidence,'source_hash',return_value='source'), \
                     patch.object(start,'memory_snapshot',return_value={'MemFreeKiB':free,'SwapUsedKiB':0}), \
                     patch.object(start.os,'posix_fadvise',side_effect=error):
                    with self.assertRaises(ValueError): start.prepare_file_cache(report)
                result=json.loads(report.read_text())
                self.assertFalse(result['preparationPass'])
                self.assertEqual(bool(error),bool(result['errors']))

    def test_residual_swap_blocks_benchmarks_but_is_explicit_for_archival_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            with patch.object(start.evidence,'ROOT',root),patch.object(start.evidence,'REPORTS',root), \
                 patch.object(start.evidence,'source_hash',return_value='source'), \
                 patch.object(start,'memory_snapshot',return_value={'MemFreeKiB':4*1024**2,'SwapUsedKiB':128}), \
                 patch.object(start.os,'posix_fadvise'):
                with self.assertRaises(ValueError): start.prepare_file_cache(root/'benchmark.json')
                result=start.prepare_file_cache(root/'archive.json',require_empty_swap=False)
            self.assertTrue(result['preparationPass']); self.assertFalse(result['requiresEmptySwap'])


if __name__=='__main__': unittest.main()
