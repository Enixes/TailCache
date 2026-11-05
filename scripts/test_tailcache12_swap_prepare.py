import copy
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch,Mock

import tailcache12_swap_prepare as swap


class SwapPreparationTest(unittest.TestCase):
    def state(self,used=20432):
        return dict(memory=dict(MemAvailableKiB=6*1024**2,SwapUsedKiB=used),
            devices=[dict(name='/dev/zram0',type='partition',sizeKiB=5968892,usedKiB=used,priority=100),
                     dict(name='/dev/sda3',type='partition',sizeKiB=9227464,usedKiB=0,priority=-1)],
            unitProperties='configured-active-units',zramSettings={'comp_algorithm':'[zstd]'},
            swappiness='60',zswapEnabled='Y')

    def test_only_configured_zram_is_restarted_and_final_policy_and_empty_swap_are_verified(self):
        before=self.state(); after=self.state(0); after['devices'].reverse()
        with tempfile.TemporaryDirectory() as directory:
            report=pathlib.Path(directory)/'reset.json'
            with patch.object(swap,'snapshot',side_effect=[before,after,after]), \
                 patch.object(swap.evidence,'source_hash',return_value='source'), \
                 patch.object(swap,'measurement_source_hash',return_value='measurement'), \
                 patch.object(swap.subprocess,'run',return_value=Mock(returncode=0,stdout='ok',stderr='')) as run:
                result=swap.reset(report)
            self.assertTrue(result['preparationPass']); self.assertTrue(result['configurationRestored'])
            self.assertEqual(['sudo','-n','systemctl','restart','dev-zram0.swap'],run.call_args.args[0])
            self.assertTrue(json.loads(report.read_text())['preparationPass'])

    def test_insufficient_memory_disk_swap_or_large_residual_prevents_admin_action(self):
        cases=[]
        low=self.state(); low['memory']['MemAvailableKiB']=1024; cases.append(low)
        disk=self.state(); disk['devices'][1]['usedKiB']=1; cases.append(disk)
        cases.append(self.state(300*1024))
        for state in cases:
            with tempfile.TemporaryDirectory() as directory,patch.object(swap,'snapshot',return_value=state), \
                 patch.object(swap.subprocess,'run') as run:
                with self.assertRaises(ValueError): swap.reset(pathlib.Path(directory)/'reset.json')
                run.assert_not_called()

    def test_admin_failure_or_changed_final_policy_is_retained_and_never_passes(self):
        for exit_code in (0,1):
            before=self.state(); after=self.state(0 if exit_code==0 else 20432)
            if exit_code==0: after['devices'][0]['priority']=0
            with tempfile.TemporaryDirectory() as directory,patch.object(swap,'snapshot',side_effect=[before,after,after]), \
                 patch.object(swap.evidence,'source_hash',return_value='source'), \
                 patch.object(swap,'measurement_source_hash',return_value='measurement'), \
                 patch.object(swap.subprocess,'run',return_value=Mock(returncode=exit_code,stdout='',stderr='authentication required')):
                result=swap.reset(pathlib.Path(directory)/'reset.json')
                self.assertFalse(result['preparationPass'])

    def test_interrupted_restart_attempts_restoration_and_still_requires_review(self):
        before=self.state(); missing=self.state(0); missing['devices']=missing['devices'][1:]
        after=self.state(0)
        with tempfile.TemporaryDirectory() as directory,patch.object(swap,'snapshot',side_effect=[before,missing,after]), \
             patch.object(swap.evidence,'source_hash',return_value='source'), \
             patch.object(swap,'measurement_source_hash',return_value='measurement'), \
             patch.object(swap.subprocess,'run',side_effect=[subprocess.TimeoutExpired('restart',60),Mock(returncode=0,stdout='restored',stderr='')]) as run:
            result=swap.reset(pathlib.Path(directory)/'reset.json')
            self.assertTrue(result['configurationRestored']); self.assertFalse(result['preparationPass'])
            self.assertEqual(['sudo','-n','systemctl','start','dev-zram0.swap'],run.call_args.args[0])


if __name__=='__main__': unittest.main()
