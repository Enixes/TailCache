#!/usr/bin/env python3
"""One-time residual-page recovery with identical final swap policy, outside collection."""
import argparse
import fcntl
import hashlib
import json
import pathlib
import subprocess
import time

import tailcache12 as evidence
from tailcache12_calibration_start import memory_snapshot
from tailcache12_provenance import measurement_source_hash

PROPERTIES='Id,What,Options,Priority,ActiveState'


def snapshot():
    command=['systemctl','show','dev-zram0.swap','dev-sda3.swap','--property='+PROPERTIES]
    result=subprocess.run(command,text=True,capture_output=True,check=True,timeout=15)
    devices=[]
    for line in pathlib.Path('/proc/swaps').read_text().splitlines()[1:]:
        name,kind,size,used,priority=line.split()
        devices.append(dict(name=name,type=kind,sizeKiB=int(size),usedKiB=int(used),priority=int(priority)))
    settings={}
    for name in ('disksize','comp_algorithm','mem_limit','max_comp_streams'):
        path=pathlib.Path('/sys/block/zram0')/name
        settings[name]=path.read_text().strip() if path.exists() else None
    return dict(memory=memory_snapshot(),devices=devices,unitProperties=result.stdout.strip(),zramSettings=settings,
        swappiness=pathlib.Path('/proc/sys/vm/swappiness').read_text().strip(),
        zswapEnabled=pathlib.Path('/sys/module/zswap/parameters/enabled').read_text().strip())


def configuration(state):
    return dict(devices=sorted([{k:v for k,v in d.items() if k!='usedKiB'} for d in state['devices']],key=lambda d:d['name']),
                **{k:state[k] for k in ('unitProperties','zramSettings','swappiness','zswapEnabled')})


def reset(report):
    if report.exists(): raise ValueError('Retained swap preparation exists; refusing overwrite')
    before=snapshot(); devices={d['name']:d for d in before['devices']}
    if (set(devices)!={'/dev/zram0','/dev/sda3'} or devices['/dev/sda3']['usedKiB']!=0
            or before['memory']['MemAvailableKiB']<3*1024**2 or devices['/dev/zram0']['usedKiB']>256*1024):
        raise ValueError('Swap recovery requires the reviewed devices, empty disk swap and ample RAM')
    record=dict(version=1,sourceSha256=evidence.source_hash(),
        measurementSourceSha256=measurement_source_hash(evidence.ROOT),
        scriptSha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
        before=before,preparationPass=False,command=['sudo','-n','systemctl','restart','dev-zram0.swap'],
        startNs=time.monotonic_ns())
    try:
        if devices['/dev/zram0']['usedKiB']:
            completed=subprocess.run(record['command'],text=True,capture_output=True,timeout=60)
            record.update(exitCode=completed.returncode,stdout=completed.stdout,stderr=completed.stderr)
        else: record.update(exitCode=0,stdout='Already empty; no restart performed',stderr='',command=[])
        record['after']=snapshot()
        record['configurationRestored']=configuration(before)==configuration(record['after'])
        record['preparationPass']=(record['exitCode']==0 and record['configurationRestored']
            and record['after']['memory']['SwapUsedKiB']==0)
    except Exception as error: record['error']=f'{type(error).__name__}: {error}'
    finally:
        try:
            after=snapshot()
            if not any(d['name']=='/dev/zram0' for d in after['devices']):
                restore=['sudo','-n','systemctl','start','dev-zram0.swap']
                completed=subprocess.run(restore,text=True,capture_output=True,timeout=60)
                record['restorationAttempt']=dict(command=restore,exitCode=completed.returncode,
                    stdout=completed.stdout,stderr=completed.stderr)
                after=snapshot()
            record['after']=after
            record['configurationRestored']=configuration(before)==configuration(after)
            if not record['configurationRestored'] or after['memory']['SwapUsedKiB']!=0:
                record['preparationPass']=False
        except Exception as error:
            record['preparationPass']=False; record['verificationError']=f'{type(error).__name__}: {error}'
        record['endNs']=time.monotonic_ns(); evidence.save(report,record)
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('attempt_id'); args=parser.parse_args()
    if not evidence.re.fullmatch(r'[A-Za-z0-9._-]+',args.attempt_id): parser.error('Invalid identifier')
    report=evidence.REPORTS/(args.attempt_id+'.json')
    with (evidence.REPORTS/'native-benchmark.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('A benchmark/controller is active; swap action refused')
        result=reset(report)
    print(json.dumps({k:v for k,v in result.items() if k not in ('before','after')},indent=2),flush=True)
    return 0 if result['preparationPass'] else 1


if __name__=='__main__': raise SystemExit(main())
