#!/usr/bin/env python3
"""Host-only source-to-paper reconciliation. No collector imports or workload runs."""
import argparse
import csv
import hashlib
import json
import pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition,message):
    if not condition:raise ValueError(message)


def run(out):
    package=json.loads((out/'paper-data.json').read_text())
    verified={}
    for name,entry in package['provenance'].items():
        path=ROOT/entry['path']
        check(digest(path)==entry['sha256'],f'Original input changed: {path}')
        verified[name]=entry['sha256']
    source={name:json.loads((ROOT/package['provenance'][name]['path']).read_text()) for name in ('focused','midpoint')}
    expected={(name,r['batch'],r['label']):r for name,d in source.items() for r in d['observations']}
    observed={(r['dataset'],r['batch'],r['label']):r for r in package['observations']}
    check(len(observed)==len(package['observations'])==len(expected)==162 and set(observed)==set(expected),
          'Source/export observation coverage differs')
    fields=0
    for identity,row in observed.items():
        original=expected[identity]
        for key,value in row.items():
            if key=='dataset':continue
            fallback={'reuse':False,'seed':24301,'cohort':'historical'}
            check(value==original.get(key,fallback.get(key)),f'Source/export field differs: {identity}/{key}')
            fields+=1
    tails=json.loads((ROOT/package['provenance']['tails']['path']).read_text())
    expected_curves={(r['batch'],r['label']):r['channels']['response'] for r in tails['forks']
                     if observed[('midpoint',r['batch'],r['label'])]['cohort']=='primary'}
    actual_curves={(r['batch'],r['label']):r['response'] for r in package['curves']}
    check(len(actual_curves)==len(package['curves'])==18 and actual_curves==expected_curves,
          'Source/export full response distributions differ')
    accepted=json.loads((ROOT/package['provenance']['original']['path']).read_text())
    dataset=ROOT/accepted['datasetDirectory']
    for key in ('acceptance','deliveryManifest','researcherReview'):
        entry=accepted[key];check(digest(ROOT/entry['path'])==entry['sha256'],f'Original acceptance reference changed: {key}')
    audit_path=dataset/accepted['independentAudit']['path']
    check(digest(audit_path)==accepted['independentAudit']['sha256'],'Original independent audit changed')
    old_audit=json.loads(audit_path.read_text())
    check(old_audit['passed'] and not old_audit['unconditionalProtocolQualified'], 'Original audit scope changed')
    summary_path=dataset/'independent-review-002/comparison-summary.csv'
    summary=list(csv.DictReader(summary_path.open()))
    check(len(summary)==16,'Original comparison coverage differs')
    original_summary=dict(outcome=accepted['outcome'],campaignConditionallyUsable=accepted['campaignConditionallyUsable'],
                          campaignHardRejected=accepted['campaignHardRejected'],
                          originalPrimaryProtocolQualified=accepted['originalPrimaryProtocolQualified'],
                          comparisonSource=str(summary_path.relative_to(ROOT)),comparisonSourceSha256=digest(summary_path),
                          comparisons=summary,independentAuditSha256=digest(audit_path))
    (out/'original-campaign-summary.json').write_text(json.dumps(original_summary,indent=2)+'\n')
    lines=['# Original campaign: conditional results and exclusions', '',
           'These are the original audit’s point ratios and direction classifications. They are not fresh paired ratios, and an unresolved endpoint must not be classified from its point estimate alone. The original unconditional protocol remains NO_GO. Full condition limitations are retained in [the JSON](original-campaign-summary.json).', '',
           '| Recorder | Payload (B) | Ballast (MiB) | Complete comparison | No conditional quality limitation | p99 Ch/C | p99.9 Ch/C | p99 direction | p99.9 direction |',
           '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in summary:
        ratios=[f'{float(r[k]):.3f}' if r[k] else 'missing' for k in ('p99Ratio','p999Ratio')]
        lines.append('| '+' | '.join([r['channel'],r['payloadBytes'],r['liveMiB'],r['complete'],r['resolvedConditionalClaimAllowed'],*ratios,r['p99Direction'],r['p999Direction']])+' |')
    (out/'ORIGINAL_CAMPAIGN.md').write_text('\n'.join(lines)+'\n')
    result=dict(schema='tailcache-paper-source-audit-20261115',passed=True,newBenchmarkRuns=0,
                paperDataSha256=digest(out/'paper-data.json'),originalInputHashes=verified,
                observationsMatched=len(observed),topLevelObservationFieldsMatched=fields,
                completeResponseDistributionsMatched=len(actual_curves),
                originalCampaignComparisons=len(summary),originalCampaignAcceptanceReferencesVerified=4,
                originalRawLogsReaudited=False,
                limits='Exact source-to-export reconciliation; does not repeat prior full raw-GC/runtime/archive audits.')
    (out/'source-audit-20261115.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=pathlib.Path,default=ROOT/'docs/preprint')
    run(parser.parse_args().out)
