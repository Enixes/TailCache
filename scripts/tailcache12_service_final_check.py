#!/usr/bin/env python3
"""Read-only final live-runtime/input and selected-claim reconciliation."""
from pathlib import Path
import json,hashlib,collections,datetime
R=Path(__file__).resolve().parents[1];B=R/'docs/service-followup'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
d=json.loads((B/'followup-data-20261117.json').read_text());runtime=set();archived=0;mechanism=0
for name,i in d['cohortInputs'].items():
 p=R/'evidence-archives'/i['attempt'];protocol=json.loads((p/'protocol.json').read_text());a=json.loads((p/'independent-audit-001/audit.json').read_text())
 assert a['passed'] and sha(p/'study.json')==i['studySha256'] and sha(p/'protocol.json')==i['protocolSha256']
 assert sha(p/'source.tar.gz')==i['sourceArchiveSha256']==a['sourceArchiveSha256']
 assert sha(p/'independent-audit-001/audit.json')==i['auditSha256']
 for f,h in protocol['runtimeSha256'].items():assert sha(Path(f))==h;runtime.add(f)
 archived+=1
 if name!='observer':
  m=p/'mechanism-audit-001/report.json';assert sha(m)==i['mechanismAuditSha256'];assert json.loads(m.read_text())['passed'];mechanism+=1
assert sha(R/'docs/preprint/paper-data.json')=='a733eee906a863be68e7fd09ef9e6d3b51cf148ae69f5401c4a0706912ea50b7'
def points(c,stage=None):return [p for p in d['points'] if p['cohort']==c and (stage is None or p['stage']==stage)]
def ratios(p,ch='service'):return p['conclusions'][ch]['99.9']['ratios']
primary=points('replication','payload-confirmation')
assert len(primary)==8 and all(p['conclusions']['service']['99']['direction']=='Caffeine lower' for p in primary)
assert all(all(v<1 for v in ratios(p)) for p in primary if p['payload']==512)
assert all(all(v>1 for v in ratios(p)) for p in primary if p['payload']==4096)
assert all(all(v<1 for v in ratios(p,'response')) for p in points('paced'))
for p in points('geometry'):
 assert all(v>1 for v in ratios(p,'response')) if p['stage']=='geometry-repeated-short' else all(v<1 for v in ratios(p,'response'))
negative=json.loads((R/'evidence-archives/service-large-payload-pilot-20261117-001/worth-decision.json').read_text());assert negative['kind']=='none'
warnings=collections.Counter(w for r in d['forks'] for w in r['warnings'])
out=dict(passed=True,verifiedUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),packageSha256=sha(B/'followup-data-20261117.json'),cohortStudyProtocolSourceAuditBindings=archived,mechanismAuditBindings=mechanism,uniqueLiveRuntimeFilesVerified=len(runtime),originalPaperDataUnchanged=True,primaryServiceP99AllCaffeineLower=True,pacedResponseP999AllChronicleLower=True,geometryResponseDirectionsOpposite=True,largerPayloadDecision='none',warningBearingForks=sum(bool(r['warnings']) for r in d['forks']),warningInstances=dict(warnings),limits='Final input/runtime and selected claim reconciliation; prior raw histogram/event audits remain separately bound, not all re-executed in this pass.')
(B/'final-evidence-check-20261117.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
