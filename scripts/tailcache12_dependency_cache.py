"""Opt-in clean-page advice for inactive, pinned Java/Gradle code only."""
import hashlib
import json
import os
import pathlib
import re
import stat

import tailcache12 as evidence
from tailcache12_calibration_start import memory_snapshot

JDK=pathlib.Path('/usr/lib/jvm/java-21-openjdk')
EXACT=(JDK/'lib/modules',JDK/'lib/server/libjvm.so')
GRADLE=pathlib.Path('/home/y/.gradle/wrapper/dists/gradle-9.7.1-bin/1w1c7tv4s851m17nbqdsro2tv/gradle-9.7.1/lib')
MODULES=pathlib.Path('/home/y/.gradle/caches/modules-2/files-2.1')
METHOD='readonly-fsync-fadvise-inactive-pinned-dependency-code-v1'
URL='distributionUrl=https\\://services.gradle.org/distributions/gradle-9.7.1-bin.zip'


def allowed(name):
    p=pathlib.PurePosixPath(name)
    if p.as_posix()!=name or '..' in p.parts:return False
    if p in EXACT:return True
    if p.is_relative_to(GRADLE):return p.suffix=='.jar'
    if p.is_relative_to(MODULES):
        parts=p.relative_to(MODULES).parts
        return len(parts)==5 and bool(re.fullmatch('[0-9a-f]{40}',parts[3])) and parts[4].endswith('.jar')
    return False


def active_java():
    result=[]
    for p in pathlib.Path('/proc').glob('[0-9]*'):
        try:
            comm=(p/'comm').read_text().strip()
            try:exe=str((p/'exe').resolve(strict=True))
            except PermissionError:exe=None
            except FileNotFoundError:exe=None
            if comm in ('java','javaw') or (exe and pathlib.Path(exe).name in ('java','javaw')):
                result.append(dict(pid=int(p.name),comm=comm,executable=exe))
        except (FileNotFoundError,ProcessLookupError):pass
    return result


def declarations():
    values={
        'wrapper':(evidence.ROOT/'gradle/wrapper/gradle-wrapper.properties').read_text(),
        'jdkRelease':(JDK/'release').read_text()}
    return {k:dict(text=v,sha256=hashlib.sha256(v.encode()).hexdigest()) for k,v in values.items()}


def verify_declarations(values):
    if set(values)!={'wrapper','jdkRelease'}:raise ValueError('Missing pinned dependency declarations')
    for row in values.values():
        if hashlib.sha256(row['text'].encode()).hexdigest()!=row['sha256']:
            raise ValueError('Changed pinned dependency declaration')
    if ([v for v in values['wrapper']['text'].splitlines() if v.startswith('distributionUrl=')]!=[URL]
            or [v for v in values['jdkRelease']['text'].splitlines() if v.startswith('JAVA_RUNTIME_VERSION=')]
                !=['JAVA_RUNTIME_VERSION="21.0.12.1+1"']
            or [v for v in values['jdkRelease']['text'].splitlines() if v.startswith('JAVA_VERSION=')]
                !=['JAVA_VERSION="21.0.12.1"']):
        raise ValueError('Inactive dependency preparation requires pinned Java21/Gradle9.7.1')


def targets():
    result=list(EXACT)
    for root in (GRADLE,MODULES):
        if root.is_symlink() or root.resolve()!=root or not root.is_dir():
            raise ValueError('Dependency root absent/symlink/escape')
        result.extend(p for p in root.rglob('*.jar') if allowed(str(p)))
    if len(result)!=len(set(result)):raise ValueError('Duplicate dependency targets')
    if not any(p.is_relative_to(GRADLE) for p in result) or not any(p.is_relative_to(MODULES) for p in result):
        raise ValueError('Missing dependency jar inventory')
    for p in result:
        if not allowed(str(p)) or p.is_symlink() or p.resolve()!=p:
            raise ValueError('Dependency target symlink/escape/undeclared path')
    return result


def prepare(report):
    if report.exists():raise ValueError('Dependency preparation exists; refusing overwrite')
    result=dict(version=1,method=METHOD,sourceSha256=evidence.source_hash(),operatorUid=os.getuid(),
        before=memory_snapshot(),files=[],errors=[],processChecks=[],preparationPass=False,readOnly=True)
    try:
        result['declarations']=declarations();verify_declarations(result['declarations'])
        busy=active_java();result['processChecks'].append(busy)
        if busy:raise ValueError('Java active; no dependency advice allowed')
        paths=targets();result['declaredTargets']=[str(p) for p in paths];identities={};seen=set()
        for p in paths:
            info=p.stat();uid=0 if p in EXACT else os.getuid();identity=(info.st_dev,info.st_ino)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=uid or identity in seen):
                raise ValueError('Unexpected dependency target ownership/type/inode alias')
            seen.add(identity);identities[p]=(info.st_dev,info.st_ino,info.st_uid,info.st_size,info.st_mtime_ns)
        busy=active_java();result['processChecks'].append(busy)
        if busy:raise ValueError('Java appeared before dependency advice')
        for p,identity in identities.items():
            fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
            try:
                before=os.fstat(fd)
                actual=(before.st_dev,before.st_ino,before.st_uid,before.st_size,before.st_mtime_ns)
                if actual!=identity or not stat.S_ISREG(before.st_mode):
                    raise ValueError('Dependency fd identity changed before advice')
                os.fsync(fd);os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED);after=os.fstat(fd)
                if (after.st_dev,after.st_ino,after.st_uid,after.st_size,after.st_mtime_ns)!=identity:
                    raise ValueError('Dependency file changed during advice')
                result['files'].append(dict(path=str(p),device=before.st_dev,inode=before.st_ino,uid=before.st_uid,
                    bytesBefore=before.st_size,bytesAfter=after.st_size,mtimeBeforeNs=before.st_mtime_ns,
                    mtimeAfterNs=after.st_mtime_ns,advice='POSIX_FADV_DONTNEED',regular=True))
            finally:os.close(fd)
        result['preparationPass']=True
    except (OSError,ValueError) as error:
        result['errors'].append(dict(error=str(error)))
    result['after']=memory_snapshot()
    report.parent.mkdir(parents=True,exist_ok=True)
    with report.open('x') as stream:json.dump(result,stream,indent=2)
    if not result['preparationPass']:raise ValueError('Inactive dependency advice failed; no benchmark launched')
    return result


def verify(record,source):
    if (record.get('version')!=1 or record.get('method')!=METHOD or record.get('sourceSha256')!=source
            or record.get('readOnly') is not True or record.get('preparationPass') is not True
            or record.get('errors') or record.get('processChecks')!=[[],[]] or not record.get('files')):
        raise ValueError('Invalid inactive dependency code preparation')
    verify_declarations(record['declarations'])
    paths=[r['path'] for r in record['files']];declared=record.get('declaredTargets',[])
    if (paths!=declared or len(paths)!=len(set(paths)) or not set(map(str,EXACT)).issubset(paths)
            or any(not allowed(p) for p in paths) or not any(pathlib.Path(p).is_relative_to(GRADLE) for p in paths)
            or not any(pathlib.Path(p).is_relative_to(MODULES) for p in paths)):
        raise ValueError('Changed inactive dependency target policy')
    seen=set()
    for row in record['files']:
        identity=(row['device'],row['inode']);uid=0 if pathlib.Path(row['path']) in EXACT else record['operatorUid']
        if (row.get('regular') is not True or row.get('advice')!='POSIX_FADV_DONTNEED' or row['uid']!=uid
                or row['bytesBefore']<0 or row['bytesAfter']!=row['bytesBefore'] or row['inode']<=0
                or row['mtimeAfterNs']!=row['mtimeBeforeNs'] or identity in seen):
            raise ValueError('Dependency identity/size/mtime/type/ownership changed')
        seen.add(identity)
    return True
