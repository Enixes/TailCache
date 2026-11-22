"""Explicit read-only clean-page advice for observed Task12 tooling, never general caches."""
import json
import os
import pathlib
import stat

import tailcache12 as evidence
from tailcache12_calibration_start import memory_snapshot

SESSION='01a1032c-87df-72d1-93cb-cd6f076451a0'
TASK_HOME=pathlib.Path('/home/y')
BROWSER=TASK_HOME/'.cache/ms-playwright'
EXACT=(
    TASK_HOME/'.codex/packages/standalone/releases/0.167.0-x86_64-unknown-linux-musl/bin/codex',
    TASK_HOME/'.codex/packages/standalone/releases/0.167.0-x86_64-unknown-linux-musl/bin/codex-code-mode-host',
    pathlib.Path('/usr/lib/chatgpt/resources/cua_node/bin/node'),
    TASK_HOME/'.codex/cache/remote_plugin_catalog/e82c7596fac8d7b0.json',
    TASK_HOME/('.codex/sessions/2026/10/04/rollout-2026-10-04T00-40-12-'+SESSION+'.jsonl'))
METHOD='readonly-fsync-fadvise-exact-task-tooling-v1'


def allowed(name):
    p=pathlib.PurePosixPath(name)
    if '..' in p.parts or p.as_posix()!=name:return False
    if p in EXACT:return True
    if not p.is_relative_to(BROWSER) or p==BROWSER:return False
    parts=p.relative_to(BROWSER).parts
    if len(parts)<2 or not (parts[0]=='.links' or parts[0].startswith(
            ('chromium-','chromium_headless_shell-','firefox-','webkit-','ffmpeg-','winldd-'))):return False
    return not any(part in ('User Data','user-data','Default','Cookies','History','GPUCache') for part in parts)


def active_browsers():
    found=[]
    for p in pathlib.Path('/proc').glob('[0-9]*'):
        try:
            if (p/'exe').resolve(strict=True).is_relative_to(BROWSER):found.append(int(p.name))
        except OSError:pass
    return found


def targets():
    if BROWSER.is_symlink():raise ValueError('Tool installation root is a symlink')
    result=list(EXACT)
    if BROWSER.exists():result.extend(p for p in BROWSER.rglob('*')
        if p.is_file() and not p.is_symlink() and allowed(str(p)))
    if len(result)!=len(set(result)):raise ValueError('Duplicate task-tooling cache targets')
    for p in result:
        if not allowed(str(p)) or p.is_symlink() or p.resolve()!=p:
            raise ValueError('Tooling cache target symlink/escape/undeclared path')
    return result


def prepare(report):
    if report.exists():raise ValueError('Tooling preparation exists; refusing overwrite')
    result=dict(version=1,method=METHOD,sessionId=SESSION,sourceSha256=evidence.source_hash(),
        operatorUid=os.getuid(),before=memory_snapshot(),files=[],missing=[],errors=[],activeBrowserPids=[],
        preparationPass=False,readOnly=True)
    try:paths=targets();busy=active_browsers()
    except (OSError,ValueError) as error:
        result['errors'].append(dict(error=str(error)));evidence.save(report,result);raise
    result['activeBrowserPids']=busy;result['declaredTargets']=[str(p) for p in paths]
    if busy:
        evidence.save(report,result);raise ValueError('Tool browser installation is active; no advice applied')
    # Validate every target before any advice. Live code mappings remain protected by the kernel.
    identities={}
    for p in paths:
        if not p.exists():result['missing'].append(str(p));continue
        info=p.stat();expected_uid=0 if str(p)=='/usr/lib/chatgpt/resources/cua_node/bin/node' else os.getuid()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=expected_uid:
            result['errors'].append(dict(path=str(p),error='Unexpected tooling target type/ownership'))
            evidence.save(report,result);raise ValueError('Unexpected tooling target type/ownership')
        identities[p]=(info.st_dev,info.st_ino,info.st_uid)
    for p in identities:
        try:
            fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
            try:
                before=os.fstat(fd)
                if (before.st_dev,before.st_ino,before.st_uid)!=identities[p] or not stat.S_ISREG(before.st_mode):
                    raise ValueError('Tooling target identity changed before advice')
                os.fsync(fd);os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED);after=os.fstat(fd)
                if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino) or after.st_size<before.st_size:
                    raise ValueError('Tooling file identity/size changed during advice')
                result['files'].append(dict(path=str(p),device=before.st_dev,inode=before.st_ino,uid=before.st_uid,
                    bytesBefore=before.st_size,bytesAfter=after.st_size,advice='POSIX_FADV_DONTNEED',regular=True))
            finally:os.close(fd)
        except (OSError,ValueError) as error:result['errors'].append(dict(path=str(p),error=str(error)))
    result['after']=memory_snapshot();result['preparationPass']=not result['errors'] and bool(result['files'])
    evidence.save(report,result)
    if not result['preparationPass']:raise ValueError('Task-tooling advice failed; no benchmark launched')
    return result


def verify(record,source):
    if (record.get('version')!=1 or record.get('method')!=METHOD or record.get('sessionId')!=SESSION
            or record.get('sourceSha256')!=source or record.get('readOnly') is not True
            or record.get('preparationPass') is not True or record.get('errors') or record.get('activeBrowserPids')
            or not record.get('files')):raise ValueError('Invalid task-tooling cache proof')
    paths=[r['path'] for r in record['files']]
    declared=record.get('declaredTargets',[]);missing=record.get('missing',[])
    if (len(paths)!=len(set(paths)) or len(declared)!=len(set(declared)) or set(paths)&set(missing)
            or set(paths+missing)!=set(declared) or not set(map(str,EXACT)).issubset(declared)
            or any(not allowed(p) for p in declared)):
        raise ValueError('Undeclared/duplicate task-tooling advice target')
    for row in record['files']:
        expected_uid=0 if row['path']=='/usr/lib/chatgpt/resources/cua_node/bin/node' else record['operatorUid']
        if (row.get('advice')!='POSIX_FADV_DONTNEED' or row.get('regular') is not True or row['uid']!=expected_uid
                or row['bytesBefore']<0 or row['bytesAfter']<row['bytesBefore'] or row['inode']<=0):
            raise ValueError('Tooling advice did not preserve the declared file')
    return True
