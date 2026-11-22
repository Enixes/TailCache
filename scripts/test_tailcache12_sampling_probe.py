import pathlib
import tempfile
import unittest
from unittest.mock import patch

import tailcache12_sampling_probe as probe


class SamplingProbePreparationTest(unittest.TestCase):
    def test_diagnostic_modes_refuse_inherited_vm_override(self):
        for mode in ('opaque-operation','tlab-debug','fixed-buffer'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                with (patch.object(probe.evidence, 'REPORTS', pathlib.Path(directory)),
                      patch('sys.argv', ['probe','new-probe','new-quiet','--plan',mode]),
                      patch.dict(probe.os.environ, {'JAVA_TOOL_OPTIONS':'-Xmx42m'}),
                      patch.object(probe, 'prepare_file_cache') as prepare):
                    with self.assertRaises(ValueError): probe.main()
                    prepare.assert_not_called()
                    self.assertFalse(list(pathlib.Path(directory).iterdir()))

    def test_failed_quiet_or_changed_source_cannot_launch(self):
        for quiet, hashes in ((False, ['same', 'same']), (True, ['before', 'after'])):
            with self.subTest(quiet=quiet), tempfile.TemporaryDirectory() as directory:
                with (patch.object(probe.evidence, 'REPORTS', pathlib.Path(directory)),
                      patch('sys.argv', ['probe', 'new-probe', 'new-quiet']),
                      patch.object(probe.evidence, 'source_hash', side_effect=hashes),
                      patch.object(probe, 'measurement_source_hash', return_value='measurement'),
                      patch.object(probe, 'prepare_file_cache', return_value={}),
                      patch.object(probe, 'run_preflight', return_value={'quietPass': quiet}),
                      patch.object(probe.evidence, 'save'),
                      patch.object(probe.subprocess, 'run') as run):
                    with self.assertRaises(ValueError):
                        probe.main()
                    run.assert_not_called()
                    self.assertTrue((pathlib.Path(directory) / 'new-probe-declaration.json').is_file())

    def test_existing_evidence_refused_before_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            (pathlib.Path(directory) / 'retained-probe').mkdir()
            with (patch.object(probe.evidence, 'REPORTS', pathlib.Path(directory)),
                  patch('sys.argv', ['probe', 'retained-probe', 'new-quiet']),
                  patch.object(probe, 'prepare_file_cache') as prepare):
                with self.assertRaises(ValueError):
                    probe.main()
                prepare.assert_not_called()


if __name__ == '__main__':
    unittest.main()
