#!/usr/bin/env python3
"""Exclusive, bounded-memory verified archival outside benchmark collection."""
import argparse
import fcntl
import hashlib
import json
import os
import pathlib
import re
import tarfile

import tailcache12 as evidence
from tailcache12_calibration_start import prepare_file_cache

CHUNK=1024*1024


def stream_digest(stream):
    digest=hashlib.sha256()
    while chunk:=stream.read(CHUNK): digest.update(chunk)
    return digest.hexdigest()


def file_digest(path):
    with path.open('rb') as stream: return stream_digest(stream)


def advise(path):
    with path.open('rb') as stream:
        os.fsync(stream.fileno())
        os.posix_fadvise(stream.fileno(),0,0,os.POSIX_FADV_DONTNEED)


def create_archive(root,name,cache_prepare=None,include_prefixes=None,parent=None):
    if not re.fullmatch(r'native-final-[A-Za-z0-9._-]+\.tar\.gz',name):
        raise ValueError('Require a distinct native-final archive basename')
    reports=root/'build/reports/tailcache12'; reports.mkdir(parents=True,exist_ok=True)
    out=root/'evidence-archives'/name; out.parent.mkdir(parents=True,exist_ok=True)
    metadata=out.with_suffix('.json')
    if out.exists() or metadata.exists(): raise ValueError('Retained archive exists; refusing overwrite')
    if bool(include_prefixes)!=(parent is not None):raise ValueError('Incremental prefixes require a verified parent archive')
    if include_prefixes and (len(set(include_prefixes))!=len(include_prefixes)
            or any(not re.fullmatch(r'native-final-[A-Za-z0-9._-]+',p) for p in include_prefixes)):
        raise ValueError('Invalid/duplicate incremental prefixes')
    parent_ref=None
    with (reports/'native-benchmark.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('A benchmark/controller is active; archive refused')
        if cache_prepare: cache_prepare(reports/(name.removesuffix('.tar.gz')+'-cache-preparation.json'))
        if parent:
            parent_name,expected_hash=parent
            if (not re.fullmatch(r'native-final-[A-Za-z0-9._-]+\.tar\.gz',parent_name)
                    or parent_name==name or not re.fullmatch(r'[0-9a-f]{64}',expected_hash)):
                raise ValueError('Invalid incremental archive parent')
            previous=out.parent/parent_name
            if previous.is_symlink() or not previous.is_file() or file_digest(previous)!=expected_hash:
                raise ValueError('Parent archive missing or checksum mismatch')
            parent_ref=dict(path=parent_name,sha256=expected_hash,bytes=previous.stat().st_size)
            advise(previous)
        files=sorted(p for p in reports.rglob('*') if p.is_file() and not p.is_symlink()
            and p.relative_to(reports).parts[0].startswith('native-final-')
            and (not include_prefixes or any(p.relative_to(reports).parts[0].startswith(prefix) for prefix in include_prefixes)
                 or p.relative_to(reports).parts[0].startswith(name.removesuffix('.tar.gz')+'-cache-preparation')))
        if include_prefixes and not files:raise ValueError('Incremental archive selected no retained files')
        if include_prefixes and any(not any(p.relative_to(reports).parts[0].startswith(prefix) for p in files)
                                    for prefix in include_prefixes):
            raise ValueError('An incremental prefix has no retained evidence')
        inventory={}
        for path in files:
            inventory[path.relative_to(root).as_posix()]=file_digest(path)
            advise(path)
        with tarfile.open(out,'x:gz',compresslevel=1) as archive:
            for path in files:
                archive.add(path,arcname=path.relative_to(root).as_posix(),recursive=False)
                advise(path)
        advise(out)
        verified=0; seen=set()
        with tarfile.open(out,'r:gz') as archive:
            for member in archive:
                if not member.isfile() or member.name in seen or member.name not in inventory:
                    raise ValueError('Unexpected/duplicate archive member')
                with archive.extractfile(member) as stream:
                    if stream_digest(stream)!=inventory[member.name]: raise ValueError('Archive member checksum mismatch')
                seen.add(member.name); verified+=1
        if seen!=set(inventory): raise ValueError('Incomplete archive inventory')
        result=dict(path=str(out),bytes=out.stat().st_size,sha256=file_digest(out),
            verifiedMembers=verified,members=inventory,hashChunkBytes=CHUNK)
        if parent_ref:result.update(archiveScope='incremental',parentArchive=parent_ref,includePrefixes=list(include_prefixes))
        advise(out)
        with metadata.open('x') as stream: json.dump(result,stream,indent=2)
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('archive_name')
    parser.add_argument('--include-prefix',action='append');parser.add_argument('--parent-archive');parser.add_argument('--parent-sha256')
    parser.add_argument('--streaming-private-cache',action='store_true');args=parser.parse_args()
    if bool(args.parent_archive)!=bool(args.parent_sha256):parser.error('Require both parent archive and SHA256')
    result=create_archive(evidence.ROOT,args.archive_name,
        lambda p:prepare_file_cache(p,require_empty_swap=False,include_build_outputs=args.streaming_private_cache,
            stream_inventory=args.streaming_private_cache),include_prefixes=args.include_prefix,
        parent=(args.parent_archive,args.parent_sha256) if args.parent_archive else None)
    print(json.dumps({k:v for k,v in result.items() if k!='members'}),flush=True)


if __name__=='__main__': main()
