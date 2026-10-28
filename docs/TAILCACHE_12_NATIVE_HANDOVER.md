# TailCache Task 12: saved work for native Linux

Saved on 28 October 2026. The user will handle OS installation. No drive was resized, formatted or erased, and no installer was written. The Windows continuation is paused and must not restart WSL measurements automatically.

## What is preserved

The portable work archive contains the full Linux checkout, including `.git`, uncommitted and untracked sources, all retained raw/derived reports, task-specific Gradle caches, previous hashed evidence archives and `environment.sh`. The separate full Ubuntu WSL export is a rollback copy of the Linux filesystem and installed tools. `SHA256SUMS` and backup metadata accompany the files.

The active branch is `tailcache-12-crossover`, based on `ed9a9358b42eb3de04ad3c2de1a127a9e54ed90a`. The user requested committing and pushing the source checkpoint on this branch. Clone the latest branch revision for the source; the large raw results, caches and backup archives are excluded from Git. No PR is needed.

```sh
git clone --branch tailcache-12-crossover https://github.com/Enixes/TailCache.git
cd TailCache
```

Existing verified backups are retained in `G:\TailCache-backup-20261028-001` and the Windows checkout's `build/native-migration/20261028-001/`. Git alone does not contain those raw artifacts. The portable archive is 755,762,287 bytes with SHA256 `07cdbd5b4607a8164ad945fb73f00f3fdbf8807e821981d7955ad2f2b1781c41`; the full WSL export is 4,682,106,880 bytes with SHA256 `1d3823d7d1a72cf2a165bb208bdc09f12f6f8077f4f324741bfed104af946246`. The source publication may include later handover metadata than those frozen backup snapshots.

## Exact research checkpoint

Task 12 is **incomplete**, with `campaignReady=false` and `reportable=false`.

- Java verification: 34 tests passed. Python verification: 40 tests passed. Native Windows observer forced-lock regression passed. Java measurement sources are unchanged since the latest qualification.
- Measurement-source identity: `866e0d76f0125b716007745824d2e85949a4c78ff9c4db0ef3ba0d4ff84a9888`.
- Observer-v5 functional validation passed all 14 host screens. Matching Caffeine/4-KiB/96-MiB XML probes passed 2/2. Complete every-operation compiler screen passed 8/8 (maximum iteration 1 ms), and JMH compiler screen passed 8/8 (maximum iteration 4 ms). Raw replay and all four source-archive matches passed.
- Latest calibration `wsl-recorder-calibration-20261028-005` ended before the migration checkpoint: **12/64 accepted logical slots, 15 recorded JVM attempts**. The Caffeine/4-KiB/96-MiB every-operation slot exhausted its predeclared two CPU-only retries. All three rejected candidates and both retry preflights remain retained. The grid is rejected/incomplete.
- Grids 001-004 remain rejected under their original rules. Do not reuse their forks to fill a later grid or reinterpret them under a new threshold.
- The exact process behind the earlier CPU spike is unknown. The later host diagnostic contains stale observations after its old observer crashed; its saved analysis excludes those samples. Observer v5 repaired the separate snapshot-sharing failure.

The full current source, raw manifests, histograms, compiler/GC logs, host samples and prior checkpoints are in `build/reports/tailcache12/` and the saved evidence archives. Absolute raw paths recorded by WSL can be resolved through the retained sibling directories by `raw_directory()`; do not flatten or rename those directories.

## Restore the portable archive

Keep the backup folder intact and verify its `SHA256SUMS`. On the installed native Linux system, extract the work archive into a new folder, for example:

```sh
mkdir -p "$HOME/tailcache-saved"
tar --no-same-owner -xzf TailCache-work-20261028.tar.gz -C "$HOME/tailcache-saved"
cd "$HOME/tailcache-saved/TailCache"
export GRADLE_USER_HOME="$HOME/tailcache-saved/.gradle"
```

Install Java 21, Python 3 and Git through the OS package manager if needed. Set `JAVA_HOME` to that Java 21 installation and record the exact build. The WSL baseline used Ubuntu OpenJDK 21.0.12.1, Gradle 9.7.1 and Python 3.14.4. The preserved caches include the Gradle distribution and dependencies; the full WSL export additionally preserves the old installed runtime. Do not assume a different native JDK build is already qualified.

The saved `environment.sh` contains old `/opt/tailcache` paths. Adapt those paths if restoring under your home directory. Clear Windows transport and old callback scheduling variables on native Linux:

```sh
unset TAILCACHE_REQUIRE_WINDOWS_HOST TAILCACHE_WINDOWS_HOST_FILE
unset TAILCACHE_CONTROLLER_ANCHOR_UNIX_SECONDS TAILCACHE_CONTROLLER_PERIOD_SECONDS
unset TAILCACHE_CONTROLLER_BEFORE_SECONDS TAILCACHE_CONTROLLER_AFTER_SECONDS
./gradlew --offline test jmhClasses
python3 -m unittest discover -s scripts -p 'test_tailcache12*.py'
```

## Continue on the new environment

Use fresh native-Linux attempt IDs. **Do not resume a WSL attempt after changing OS/runtime.** Preserve the RAM configuration (the recorded baseline is DDR4-2133) and document native CPU governor, power, kernel, JDK and host conditions before timing. The user previously observed BIOS SVM/XMP resets; no BIOS update was performed.

1. Read `TAILCACHE_12_COMPLETION_PLAN.md`, `TAILCACHE_12_STATUS.json`, `TAILCACHE_12_RUNBOOK.md` and the research plan. Requalify functional validation, both full compiler screens and the matching pressure probe on native Linux; retain new source/environment archives. The candidate duration is 60 one-second warmups and eight measurements, with the unchanged 80-ms aggregate/10-ms-per-iteration compiler rules.
2. Start a **new** both-recorder pressure calibration. Candidate inputs remain 32,768 residents, fixed 512-MiB G1 heap, 256/4,096-B payloads, 0/96/208/288-MiB common ballast, 32-MiB/s churn, seed 24301 and two counterbalanced passes. Audit full occupancy/GC/churn/histogram/identity/integrity/host/compiler and independent-replica coverage.
3. The current opt-in CPU retry protocol is **Windows-observer-v5-specific**. Do not pass `--host-cpu-retries 2` on native Linux; it requires that Windows observer. A native retry protocol, if needed, must be declared and reviewed prospectively. Do not merely increase limits or accept old rejected data.
4. Complete independent observer/floor characterization and coherence review. The short functional characterizations do not qualify these gates. Then run/review the guarded eight-cell pilot.
5. Freeze exposure, variance, endpoints, gates, seeds/order and retry rules before implementing/executing the 16-condition, two-pass, three-fork confirmatory campaign and robustness seeds. That campaign is not yet implemented or run. Use independent fork/block statistics and raw histogram endpoints, keep noisy valid/invalid data, and withhold claims for missing coverage.

An agent continuing this work should finish all Task 12A-12G gates and produce an analysis-ready evidence package. A successful build, launched job, partial calibration or saved handover is not completion.
