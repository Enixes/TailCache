#!/usr/bin/env python3
"""Fixed secondary12, plus one separately instrumented compiler diagnostic."""
import argparse,json,pathlib,random,subprocess,sys
import tailcache12_predictor_campaign as c
import tailcache12_predictor_sequence as sequence
import tailcache12_focused as f
ROOT=c.ROOT
OLD=c.core.source_files
def sources():return sorted(set(OLD()+[ROOT/'docs/TAILCACHE_PREDICTOR_CONFIRMATION_PROTOCOL.md',ROOT/'docs/predictor/DRAIN_CANDIDATE.md',ROOT/'docs/predictor/drain-candidate-v1.json',ROOT/'docs/predictor/drain_candidate.py.txt',ROOT/'docs/predictor/numeric-baseline-v1.json',ROOT/'docs/predictor/compiler-only.jfc']))
c.core.source_files=sources

def schedule():
    cells=[(w,b) for w in (0,50,500) for b in (1,2)];random.Random(44820).shuffle(cells);rows=[]
    for i,(w,b) in enumerate(cells):
        pair=c.core.pair_specs('drain-confirm-w'+str(w),4096,0,block=b,seed=44810+b,reverse=bool((i+b)%2))
        for r in pair:r.update(writeBps=w,regime='arrival',qps=50000,warmupMs=120000,conditioningMs=4000,measureMs=30000)
        rows+=pair
    return rows

def design(kind,maxjvms,slots,controls):
    base=ROOT/'build/predictor-20261118'
    inputs=[base/'compilation.json',base/'functional-validation.json',base/'runner-smoke-receipt.json',base/'timed-loop-review.json',
            ROOT/'docs/predictor/model-v1.json',ROOT/'docs/predictor/drain-candidate-v1.json',ROOT/'docs/predictor/numeric-baseline-v1.json',
            ROOT/'evidence-archives/predictor-validation-20261118-001/study.json',ROOT/'evidence-archives/predictor-validation-20261118-001/score-v1.json',ROOT/'evidence-archives/predictor-validation-20261118-001/drain-score-v1.json']
    return dict(kind=kind,maxWorkloadJvms=maxjvms,controls=controls,functionalValidationJvms=0,functionalReceiptReused=True,
        functionalValidationReceipt='build/predictor-20261118/functional-validation.json',warmupMs=120000,conditioningMs=4000,measureMs=30000,
        perSlotTiming=True,primaryEndpoint='Frozen M2 response-p99.9 numerical accuracy; updated replication forecast separate',
        protocol='docs/TAILCACHE_PREDICTOR_CONFIRMATION_PROTOCOL.md',discoveryInputs={str(p.relative_to(ROOT)):f.sha(p) for p in inputs},schedule=slots,
        inheritedTransientQualification=True,updatedReplicationForecast={'0':'Caffeine lower','50':'Chronicle lower','500':'Chronicle lower'})

def diagnostic(attempt):
    out=ROOT/'evidence-archives'/attempt
    if (out/'diagnostic-complete.json').exists():
        r=f.load(out/'diagnostic-complete.json')
        for name,h in r['inputs'].items():c.core.check(f.sha(out/name)==h,'Retained diagnostic changed')
        return
    d=design('compiler-diagnostic',0,[],1);camp=c.Campaign(out,design=d,classpath_file=ROOT/'build/predictor-20261118/classpath.txt')
    row=c.core.pair_specs('compiler-diagnostic-w200',4096,0,seed=44801)[0]
    row.update(writeBps=200,regime='arrival',qps=50000,warmupMs=120000,conditioningMs=4000,measureMs=30000)
    directory=out/'controls'/row['label'];saved=f.FLAGS
    try:
        f.FLAGS=[*saved,f'-Xlog:jit+compilation=debug:file={directory}/jit.log:uptimemillis,timenanos,level,tags:filecount=0',
                 f'-XX:StartFlightRecording=filename={directory}/compiler.jfr,settings={ROOT}/docs/predictor/compiler-only.jfc,dumponexit=true,maxsize=8m']
        r=camp.execute([row],control=True)[0]
    finally:f.FLAGS=saved
    camp.check_frozen();inputs={str(p.relative_to(out)):f.sha(p) for p in [directory/'service-result.json',directory/'compiler.jfr',directory/'jit.log']}
    c.core.immutable(out/'diagnostic-complete.json',dict(passed=r['status']=='OK',diagnosticJvms=1,researchObservations=0,
        inputContract='Additional compiler-only JFR/JIT instrumentation; no pooling with measured cohorts',inputs=inputs))
    command=['/usr/lib/jvm/java-21-openjdk/bin/jfr','print','--json','--events','jdk.Compilation,jdk.CompilerPhase,jdk.Deoptimization,jdk.JVMInformation',str(directory/'compiler.jfr')]
    target=out/'compiler-events.json'
    if not target.exists():
        with target.open('x') as stream:r=subprocess.run(command,stdout=stream,stderr=subprocess.PIPE,text=True)
        c.core.check(r.returncode==0,'JFR extraction retained; inspect diagnostic')
    print('COMPILER_DIAGNOSTIC_COMPLETE',flush=True)

def collect(attempt):
    out=ROOT/'evidence-archives'/attempt;d=design('drain-confirmation',12,schedule(),0)
    camp=c.Campaign(out,design=d,classpath_file=ROOT/'build/predictor-20261118/classpath.txt')
    camp.execute(d['schedule']);rows=camp.observations();pairs=c.core.pairs(rows);by={r['label']:r for r in rows}
    c.core.check(len(rows)==12 and len(pairs)==6,'Exact fresh12 coverage')
    for p in pairs:
        a,b=[by[p['labels'][k]] for k in c.core.BACKENDS]
        c.core.check([(w['phase'],w['writes']) for w in a['windows']]==[(w['phase'],w['writes']) for w in b['windows']],'Matched logical writes')
        p['ratios']['response']={q:b['latency']['response']['percentilesNs'][q]/a['latency']['response']['percentilesNs'][q] for q in c.core.PERCENTILES}
        p.update(writeBps=a['writeBps'],warmupMs=a['warmupMs'])
    camp.check_frozen();c.core.immutable(out/'study.json',dict(kind='predictor-secondary-validation',observations=rows,pairs=pairs,collectionComplete=True,workloadJvms=12,
        primary='Frozen M2 response-p99.9 numerical error',limits='Fresh secondary holdout; original forecast not revised.'))
    camp.state.update(complete=True,collectionComplete=True,researchComplete=False,completedUtc=f.now());camp.checkpoint()

def main():
    p=argparse.ArgumentParser();p.add_argument('attempt');p.add_argument('--diagnostic',required=True);a=p.parse_args()
    c.qualification();worth=f.load(ROOT/'evidence-archives/predictor-validation-20261118-001/drain-score-v1.json')
    c.core.check(worth['worth']['allowFresh12'],'Frozen worth rule failed')
    s=f.load(c.STATUS);s.update(phase='SECONDARY_CONFIRMATION_RUNNING',running=dict(attempt=a.attempt,diagnostic=a.diagnostic),updatedUtc=f.now());f.save(c.STATUS,s)
    diagnostic(a.diagnostic);collect(a.attempt)
    out=ROOT/'evidence-archives'/a.attempt;steps=out/'postprocess';steps.mkdir(exist_ok=True)
    for name,args,artifact in [
        ('raw',['tailcache12_predictor_audit.py',a.attempt],out/'independent-audit-001/audit.json'),
        ('mechanism',['tailcache12_service_mechanism.py',a.attempt,'--out',str(out/'mechanism-audit-001/report.json')],out/'mechanism-audit-001/report.json'),
        ('predict',['tailcache12_predictor_score.py','predict',a.attempt],out/'predictions-v1.json'),
        ('score',['tailcache12_predictor_score.py','score',a.attempt],out/'score-v1.json'),
        ('drain',['tailcache12_predictor_drain.py',a.attempt],out/'drain-score-v1.json')]:sequence.step(steps,name,args,artifact)
    s=f.load(c.STATUS);s.update(phase='ALL_COLLECTION_COMPLETE_REVIEW_PENDING',running=None,updatedUtc=f.now(),
        secondary=dict(attempt=a.attempt,researchForks=12,rawAuditPassed=True,mechanismAuditPassed=True),compilerDiagnostic=dict(attempt=a.diagnostic,diagnosticJvms=1))
    f.save(c.STATUS,s);print('SECONDARY_PREDICTOR_COMPLETE',flush=True)
if __name__=='__main__':main()
