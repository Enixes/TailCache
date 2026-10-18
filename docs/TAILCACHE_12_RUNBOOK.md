# Task 12 — running on another machine

Use branch `tailcache-12-crossover`. Task 12A and functional pause capture are implemented. This branch also supplies GC occupancy/exposure analysis and exploratory calibration. **Host/JIT qualification, observer coherence, the pilot and the reportable crossover campaign remain open.** A larger machine still needs to pass the JIT screen.

## Prepare a Linux host

Requirements: a Java 21 JDK (including `jcmd`), Python 3.10 or newer, Git, and network access for the initial dependency download. The scripts use Linux `/proc` and available power/governor information. They call Gradle and Git directly; RTK is not required on the benchmark machine.

```sh
git clone --branch tailcache-12-crossover https://github.com/Enixes/TailCache.git
cd TailCache
java -version
./gradlew test jmhClasses resultToolsClasses
python3 -m unittest discover -s scripts -p 'test_tailcache12*.py' -v
```

The first Gradle command populates dependencies; evidence scripts then run Gradle offline. Confirm Gradle can locate Java 21 with `./gradlew -q javaToolchains`. Keep the same exact JDK build for paired conditions. Use AC power, a stable power mode and a quiet host. Complete downloads/builds before collecting benchmark evidence.

All attempt IDs below must be new. Output directories are immutable. Preserve every rejected attempt and its reasons. Never run two benchmark drivers concurrently.

## Validate and qualify

```sh
python3 scripts/tailcache12.py validate machine-b-functional-001
python3 scripts/tailcache12.py pause machine-b-pause-001
python3 scripts/tailcache12.py jit machine-b-jit-001 --warmups 30
```

`validate` checks adapters, retained payload ownership, pause capture, histogram counts and observer floors. Its short observer comparison is characterization; it does not qualify observer coherence. `pause` verifies a deliberately induced full-GC pause against worker evidence. Both are explicitly non-reportable, even if functional checks pass.

`jit` checks both backends/payloads in two orders with eight measured iterations per fresh JVM. The existing limits remain 80 ms total compiler time and 10 ms per iteration. It records narrower worker-envelope counters as supporting evidence and requires their complete per-fork sidecars. On host failure it suspends remaining blocks. Inspect `audit.json`, `manifest.json`, `host.csv`, raw compiler XML and GC logs. A successful Gradle exit does not establish qualification.

JIT probes use 8,192 residents, 8 MiB application data, a 512 MiB heap and 16 MiB/s churn as exploratory controls. A passing low-pressure JIT probe does not qualify the larger calibration grid or every campaign fork. Verify the eventual calibrated conditions before the pilot.

## Check the GC analysis, then calibrate

A short functional probe exercises both backends with identical controls:

```sh
python3 scripts/tailcache12_calibrate.py probe machine-b-gc-probe-001 --heap-mib 256 --residents 8192 --payloads 4096 --live-mib 64 --churn-mib 32 --warmups 3 --measurements 3 --repeats 1
```

`probe` never sets `calibrationReady=true`. Its zero exit means the diagnostic completed, not that host or research quality passed. Read `calibration.json` for rejection reasons, raw GC pauses, clipped measurement overlap, occupancy, rates and histogram-derived percentiles.

The candidate full calibration is:

```sh
python3 scripts/tailcache12_calibrate.py calibrate machine-b-calibration-001
python3 scripts/tailcache12_calibrate.py audit machine-b-calibration-001
```

Defaults are a fixed 512 MiB heap, 32,768 residents, both payloads, 32 MiB/s offered non-cache churn and application live-set inputs of 0/96/208/288 MiB. There are two counterbalanced passes, each with 12 warmups and eight measurements: **32 fresh worker JVMs**. These are candidate inputs, not a frozen protocol. A larger host does not automatically require a larger JVM heap.

The audit requires complete paired fingerprints, fixed heap evidence, matching histogram counts, measured post-GC occupancy, old/humongous-region evidence, achieved churn within ±10%, zero dropped demand, no host monitor failure and passing host screens. Independent occupancy replicas must stay within ±5 percentage points; adjacent levels must separate by at least five points. The 4-KiB Caffeine anchor must span low used heap (≤40%) through severe sustainable used heap (80–95%). Adjust candidate inputs in a **new attempt** if calibration fails; preserve the failed grid. Occupancy bands are backend-specific outcomes; both backends receive identical inputs.

Post-collection used heap and old-region capacity are not an exact live-object census. The parser excludes setup collections and concurrent-cycle durations from pause totals. It retains whole pause duration separately from pause time overlapping actual worker windows; GC and safepoint totals must not be added.

An interrupted calibration can resume completed blocks only when the source and all input arguments are unchanged:

```sh
python3 scripts/tailcache12_calibrate.py calibrate machine-b-calibration-001 --resume
```

Resumption verifies prior hashes and refuses to overwrite a partial existing block. A host-rejected grid remains suspended; use a new attempt after restoring a quiet host. Audit reconstructs decisions from raw data and exits nonzero for incomplete/rejected grids. Even a passing calibration keeps `campaignReady=false` until JIT/observer qualification and the eight-cell pilot pass. Automated pilot/campaign execution is not supplied by this delivery.

## Preserve and return evidence

Each attempt retains a source archive, Git identity/dirty state, commands, host samples and artifact hashes under `build/reports/tailcache12/`. Derived JSON/CSV can be replayed from raw inputs. Copy the entire attempt plus its manifest-linked sibling run directories before `clean` or moving machines. They are ignored by Git and are not included in this branch push.

```sh
mkdir -p evidence-archives
tar -czf evidence-archives/task12-machine-b-001.tar.gz build/reports/tailcache12
sha256sum evidence-archives/task12-machine-b-001.tar.gz
```

Use a new archive filename each time and store a copy outside the checkout. Bring back the JIT audit and calibration evidence before freezing the pilot/campaign protocol. See [the research plan](TAILCACHE_12_PLAN.md) for the remaining acceptance gates.
