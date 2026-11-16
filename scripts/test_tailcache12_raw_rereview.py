import pathlib
import subprocess
import sys
import tempfile
import unittest

import tailcache12_raw_rereview as review


class RawReviewFailureTest(unittest.TestCase):
    def test_raw_auditors_refuse_optimized_python_before_writing(self):
        for script in ('scripts/tailcache12_raw_rereview.py', 'ops/tailcache12_final_raw_audit.py'):
            with self.subTest(script=script), tempfile.TemporaryDirectory() as tmp:
                out = pathlib.Path(tmp) / 'audit'
                result = subprocess.run([sys.executable, '-O', str(review.ROOT / script),
                                         '--out', str(out)], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Run without -O', result.stderr)
                self.assertFalse(out.exists())

    def test_existing_evidence_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            marker = out / 'audit.json'
            marker.write_bytes(b'previous receipt\n')
            with self.assertRaises(FileExistsError):
                review.run(out)
            self.assertEqual(marker.read_bytes(), b'previous receipt\n')
            self.assertEqual(list(out.iterdir()), [marker])

    def test_empty_distribution_cannot_produce_a_percentile(self):
        with self.assertRaisesRegex(ValueError, 'Empty rank input'):
            review.rank([], 99.999)


if __name__ == '__main__':
    unittest.main()
