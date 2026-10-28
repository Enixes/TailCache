"""Match measurement sources across stages while retaining every full snapshot.

Analysis, tests and documentation can evolve after a run without changing its
workload. Resuming an individual attempt still requires its complete source hash.
"""
import hashlib
import pathlib
import tarfile

VERSION = "tailcache12-measurement-source-v2-controller"
CONTROLS = ("build.gradle.kts", "settings.gradle.kts", "gradle.properties", "gradlew",
            "scripts/tailcache12.py", "scripts/tailcache12_controller.py",
            "scripts/windows_host_monitor.ps1")
PREFIXES = ("src/main/", "src/jmh/", "gradle/wrapper/")


def selected(name):
    return name in CONTROLS or name.startswith(PREFIXES)


def fingerprint(files):
    if not set(CONTROLS).issubset(files) or any(not any(n.startswith(p) for n in files) for p in PREFIXES):
        raise ValueError("Incomplete measurement source snapshot")
    digest = hashlib.sha256((VERSION + "\0").encode())
    for name in sorted(files):
        digest.update(name.encode() + b"\0")
        digest.update(hashlib.sha256(files[name]).digest())
    return digest.hexdigest()


def measurement_source_hash(root):
    root = pathlib.Path(root)
    paths = [root / name for name in CONTROLS]
    for prefix in PREFIXES:
        paths.extend(p for p in (root / prefix).rglob("*") if p.is_file())
    return fingerprint({p.relative_to(root).as_posix(): p.read_bytes() for p in paths})


def archive_measurement_source_hash(path):
    files = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            if member.isfile() and selected(member.name):
                if member.name in files:
                    raise ValueError("Duplicate measurement source in archive")
                files[member.name] = archive.extractfile(member).read()
    return fingerprint(files)
