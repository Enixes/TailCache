#!/usr/bin/env python3
"""Independent offline bins/HDR/GC/RSS/provenance reconciliation for the service cohort."""
import argparse
import collections
import csv
import hashlib
import importlib.util
import json
import math
import pathlib
import subprocess
import tarfile

ROOT=pathlib.Path(__file__).resolve().parents[1]


def require(value,message):
    if not value:raise ValueError(message)


def load(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def csvrows(path):
    with path.open() as f:return list(csv.DictReader(f))


def same(actual,expected,label):
    require((actual is None and expected is None) or (actual is not None and expected is not None
            and math.isclose(actual,expected,rel_tol=1e-12,abs_tol=1e-6)),label)


def audit(base,out):
    require(__debug__,'Run without -O: prior independent GC parser uses assertions')
    out.mkdir(parents=True,exist_ok=False)
    study=load(base/'study.json');protocol=load(base/'protocol.json');state=load(base/'state.json')
    require(state['complete'] and len(study['observations'])<=protocol['maxWorkloadJvms'],
            'Incomplete collection or budget exceeded')
    # Verify the archived source/runtime, so a later legitimate checkout edit does not
    # make a previously frozen cohort unverifiable. Never execute arbitrary tar paths.
    archived_source={}
    with tarfile.open(base/'source.tar.gz','r:gz') as archive:
        for member in archive:
            require(member.isfile() and member.name in protocol['sourceFiles'] and member.name not in archived_source,
                    'Unexpected/duplicate source archive member')
            with archive.extractfile(member) as stream:data=stream.read()
            require(hashlib.sha256(data).hexdigest()==protocol['sourceFiles'][member.name],'Archived source changed')
            archived_source[member.name]=data
    require(set(archived_source)==set(protocol['sourceFiles']),'Archived source coverage')
    runtime={}
    original_cp=protocol['classpath'].split(':')
    for index,item in enumerate(original_cp):
        original=pathlib.Path(item);destination=base/'runtime'/str(index)
        for file,digest in protocol['runtimeSha256'].items():
            p=pathlib.Path(file)
            if str(p)==item:
                archived=destination/p.name
            elif p.is_relative_to(original):
                archived=destination/p.relative_to(original)
            else:continue
            require(sha(archived)==digest,'Archived runtime changed: '+file);runtime[file]=digest
    require(runtime==protocol['runtimeSha256'],'Archived runtime coverage')
    for file,digest in protocol['preservedPaperInputs'].items():require(sha(ROOT/file)==digest,'Prior paper evidence changed')
    entries=[(r,base/'slots'/r['label']) for r in study['observations']]
    entries += [(load(p),p.parent) for p in sorted((base/'controls').glob('*/service-result.json'))]
    require(len({str(p) for r,p in entries})==len(entries),'Duplicate observation identities')
    counts=collections.Counter();paths=[]
    for row,directory in entries:
        for file,digest in row['rawSha256'].items():
            require(sha(directory/file)==digest,'Raw file changed: '+str(directory/file));counts['rawFiles']+=1
        paths.extend(sorted((directory/'worker').glob('*.hdr')))
    java=pathlib.Path('/usr/lib/jvm/java-21-openjdk/bin')
    cp=':'.join(str(base/p) for p in protocol['archivedClasspath'])
    helper=out/'TailCacheFocusedHdrVerify.java'
    helper.write_bytes(archived_source['scripts/java/TailCacheFocusedHdrVerify.java'])
    subprocess.run([str(java/'javac'),'-cp',cp,'-d',str(out),str(helper)],check=True,capture_output=True)
    decoded=out/'decoded.csv'
    ran=subprocess.run([str(java/'java'),'-Xmx96m','-cp',str(out)+':'+cp,'TailCacheFocusedHdrVerify',str(base),str(decoded)],check=True,capture_output=True,text=True)
    raw={r['path']:r for r in csvrows(decoded)}
    require(set(raw)=={str(p.resolve()) for p in paths},'Available histogram coverage mismatch')
    independent=out/'prior_independent_gc.py'
    independent.write_bytes(archived_source['ops/tailcache12_final_raw_audit.py'])
    spec=importlib.util.spec_from_file_location('independent_original',independent)
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    for row,directory in entries:
        if not row.get('latencyVerified') or row['status']!='OK':
            counts['failureOutcomes']+=1;continue
        windows=csvrows(directory/'worker/windows.csv')
        require(windows==row['windows'],'Raw phase windows changed')
        measured=[w for w in windows if w['phase']=='MEASUREMENT'];require(len(measured)==1,'Window count')
        w=measured[0];n=int(w['operations']);writes=int(w['writes'])
        for channel,data in row['latency'].items():
            r=raw[str((directory/'worker'/(channel+'.hdr')).resolve())]
            expected=0 if channel=='response' else writes if channel=='update-service' else n-writes if channel=='read-service' else n
            require(int(r['count'])==data['count']==expected,'Per-channel conservation')
            for p,k in [('50','p50Ns'),('99','p99Ns'),('99.9','p999Ns'),('99.99','p9999Ns'),('99.999','p99999Ns')]:
                if expected:same(int(r[k]),data['percentilesNs'][p],'Published/library percentile');counts['quantileEndpoints']+=bool(expected)
            counts['channelCounts']+=1
        def distribution(name):return {int(b['upperEquivalentNs']):int(b['count']) for b in csvrows(directory/'worker'/(name+'-bins.csv'))}
        union=collections.Counter(distribution('read-service'));union.update(distribution('update-service'))
        require(dict(union)==distribution('service'),'Raw per-bin read/update union')
        counts['perBinUnions']+=1
        same(int(w['workerAllocatedBytes'])/n,row['measurement']['workerBytesPerOperation'],'Worker allocation')
        seconds=(int(w['endNs'])-int(w['startNs']))/1e9
        same(n/seconds,row['measurement']['operationsPerSecond'],'Throughput')
        memory=csvrows(directory/'process-memory.csv')
        selected=[r for r in memory if int(r['sampleStartNs'])>=int(w['startNs']) and int(r['sampleEndNs'])<=int(w['endNs']) and r['VmRSSKiB']]
        same(max((int(r['VmRSSKiB']) for r in selected),default=None),row['processMemory']['measuredMaxRssKiB'],'RSS')
        gc=old.gc_audit(directory/'gc-through-measurement.log',[(int(w['startNs']),int(w['endNs']))])
        for key,value in gc.items():
            if key!='occupancyCount':same(value,row['gc'][key],'Independent GC/'+key)
        counts['gcSummaries']+=1;counts['rssSummaries']+=1
        config=dict(line.split('=',1) for line in (directory/'worker/configuration.txt').read_text().splitlines() if '=' in line)
        require(config['traceSha256']==row['trace']['traceSha256'],'Trace identity')
        require(config['traceArrayPayloadBytes']=='9000027','Trace memory declaration')
        require('-Dchronicle.analytics.disable=true' in config['jvmArgs'],'Analytics must be disabled')
    # A confirmation may contain multiple paired forks; each must be complete and correctly matched.
    grouped=collections.defaultdict(dict)
    for row in study['observations']:
        key=tuple(row[k] for k in ('stage','payload','liveMiB','seed','block'))
        require(row['backend'] not in grouped[key],'Duplicate backend');grouped[key][row['backend']]=row
    require(len(grouped)==len(study['pairs']),'Pair coverage')
    for pair in study['pairs']:
        arms=grouped[tuple(pair[k] for k in ('stage','payload','liveMiB','seed','block'))]
        if pair['valid']:
            require(set(arms)=={'CAFFEINE','CHRONICLE_IN_MEMORY'},'Incomplete valid pair')
            require(len({r['trace']['traceSha256'] for r in arms.values()})==1,'Different paired traces')
            for channel,values in pair['ratios'].items():
                for percentile,value in values.items():
                    same(arms['CHRONICLE_IN_MEMORY']['latency'][channel]['percentilesNs'][percentile]/
                         arms['CAFFEINE']['latency'][channel]['percentilesNs'][percentile],value,'Published paired ratio')
                    counts['pairedRatios']+=1
    manifest=[dict(path=str(p.relative_to(base)),bytes=p.stat().st_size,sha256=sha(p))
              for p in sorted(base.rglob('*')) if p.is_file() and not p.is_relative_to(out)]
    (out/'inventory.json').write_text(json.dumps(manifest,indent=2)+'\n')
    receipt=dict(passed=True,newWorkloadJvms=len(study['observations']),controlJvms=len(entries)-len(study['observations']),
                 independentlyDecodedHistograms=len(raw),counts=dict(counts),studySha256=sha(base/'study.json'),
                 protocolSha256=sha(base/'protocol.json'),sourceArchiveSha256=sha(base/'source.tar.gz'),
                 inventoryFiles=len(manifest),runtimeFilesVerified=len(protocol['runtimeSha256']),
                 helper=load(base/'setup/functional-validation.json') if (base/'setup/functional-validation.json').exists() else None,
                 limits='Offline reconciliation reuses pinned HDR decoder and prior independent GC parser; no event-level causal claim or independent new performance replication.')
    (out/'audit.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('attempt');parser.add_argument('--out',type=pathlib.Path)
    args=parser.parse_args();base=ROOT/'evidence-archives'/args.attempt
    audit(base,args.out or base/'independent-audit-001')
