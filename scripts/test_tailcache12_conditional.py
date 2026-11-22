import copy
import csv
import json
import pathlib
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import tailcache12_conditional as study


class ConditionalStudyTest(unittest.TestCase):
    def rows(self,stage):
        rows=[]
        for label,p in study.grid(stage):
            factor=(.8 if p['Channel']=='sample-calibration' else 1.2) if p['Backend']=='CHRONICLE_IN_MEMORY' else 1
            fraction=(.30 if p['Backend']=='CAFFEINE' and p['Payload']==4096 else .08)+p['LiveBytes']/1024**2/512
            rows.append(dict(label=label,inputs=p,finalPolicyUsable=True,warnings=[],fatalReasons=[],strictReasons=[],
                servicePercentilesNs={'50':20,'99':100*factor,'99.9':200*factor},postGcUsedHeapMedianFraction=fraction))
        return rows

    def floors(self):
        return [dict(label=k,inputs=p,finalPolicyUsable=True,warnings=[],servicePercentilesNs={'50':5}) for k,p in study.grid('floors')]

    def bootstrap(self,blocks,**kwargs):
        ratio=blocks[0][0][1]/blocks[0][0][0]
        return dict(ratio=ratio,lower=ratio*.99,upper=ratio*1.01,lower95=ratio*.99,upper95=ratio*1.01)

    def test_all_stages_have_complete_distinct_schedules_and_primary_replication(self):
        self.assertEqual(sum(study.COUNTS.values()),402)
        for stage in study.STAGES:
            slots=study.grid(stage);self.assertEqual(len(slots),study.COUNTS[stage]);self.assertEqual(len(slots),len({k for k,p in slots}))
        main=study.grid('campaign');self.assertEqual(len(main),192)
        keys={tuple(p[k] for k in ('Backend','Payload','LiveBytes','Channel')) for label,p in main}
        self.assertEqual(len(keys),32)
        for key in keys:
            chosen=[p for label,p in main if tuple(p[k] for k in ('Backend','Payload','LiveBytes','Channel'))==key]
            self.assertEqual({(p['Block'],p['ForkOrdinal']) for p in chosen},{(b,f) for b in (1,2) for f in (1,2,3)})
        self.assertTrue(all(p['Warmups']==30 and p['Conditioning']==8 and p['Measurements']==8 for k,p in main))
        robust=study.grid('robustness');self.assertEqual({p['Seed'] for k,p in robust},set(study.RULES['robustnessSeeds']))
        self.assertTrue(all(p['Seed']!=24301 and p['Block']==1 for k,p in robust))
        self.assertTrue(all(p['Channel']=='compiler' for k,p in study.grid('compiler-diagnostic')))
        first=[(p['Payload'],p['LiveBytes']) for k,p in main if p['Block']==1 and p['Channel']=='sample-calibration' and p['ForkOrdinal']==1 and p['Backend']=='CAFFEINE']
        second=[(p['Payload'],p['LiveBytes']) for k,p in main if p['Block']==2 and p['Channel']=='sample-calibration' and p['ForkOrdinal']==1 and p['Backend']=='CAFFEINE']
        self.assertEqual(second,list(reversed(first)))

    def test_qualification_compiler_failure_remains_visible_without_aborting_collection(self):
        raw=dict(strictReasons=['compiler total exceeds 80 ms'],warnings=['compiler total exceeds 80 ms'],fatalReasons=[])
        qualified=study.apply_policy(raw,'qualification')
        self.assertTrue(qualified['finalPolicyUsable']);self.assertFalse(qualified['qualificationCompilerPass'])
        self.assertFalse(qualified['conditionalEndpointUseAllowed'])
        self.assertEqual(qualified['qualificationCompilerReasons'],raw['strictReasons'])
        self.assertTrue(study.apply_policy(raw,'campaign')['finalPolicyUsable'])
        self.assertEqual(raw['fatalReasons'],[])
        raw['fatalReasons']=['missing workload integrity evidence']
        self.assertFalse(study.apply_policy(raw,'campaign')['finalPolicyUsable'])
        self.assertFalse(study.apply_policy(raw,'qualification')['finalPolicyUsable'])

    def test_statistics_are_regime_conditional_and_warning_or_variance_prevents_resolved_claim(self):
        rows=self.rows('campaign');bands=study.pressure_bands(self.rows('calibration'));floors=self.floors()
        with patch.object(study.legacy_analysis,'hierarchical_ratio',side_effect=self.bootstrap):
            result=study.analyse_campaign(rows,bands,floors,self.rows('qualification'))
            self.assertEqual(len(result['comparisons']),16);self.assertEqual(len(result['channelDisagreements']),16)
            self.assertEqual(len(result['floorRatios']),48)
            self.assertTrue(all(c['resolvedConditionalClaimAllowed'] for c in result['comparisons']))
            self.assertTrue(all(v['forks']==6 for c in result['comparisons'] for b in c['runVariation'].values() for v in b.values()))
            rows[0]['warnings']=['Native CPU outside benchmark scope exceeded 10% upper bound']
            result=study.analyse_campaign(rows,bands,floors,self.rows('qualification'))
            affected=[c for c in result['comparisons'] if not c['resolvedConditionalClaimAllowed']]
            self.assertEqual(len(affected),1)
            self.assertTrue(all(r['direction']=='unresolved' and r['rawBootstrapDirection']!='unresolved' for r in affected[0]['ratios'].values()))
            floors[0]['warnings']=['compiler iteration exceeds 10 ms']
            self.assertTrue(any('floor' in issue for c in study.analyse_campaign(rows,bands,floors,self.rows('qualification'))['comparisons'] for issue in c['claimLimitations']))
            with self.assertRaises(ValueError):study.analyse_campaign(rows,bands,floors[1:],self.rows('qualification'))

    def test_qualification_requires_both_passes_and_propagates_failure_to_all_matching_pressures_and_seeds(self):
        qualification=self.rows('qualification');row=qualification[0]
        row['strictReasons']=['compiler iteration exceeds 10 ms'];row['warnings']=list(row['strictReasons'])
        evidence=study.qualification_evidence(qualification)
        affected=[r for r in evidence if not r['conditionalQualified']]
        self.assertEqual(len(affected),1);self.assertFalse(affected[0]['compilerQualified'])
        self.assertTrue(affected[0]['complete']);self.assertEqual(affected[0]['originalCompilerIntervalCeilingMs'],10)
        with patch.object(study.legacy_analysis,'hierarchical_ratio',side_effect=self.bootstrap):
            result=study.analyse_campaign(self.rows('campaign'),study.pressure_bands(self.rows('calibration')),self.floors(),qualification)
        rejected=[c for c in result['comparisons'] if not c['resolvedConditionalClaimAllowed']]
        self.assertEqual(len(rejected),4)
        self.assertEqual({c['applicationLiveBytes']//1024**2 for c in rejected},set(study.RULES['liveMiB']))
        self.assertTrue(all(c['payloadBytes']==row['inputs']['Payload'] and c['channel']=='sample' for c in rejected))
        self.assertTrue(all(any('qualification' in issue for issue in c['claimLimitations']) for c in rejected))
        robust=study.robustness_summary(self.rows('robustness'),qualification)
        self.assertEqual(sum(not r['conditionalSensitivityUsable'] for r in robust),8)
        missing=study.qualification_evidence(qualification[1:])
        self.assertTrue(any(not r['complete'] and not r['compilerQualified'] for r in missing))
        duplicate=study.qualification_evidence([qualification[0],qualification[0]]+qualification[2:])
        self.assertTrue(any(not r['complete'] for r in duplicate))

    def test_pressure_exposure_and_replica_failures_are_explicit_not_hidden(self):
        rows=self.rows('calibration');good=study.pressure_bands(rows)
        self.assertFalse(any(b['warnings'] for b in good))
        row=rows[0];row['postGcUsedHeapMedianFraction']=None
        self.assertTrue(any(b['warnings'] for b in study.pressure_bands(rows)))
        self.assertTrue(any(b['warnings'] for b in study.pressure_bands(rows[:-1])))

    def test_robustness_is_separate_and_incomplete_cells_are_rejected(self):
        rows=self.rows('robustness');summary=study.robustness_summary(rows,self.rows('qualification'))
        self.assertEqual(len(summary),32);self.assertEqual({x['seed'] for x in summary},set(study.RULES['robustnessSeeds']))
        self.assertTrue(all(x['confidenceInterval'] is None for x in summary))
        with self.assertRaises(ValueError):study.robustness_summary(rows[:-1],self.rows('qualification'))

    def test_pilot_uses_two_independent_passes_without_forging_confidence(self):
        rows=self.rows('pilot');result=study.pilot_variation(rows)
        self.assertEqual(len(result),16);self.assertTrue(all(r['confidenceInterval'] is None and not r['warnings'] for r in result))
        rows[0]['servicePercentilesNs']['99.9']*=4
        self.assertTrue(any(r['warnings'] for r in study.pilot_variation(rows)))
        with self.assertRaises(ValueError):study.pilot_variation(rows[:-1])

    def test_allocation_uses_actual_measured_windows_and_complete_thread_counters(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=pathlib.Path(tmp);worker=raw/'every-operation/worker';worker.mkdir(parents=True)
            rows=[dict(phase='MEASUREMENT',operations=n,startNs=i*10**9,endNs=(i+1)*10**9,
                workerJvmAllocatedBytes=n*10,churnJvmAllocatedBytes=n*5) for i,n in enumerate((4,6))]
            with (worker/'iterations.csv').open('w',newline='') as f:
                writer=csv.DictWriter(f,list(rows[0]));writer.writeheader();writer.writerows(rows)
            summary=study.allocation_summary(raw,'every-operation')
            self.assertEqual(summary['workerBytesPerOperation'],10);self.assertEqual(summary['totalObservedBytesPerOperation'],15)
            self.assertEqual(summary['totalObservedBytesPerSecond'],75)

    def test_original_protocol_acceptance_is_not_forged_by_conditional_success(self):
        comps=[dict(payloadBytes=p,applicationLiveBytes=live*1024**2,channel=c,resolvedConditionalClaimAllowed=True,claimLimitations=[])
            for p in (256,4096) for live in study.RULES['liveMiB'] for c in ('sample','every-operation')]
        rows=study.condition_acceptance(comps);self.assertEqual(len(rows),16)
        self.assertTrue(all(not r['originalUnconditionalProtocolAccepted'] and r['originalRejectionReasons'] for r in rows))
        self.assertTrue(all(all(c['accepted'] for c in r['conditionalRegimes'].values()) for r in rows))

    def test_partial_export_is_refused_before_creating_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);out=root/'dataset'
            for results in ({},{s:dict(complete=s!='robustness') for s in study.STAGES}):
                with self.assertRaises(ValueError):study.export(root,results,out)
                self.assertFalse(out.exists())

    def test_master_protocol_and_source_mutation_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);(root/'source.tar.gz').write_bytes(b'source archive')
            manifest=dict(sourceSha256='source',sourceArchiveSha256=study.evidence.file_sha(root/'source.tar.gz'))
            (root/'manifest.json').write_text(json.dumps(manifest))
            protocol=dict(declaration=study.declaration(),sourceSha256='source',measurementSourceSha256='measurement')
            (root/'protocol.json').write_text(json.dumps(protocol));state=dict(protocolSha256=study.evidence.file_sha(root/'protocol.json'))
            with patch.object(study,'archive_measurement_source_hash',return_value='measurement'):
                study.verify_master(root,state,'source')
                bad=copy.deepcopy(protocol);bad['declaration']['rules']['replacements']=1
                (root/'protocol.json').write_text(json.dumps(bad))
                with self.assertRaises(ValueError):study.verify_master(root,state,'source')
                state['protocolSha256']=study.evidence.file_sha(root/'protocol.json')
                with self.assertRaises(ValueError):study.verify_master(root,state,'source')
                (root/'protocol.json').write_text(json.dumps(protocol));state['protocolSha256']=study.evidence.file_sha(root/'protocol.json')
                (root/'source.tar.gz').write_bytes(b'changed archive')
                with self.assertRaises(ValueError):study.verify_master(root,state,'source')

    def test_prerequisite_hash_and_actual_completeness_are_both_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);path=root/'prior-pause';path.mkdir();(path/'source.tar.gz').write_bytes(b'archive')
            (path/'manifest.json').write_text(json.dumps(dict(sourceSha256='source',invocations=[{},{}])))
            result=dict(schemaVersion=study.VERSION,stage='pause',complete=True,sourceSha256='source',collectedInvocations=2,expectedInvocations=2)
            (path/'conditional-review.json').write_text(json.dumps(result));ref=study.reference(path)
            with patch.object(study.calibration,'verify_invocation'):
                study.verify_refs(root,{'pause':ref})
                result['complete']=False;(path/'conditional-review.json').write_text(json.dumps(result))
                with self.assertRaises(ValueError):study.verify_refs(root,{'pause':ref})
                with self.assertRaises(ValueError):study.verify_refs(root,{'pause':study.reference(path)})

    def test_archive_is_readback_verified_and_never_overwrites_or_follows_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);reports=root/'build/reports/tailcache12';reports.mkdir(parents=True)
            a=reports/'a';b=reports/'b';a.write_bytes(b'raw');b.write_bytes(b'source');archive=root/'evidence.tar.gz'
            with patch.object(study.evidence,'ROOT',root),patch.object(study.evidence,'REPORTS',reports):
                inventory,receipt=study.archive_files({a,b},archive)
                self.assertEqual(receipt['verifiedMembers'],2);self.assertEqual(len(inventory),2)
                with self.assertRaises(FileExistsError):study.archive_files({a,b},archive)
                alias=reports/'alias';alias.symlink_to(a)
                with self.assertRaises(ValueError):study.archive_files({alias},root/'rejected.tar.gz')
            self.assertEqual(a.read_bytes(),b'raw');self.assertEqual(b.read_bytes(),b'source')


if __name__=='__main__':unittest.main()
