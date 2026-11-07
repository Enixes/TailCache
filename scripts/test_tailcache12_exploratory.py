import copy
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import tailcache12_exploratory as explore


class ExploratoryTest(unittest.TestCase):
    def rows(self):
        return [dict(label=label,inputs=p,exploratoryUsable=True,warnings=[],
            servicePercentilesNs={'50':100,'99':200,'99.9':300}) for label,p in explore.schedule()]

    def test_fixed_full_matrix_and_independent_floors_with_reduced_replicas(self):
        slots=explore.schedule();self.assertEqual(len(slots),42);self.assertEqual(len(set(k for k,p in slots)),42)
        work=[p for k,p in slots if k.startswith('work-')];self.assertEqual(len(work),32)
        cells={(p['Backend'],p['Payload'],p['LiveBytes'],p['Channel']) for p in work};self.assertEqual(len(cells),32)
        for p in work:
            self.assertEqual(p['Warmups'],30);self.assertEqual(p['Conditioning'],8);self.assertEqual(p['Measurements'],8)
            self.assertEqual(p['Residents'],32768);self.assertEqual(p['HeapMiB'],512)
            self.assertNotIn('DenseObserver',p);self.assertNotIn('FlightRecorder',p)
        self.assertEqual(sum(p['Channel']=='floor' for k,p in slots),8)
        self.assertEqual(sum(p['Channel']=='timer' for k,p in slots),2)
        self.assertFalse(explore.POLICY['primaryEndpointUseAllowed']);self.assertEqual(explore.POLICY['replacements'],0)

    def test_only_predeclared_warnings_are_lenient_and_cpu_ceiling_is_hard(self):
        for reason in explore.WARNINGS:self.assertEqual(explore.classify([reason],25),([reason],[]))
        for reason in ('missing or invalid compiler-time evidence','churn demand was dropped',
                'JVM allocation does not corroborate churn','missing workload integrity evidence',
                'swap-in/out counters increased','Native thermal-throttle counter increased','unknown future failure'):
            self.assertEqual(explore.classify([reason],0),([],[reason]))
        self.assertTrue(explore.classify([],25.000001)[1])
        for value in (float('nan'),float('inf'),-1):
            with self.assertRaises(ValueError):explore.classify([],value)

    def test_descriptive_disagreement_and_floor_warning_do_not_forge_uncertainty(self):
        rows=self.rows()
        for row in rows:
            if row['inputs']['Backend']=='CHRONICLE_IN_MEMORY' and row['label'].startswith('work-'):
                factor=2 if row['inputs']['Channel']=='sample-calibration' else .5
                row['servicePercentilesNs']={'50':100,'99':200*factor,'99.9':300*factor}
        result=explore.describe(rows)
        self.assertEqual(len(result['comparisons']),16);self.assertEqual(len(result['channelDisagreements']),16)
        self.assertTrue(all(r['warning'] for r in result['floorRatios']))
        self.assertIsNone(result['confidenceIntervals']);self.assertIsNone(result['runToRunVariance'])
        self.assertTrue(all(c['confidenceInterval'] is None for c in result['comparisons']))
        self.assertFalse(result['robustnessCollected'])
        bad=next(r for r in rows if r['label'].startswith('work-'));bad['exploratoryUsable']=False
        self.assertEqual(len(explore.describe(rows)['comparisons']),15)

    def test_partial_or_hard_rejected_export_cannot_create_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            out=pathlib.Path(directory)/'dataset'
            with self.assertRaises(ValueError):explore.export(pathlib.Path(directory),dict(exploratoryComplete=False),out)
            self.assertFalse(out.exists())
            with self.assertRaises(ValueError):explore.export(pathlib.Path(directory),dict(exploratoryComplete=True,observations=[]),out)
            self.assertFalse(out.exists())

    def declaration(self,root):
        slots=explore.schedule();protocol=dict(policy=explore.POLICY,schedule=[dict(label=k,properties=p) for k,p in slots],
            sourceSha256='source',measurementSourceSha256='measurement',hdrVerifier={})
        (root/'protocol.json').write_text(json.dumps(protocol));(root/'source.tar.gz').write_bytes(b'archive')
        manifest=dict(schemaVersion=explore.VERSION,stage='exploratory-e2e',primaryEndpointUseAllowed=False,reportable=False,
            expectedBlocks=[k for k,p in slots],protocolSha256=explore.evidence.file_sha(root/'protocol.json'),
            sourceArchiveSha256=explore.evidence.file_sha(root/'source.tar.gz'),sourceSha256='source',
            measurementSourceSha256='measurement',hdrVerifier={},initialMemoryReadinessRule=explore.AVAILABLE_MEMORY_RULE,
            invocations=[dict(label=k,properties=p) for k,p in slots])
        return protocol,manifest

    def test_frozen_schedule_policy_sources_and_primary_exclusion_are_not_optional(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);protocol,manifest=self.declaration(root)
            with patch.object(explore,'archive_measurement_source_hash',return_value='measurement'):
                explore.verify_declaration(root,manifest)
                for mutation in ('order','input','duplicate','primary','source','policy'):
                    bad=copy.deepcopy(manifest)
                    if mutation=='order':bad['invocations'].reverse()
                    elif mutation=='input':bad['invocations'][0]['properties']['Warmups']=1
                    elif mutation=='duplicate':bad['invocations'].append(bad['invocations'][0])
                    elif mutation=='primary':bad['primaryEndpointUseAllowed']=True
                    elif mutation=='source':bad['sourceArchiveSha256']='wrong'
                    else:
                        changed=copy.deepcopy(protocol);changed['policy']['outsideCpuUpperCeilingPercent']=100
                        (root/'protocol.json').write_text(json.dumps(changed));bad['protocolSha256']=explore.evidence.file_sha(root/'protocol.json')
                    with self.assertRaises(ValueError):explore.verify_declaration(root,bad)
                    (root/'protocol.json').write_text(json.dumps(protocol))

    def test_structural_validator_failure_never_becomes_exploratory_warning(self):
        with patch.object(explore.calibration,'verify_invocation',side_effect=ValueError('Changed raw artifact')):
            with self.assertRaisesRegex(ValueError,'Changed raw artifact'):
                explore.audit_row(pathlib.Path('/unused'),{},dict(properties={'Channel':'sample-calibration'}),None,None)


if __name__=='__main__':unittest.main()
