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
python3 scripts/tailcache12.py jit machine-b-jit-001 --warmups 60
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

The candidate full calibration is (use the independently qualified warmup duration):

```sh
python3 scripts/tailcache12_calibrate.py calibrate machine-b-calibration-001 --warmups 60
python3 scripts/tailcache12_calibrate.py audit machine-b-calibration-001
```

Defaults are a fixed 512 MiB heap, 32,768 residents, both payloads, 32 MiB/s offered non-cache churn and application live-set inputs of 0/96/208/288 MiB. Two counterbalanced passes now calibrate **both recorders independently: 64 fresh worker JVMs**. Every-operation timing and separately logged SampleTime retain different harness footprints; their occupancy bands remain separate. The SampleTime calibration adds G1 logs and no JMH profiler. Unprofiled primary SampleTime remains separate. These are candidate inputs, not a frozen protocol. Sixty warmups passed the revised WSL harness's complete independent compiler screens in both channels; actual larger-pressure forks still require their own counters and quality checks. The CLI default of 12 is the plan's minimum, not a qualification decision. Requalify a different host or changed measurement harness.

The audit requires complete paired fingerprints, fixed heap evidence, matching histogram counts, measured post-GC occupancy, old/humongous-region evidence, achieved churn within ±10%, zero dropped demand, no host monitor failure and passing host screens. Independent occupancy replicas must stay within ±5 percentage points; adjacent levels must separate by at least five points. The 4-KiB Caffeine anchor must span low used heap (≤40%) through severe sustainable used heap (80–95%). Adjust candidate inputs in a **new attempt** if calibration fails; preserve the failed grid. Occupancy bands are backend-specific outcomes; both backends receive identical inputs.

Post-collection used heap and old-region capacity are not an exact live-object census. The parser excludes setup collections and concurrent-cycle durations from pause totals. It retains whole pause duration separately from pause time overlapping actual worker windows; GC and safepoint totals must not be added.

An interrupted calibration can resume completed blocks only when the source and all input arguments are unchanged:

```sh
python3 scripts/tailcache12_calibrate.py calibrate machine-b-calibration-001 --warmups 60 --resume
```

Resumption verifies prior hashes and refuses to overwrite a partial existing block. A host-rejected grid remains suspended; use a new attempt after restoring a quiet host. Audit reconstructs decisions from raw data and exits nonzero for incomplete/rejected grids. Full calibration also checks actual timing, per-iteration compiler counters, runtime/workload identity and post-trial totals. Even a passing calibration keeps `campaignReady=false` until JIT/observer qualification and the eight-cell pilot pass.

Prospective CPU-only retry support is explicit opt-in for a **new** calibration: `--host-cpu-retries 2 --host-cpu-retry-budget 8`. Read [the calibration retry protocol](TAILCACHE_12_CALIBRATION_RETRY_PROTOCOL.md) before use. It keeps 64 logical slots and all raw candidates, with at most 72 total JVM attempts. Only a sole Windows root-CPU rejection may receive a bounded replacement after a separately retained/replayed quiet preflight; other failures and exhausted budgets stop collection. First quality-passing selection never compares latency. The hashed declaration and candidate order are audited, and old attempts cannot acquire this policy retrospectively. The default remains stop-at-failure. Copy the complete attempt, including nested `retry-preflights/`, plus its manifest-linked raw sibling directories. This is calibration-only; primary retry rules remain to be frozen after pilot review.

## Run the guarded pilot

`scripts/tailcache12_pilot.py` supplies a paired, counterbalanced eight-cell pilot. It requires passing functional, complete two-order JIT and both-recorder calibration attempts with matching measurement sources and warmup duration. Measurement identity covers Java workload/JMH sources, Gradle build/wrapper, the core driver and native host observer. Analysis, tests and documentation may evolve; full snapshots and replay hashes remain retained. Resuming an individual attempt still requires its complete source hash to remain unchanged. The launcher refuses a missing or failed prerequisite, retains immutable source/qualification references and stops on a quality failure.

```sh
python3 scripts/tailcache12_everyop_jit.py run machine-b-everyop-jit-001 --warmups 60
python3 scripts/tailcache12_pilot.py pilot machine-b-pilot-001 --functional machine-b-functional-001 --jit machine-b-jit-001 --everyop-jit machine-b-everyop-jit-001 --calibration machine-b-calibration-001
python3 scripts/tailcache12_pilot.py audit machine-b-pilot-001
```

The pilot schedules 160 fresh worker JVMs: two orders, three forks per primary channel/condition and one supporting diagnostic fork per order/condition. The primary channels are unprofiled SampleTime and every-operation timing. Throughput, allocation/GC, separately logged SampleTime pressure checks and compiler diagnostics remain descriptive support. Audit reconstructs fork percentiles, paired ratios and provisional variance screens. It always keeps `campaignReady=false`: observer coherence, exposure, variance and retry rules must be reviewed and frozen before implementing/running the confirmatory campaign. Pilot data cannot enter that campaign.

Every-operation compiler qualification uses eight separate XML-enabled JVMs, both payloads/backends in two orders, matching the calibrated resident count, heap and churn controls. These diagnostic forks cannot supply primary latency endpoints. The pilot requires this complete repeated screen in addition to JMH's compiler screen and actual per-fork counters. `tailcache12_everyop_jit.py audit <attempt-id>` replays its source/artifact, timing, workload, histogram, GC, churn, host and compiler checks.

For WSL, keep `TAILCACHE_REQUIRE_WINDOWS_HOST=1` and `TAILCACHE_WINDOWS_HOST_FILE` pointed at the session's append-only native monitor history. `scripts/windows_host_monitor.ps1` is the native observer; `windows_cpu_diagnostic.ps1` is separate process attribution and must not run alongside primary evidence collection. `python3 scripts/tailcache12_quiet.py machine-b-quiet-001` records a bounded preflight requiring 60 consecutive seconds under the full host screen. A preflight pass never replaces per-block monitoring. Do not disable system services to force acceptance.

Observer v5 appends authoritative history before attempting the optional atomic snapshot. A reader blocking snapshot replacement (sharing/lock errors 32/33) produces a warning while fresh history continues; other I/O errors remain fatal. Native diagnostic readers permit read/write/delete sharing. `scripts/test_windows_host_monitor.ps1 -OutputDirectory <new-absolute-folder>` verifies continued fresh history under a forced snapshot lock, recovery and clean shutdown. Check the append-only history for freshness; a stale optional snapshot alone is not evidence that the authoritative observer died. V5 changes measurement-source identity and needs fresh matched qualification; historical v3/v4 evidence retains its original rules and decisions.

The optional controller launch guard uses `TAILCACHE_CONTROLLER_ANCHOR_UNIX_SECONDS` and a default 900-second period. It waits outside each block's host sampler until at least 120 seconds after a planned check-in and avoids starting within at least 180 seconds before the next one (expanded for estimated invocation duration). Retained invocation metadata includes the anchor, guard windows, estimated duration, actual launch and wait. Keep the same schedule for all conditions and preserve the declared order. This prospective procedure leaves host/compiler limits unchanged; an actual overlap or noise still rejects the block. The helper is part of measurement-source identity v2, so earlier v1 archives cannot qualify a guarded run. Record the anchor and complete documentation/automation work before a fresh quiet preflight. Do not perform coordination during timing.

## Preserve and return evidence

Each attempt retains a source archive, Git identity/dirty state, commands, host samples and artifact hashes under `build/reports/tailcache12/`. Derived JSON/CSV can be replayed from raw inputs. Copy the entire attempt plus its manifest-linked sibling run directories before `clean` or moving machines. They are ignored by Git and are not included in this branch push.

```sh
mkdir -p evidence-archives
tar -czf evidence-archives/task12-machine-b-001.tar.gz build/reports/tailcache12
sha256sum evidence-archives/task12-machine-b-001.tar.gz
```

Use a new archive filename each time and store a copy outside the checkout. Bring back the JIT audit and calibration evidence before freezing the pilot/campaign protocol. See [the research plan](TAILCACHE_12_PLAN.md) for the remaining acceptance gates.
