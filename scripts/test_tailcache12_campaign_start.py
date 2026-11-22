import json
import pathlib
import tempfile
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

import tailcache12_campaign as campaign
import tailcache12_campaign_start as start


class CampaignPreparationTest(unittest.TestCase):
    def test_new_freezes_require_current_preparation_and_bind_raw_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory); quiet=root/'quiet'; quiet.mkdir()
            attempt=root/'campaign'; manifest=dict(stage='campaign')
            for identifier in (None,'../escape'):
                with self.assertRaises(ValueError):
                    campaign.declare_initial_preparation(attempt,manifest,[],{},identifier)
            for cache in ({'version':1},{'version':2,'requiresEmptySwap':False}):
                (quiet/'host-preparation.json').write_text(json.dumps(cache))
                with patch.object(campaign.native_retry,'initialize') as initialize:
                    with self.assertRaises(ValueError):
                        campaign.declare_initial_preparation(attempt,manifest,[],{},'quiet')
                    initialize.assert_not_called()
            (quiet/'host-preparation.json').write_text(json.dumps(dict(version=2,requiresEmptySwap=True)))
            reference={'attempt':'quiet','hostPreparationSha256':'bound'}
            with patch.object(campaign.native_retry,'initial_quiet_reference',return_value=reference), \
                 patch.object(campaign.native_retry,'initialize') as initialize, \
                 patch.object(campaign.native_retry,'verify_initial_quiet') as verify:
                campaign.declare_initial_preparation(attempt,manifest,[],{},'quiet')
                self.assertEqual(reference,manifest['initialQuietRef'])
                self.assertEqual('campaign',initialize.call_args.args[3]['stage'])
                verify.assert_called_once_with(attempt,manifest,before_launch=True)

    def exercise(self,root,*,qualified=True,variance=True,quiet=True,changed=False,freeze_code=0,primary=False):
        events=[]
        argv=['campaign-start','campaign','quiet','--pilot','pilot','--floors','floors','--traces','traces.json']
        if primary: argv+=['--primary','primary']
        def launch(command,**kwargs):
            stage=command[2];events.append(stage)
            if stage=='freeze':
                self.assertEqual('quiet',command[command.index('--initial-quiet')+1])
                if primary: self.assertEqual('primary',command[command.index('--primary')+1])
            return Mock(returncode=freeze_code if stage=='freeze' else 0)
        with ExitStack() as stack:
            for target,attribute,options in (
                (start.evidence,'REPORTS',dict(new=root)),
                (start.evidence,'source_hash',dict(side_effect=['source','changed' if changed else 'source'])),
                (start.observer,'coherence',dict(return_value={'observerQualified':qualified})),
                (start.pilot,'replay',dict(return_value={'provisionalVariancePass':variance})),
                (start.campaign,'replay',dict(side_effect=lambda *_:events.append('primary-review'))),
                (start,'prepare_file_cache',dict(return_value={'preparationPass':True})),
                (start,'run_preflight',dict(side_effect=lambda *_:events.append('quiet') or {'quietPass':quiet})),
                (start.evidence,'save',dict(side_effect=lambda *_:events.append('retain'))),
                (start.subprocess,'run',dict(side_effect=launch)),
                (start.sys,'argv',dict(new=argv)),
            ): stack.enter_context(patch.object(target,attribute,**options))
            try: return start.main(),events
            except ValueError: return 'rejected',events

    def test_prerequisite_quiet_source_and_existing_evidence_fail_before_freeze(self):
        for options in ({'qualified':False},{'variance':False},{'quiet':False},{'changed':True}):
            with self.subTest(options=options),tempfile.TemporaryDirectory() as directory:
                result,events=self.exercise(pathlib.Path(directory),**options)
                self.assertEqual('rejected',result)
                self.assertNotIn('freeze',events);self.assertNotIn('run',events)
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);(root/'quiet').mkdir()
            self.assertEqual(('rejected',[]),self.exercise(root))

    def test_failed_freeze_never_runs_and_success_keeps_same_sequential_controller(self):
        with tempfile.TemporaryDirectory() as directory:
            result,events=self.exercise(pathlib.Path(directory),freeze_code=7)
            self.assertEqual(7,result);self.assertEqual(['quiet','retain','freeze'],events)
        with tempfile.TemporaryDirectory() as directory:
            result,events=self.exercise(pathlib.Path(directory),primary=True)
            self.assertEqual(0,result)
            self.assertEqual(['primary-review','quiet','retain','freeze','run'],events)


if __name__=='__main__': unittest.main()
