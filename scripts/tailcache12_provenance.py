"""Match measurement sources across stages while retaining every full snapshot.

Analysis, tests and documentation can evolve after a run without changing its
workload. Resuming an individual attempt still requires its complete source hash.
"""
import hashlib
import pathlib
import tarfile

VERSION = "tailcache12-measurement-source-v4-native-cpu"
NATIVE_LEGACY_VERSION = "tailcache12-measurement-source-v3-native-cpu"
LEGACY_VERSION = "tailcache12-measurement-source-v2-controller"
NATIVE_CONTROLS = ("scripts/tailcache12_native_host.py", "scripts/tailcache12_native.py")
CONTROLS = ("build.gradle.kts", "settings.gradle.kts", "gradle.properties", "gradlew",
            "scripts/tailcache12.py", "scripts/tailcache12_controller.py",
            "scripts/windows_host_monitor.ps1", "scripts/tailcache12_native_host.py",
            "scripts/tailcache12_native.py")
PREFIXES = ("src/main/", "src/jmh/", "gradle/wrapper/")


def selected(name):
    return name in CONTROLS or name.startswith(PREFIXES)


def fingerprint(files):
    native = (any(n in files for n in NATIVE_CONTROLS)
              or b"tailcache12_native_host" in files.get("scripts/tailcache12.py", b""))
    controls = CONTROLS if native else tuple(n for n in CONTROLS if n not in NATIVE_CONTROLS)
    if not set(controls).issubset(files) or any(not any(n.startswith(p) for n in files) for p in PREFIXES):
        raise ValueError("Incomplete measurement source snapshot")
    native_version = VERSION if b"tailcache12-host-v4-native-cpu" in files.get("scripts/tailcache12.py", b"") else NATIVE_LEGACY_VERSION
    digest = hashlib.sha256(((native_version if native else LEGACY_VERSION) + "\0").encode())
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
