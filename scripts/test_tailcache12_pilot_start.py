import pathlib
import tempfile
import unittest
from unittest.mock import patch,Mock

import tailcache12_pilot_start as start


class PilotStartTest(unittest.TestCase):
    def test_failed_quiet_or_changed_source_never_launches_pilot(self):
        for quiet_pass in (False,True):
            with self.subTest(quiet_pass=quiet_pass),tempfile.TemporaryDirectory() as directory:
                with patch.object(start.evidence,'REPORTS',pathlib.Path(directory)), \
                     patch.object(start.evidence,'source_hash',side_effect=['source','changed']), \
                     patch.object(start,'qualification_bindings'),patch.object(start.pilot,'qualification_refs',return_value=({},dict(conditioning=8),{})), \
                     patch.object(start,'prepare_file_cache'), \
                     patch.object(start,'run_preflight',return_value={'quietPass':quiet_pass}), \
                     patch.object(start.subprocess,'run') as launch, \
                     patch.object(start.sys,'argv',['pilot-start','pilot','quiet','--qualification-prefix','qualified','--calibration','calibrated']):
                    with self.assertRaises(ValueError): start.main()
                    launch.assert_not_called()

    def test_preparation_is_retained_before_immediate_child_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            events=[]
            with patch.object(start.evidence,'REPORTS',pathlib.Path(directory)), \
                 patch.object(start.evidence,'source_hash',return_value='source'), \
                 patch.object(start,'qualification_bindings'),patch.object(start.pilot,'qualification_refs',return_value=({},dict(conditioning=8),{})), \
                 patch.object(start,'prepare_file_cache',return_value={'preparationPass':True}), \
                 patch.object(start,'run_preflight',side_effect=lambda *_:events.append('quiet') or {'quietPass':True}), \
                 patch.object(start.evidence,'save',side_effect=lambda *_:events.append('retain')), \
                 patch.object(start.subprocess,'run',side_effect=lambda *a,**k:events.append('launch') or Mock(returncode=0)) as launch, \
                 patch.object(start.sys,'argv',['pilot-start','pilot','quiet','--qualification-prefix','qualified','--calibration','calibrated']):
                self.assertEqual(0,start.main())
            self.assertEqual(['quiet','retain','launch'],events)
            self.assertIn('--initial-quiet',launch.call_args.args[0])


if __name__=='__main__': unittest.main()
