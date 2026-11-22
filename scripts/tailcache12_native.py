#!/usr/bin/env python3
"""Run a Task 12 command inside a temporary user-owned accounting scope."""
import argparse
import os
import pathlib
import re
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("unit", help="Unique scope name suffix")
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="Task 12 Python script followed by its arguments")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.unit) or not args.command:
        parser.error("Require a unique unit name and Task 12 script")
    root = pathlib.Path(__file__).resolve().parents[1]
    script = (root / args.command[0]).resolve()
    if script.parent != root / "scripts" or not script.name.startswith("tailcache12") or not script.is_file():
        parser.error("Command must name an existing Task 12 Python script in scripts/")
    unit = "tailcache12-" + args.unit + ".scope"
    environment = dict(os.environ, TAILCACHE_NATIVE_SCOPE=unit, TAILCACHE_REQUIRE_NATIVE_HOST="1")
    for name in ("TAILCACHE_REQUIRE_WINDOWS_HOST", "TAILCACHE_WINDOWS_HOST_FILE",
                 "TAILCACHE_CONTROLLER_ANCHOR_UNIX_SECONDS", "TAILCACHE_CONTROLLER_PERIOD_SECONDS",
                 "TAILCACHE_CONTROLLER_BEFORE_SECONDS", "TAILCACHE_CONTROLLER_AFTER_SECONDS"):
        environment.pop(name, None)
    os.chdir(root)
    command = ["systemd-run", "--user", "--scope", "--quiet", "--expand-environment=no",
               "--unit=" + unit, sys.executable, str(script), *args.command[1:]]
    lock_path = root / "build/reports/tailcache12/native-benchmark.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # Keep the same BSD flock/scope lifetime without retaining a Python parent.
    # The native flock parent waits for systemd-run and keeps the lock descriptor.
    # Do not add --close/--no-fork/--fcntl: archive guards use fcntl.flock too.
    os.execvpe("flock",["flock","--exclusive","--nonblock","--conflict-exit-code","73",
        str(lock_path),*command],environment)


if __name__ == "__main__":
    raise SystemExit(main())
