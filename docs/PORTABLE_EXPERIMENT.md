# Collect the experiment on another machine

This package runs the unchanged continuous-stream in-memory workload used in the
18 November mechanism study. It needs **Python 3.10+ and Java 21** on the target.
Python has no third-party dependencies. Gradle, a checkout and network access are
needed only to build the bundle. Keep the experimental heap at 512 MiB when moving
to a larger host: more host RAM is headroom, not a reason to alter the treatment.

Linux is the reference collection platform. The launcher avoids systemd, sudo,
absolute Java paths and historical build directories. Windows/macOS paths and OS
locks are supported by the Python launcher, but native Chronicle compatibility and
collection on those systems have not been validated here. Their host monitoring is
**diagnostic**; missing sensors never silently establish warning-free evidence.

## Run from a fresh checkout

From the repository root, the full reproduction takes one command.

```sh
./gradlew --no-daemon tailCacheReproduce
```

Gradle runs the Java unit tests and builds the runtime bundle. The runner checks
its own scheduling, evidence validation and statistics, and saves the JUnit XML
and Python test log with the bundle. It runs the Java functional check, timer floor,
known-pause controls and diagnostic smoke before research collection.
Use a quiet Linux host for research measurements.

| Option | Research JVMs | Nominal workload time | Coverage |
|---|---:|---:|---|
| `-PtailcacheSuite=quick` | 0 | 8 seconds | Correctness, timing controls and four diagnostic workers |
| `-PtailcacheSuite=locality` | 8 | 21 minutes | Quick checks and update-locality replication |
| `-PtailcacheSuite=write-ratio` | 20 | 51 minutes | Response at 0%, 0.5%, 1%, 2%, and 5% writes |
| `-PtailcacheSuite=locality-long` | 16 | 57 minutes | Update locality with four fresh seeds and 90-second measurement windows |
| `-PtailcacheSuite=locality-arrival-rate` | 32 | 82 minutes | Locality under heavier reads and at 5%, 10%, and 20% writes |
| `-PtailcacheSuite=rq-matrix` | 64 | 2 hours 44 minutes | Payload and ballast under saturated service and fixed arrivals |
| `-PtailcacheSuite=saturated-write-pressure` | 96 | 4 hours 6 minutes | Saturated service at 256 B/4 KiB, 0/288 MiB, and 1%/5%/10% writes |
| `-PtailcacheSuite=write-transition` | 48 | 2 hours 3 minutes | Fixed-arrival response from 0.5% to 2% writes with four fresh seeds |
| `-PtailcacheSuite=split-write-timing` | 16 | 62 minutes including pilot | Separate fresh-value construction from the cache write at 256 B and 4 KiB |
| `-PtailcacheSuite=all` (default) | 84 | 3 hours 36 minutes | Quick checks, locality, write ratio and pressure/payload comparisons |

Times exclude dependency downloads, correctness tests, setup, timing controls and
evidence verification. Use `./gradlew -q tailCacheReproductionPlan` to print the
design and add `-PtailcacheSuite=quick` or `-PtailcacheSuite=locality` to preview
those profiles. Gradle selects the Java 21 toolchain. Use `gradlew.bat` on Windows.
Set `-PtailcachePython=/path/to/python` to select an alternate Python executable.

The default result directory is `results/replication-01`. For example, run the
diagnostic suite in its own directory with
`./gradlew --no-daemon tailCacheReproduce -PtailcacheSuite=quick -PtailcacheOut=results/smoke-01`.

Run each follow-up independently from a checkout with Java 21 and Python
available. Choose a distinct output directory for each new host.

```sh
./gradlew --no-daemon tailCacheReproduce -PtailcacheSuite=write-ratio -PtailcacheOut=results/write-ratio-01
./gradlew --no-daemon tailCacheReproduce -PtailcacheSuite=locality-long -PtailcacheOut=results/locality-long-01
./gradlew --no-daemon tailCacheReproduce -PtailcacheSuite=rq-matrix -PtailcacheOut=results/rq-matrix-01
```

The full suite uses one counterbalanced schedule. The shared 4 KiB, 5% write,
zero-ballast, 50k requests/s cell has the same seeds and inputs across all three
profiles, so the suite measures it once. The summary maps every profile to its
research cell numbers. Results are scoped to this suite's schedule and host.
The longer locality profile has its own seeds and timing and runs separately.

The saturated write-pressure and paced write-transition profiles use a 2%
whole-host CPU bound. After the first pass, each profile allows one retry of
both backends for up to four seed/cell pairs. Eligibility requires two complete
forks and warnings limited to CPU interference or observer coverage. GC, JIT,
churn and failed workloads stay in the original evidence. Selection follows the
frozen schedule order and uses no measured latency. The original reports keep
all first-pass results. The separate clean sensitivity view uses an original
warning-free pair or its warning-free retry, once per seed and cell. Both
profiles together allow at most 16 retry JVMs, about 41 timed minutes.

```sh
./gradlew --no-daemon tailCacheReproduce -PtailcacheSuite=saturated-write-pressure -PtailcacheOut=results/saturated-write-pressure-01
./gradlew --no-daemon tailCacheReproduce -PtailcacheSuite=write-transition -PtailcacheOut=results/write-transition-01
```

Repeat the same command with the same output directory to resume. The frozen
bundle and completed forks are verified and reused. Choose a new directory for an
independent replication or a different suite. See the printed
`suite-analysis-*/SUMMARY.md` for completion status, usable pairs, warning counts
and links to the phase reports and point conclusions. `suite.json` records the
design, and `setup-*/` holds Python and Gradle test evidence. A failed diagnostic phase
stops the suite before research. An interrupted worker without a complete receipt
needs a separate attempt, as described below.

Gradle waits while the runner collects the measurements. For a dedicated run with
Gradle exited during collection, use
`python3 scripts/tailcache_portable.py reproduce --out results/replication-01`
from the checkout. The standalone ZIP can run the same suite with
`python3 tailcache.py reproduce --out ../results/replication-01` after extraction.

## Split write timing on the Pop!_OS host

Use the Ryzen 7 5800X Pop!_OS host from the saturated matrix, with the original
Temurin 21.0.13+9 JDK, G1 settings, and native Linux monitoring. Use Python 3.10
or later. Run directly on the quiet host with stable power and cooling. The
runner records the actual JDK and host identity. Confirm Gradle selects the
same Java 21 toolchain shown by `java -version` before starting.

```sh
./gradlew -q tailCacheReproductionPlan -PtailcacheSuite=split-write-timing
./gradlew --no-daemon tailCacheReproduce -PtailcacheSuite=split-write-timing -PtailcacheOut=results/split-write-popos-01
```

The second command builds, tests, qualifies, collects, and reports in order.
There are 120 s of warmup, 4 s of conditioning, and 30 s of measurement per
pilot or research fork. Budget 65–75 minutes with dependencies cached. A
single eligible research retry pair can add another 5–6 minutes.

| Stage | Work | Advance when |
|---|---|---|
| Build and smoke | JVM and launcher tests, functional equivalence check, timer floor and injected pause, four short smoke forks | Existing diagnostic checks pass |
| Instrumentation pilot | 4 KiB, two fresh seeds, both backends, original and split timings, eight JVMs | All pairs are complete and warning-free. Per seed and backend, throughput and combined p99.9 stay within 10%, and update p99.9 within 15%. The Chronicle/Caffeine combined p99.9 ratio changes by at most 5% per seed. |
| Research | 256 B and 4 KiB, four fresh seeds per payload, both backends, 16 JVMs | Forks are reconciled against raw histograms and logical replay. At most one eligible research pair is repeated for external observer noise. |
| Interpretation | Compare the construction, cache write, and original operation distributions by payload | Keep pilot diagnostic. Qualify the research direction by clock resolution, tail support, and agreement across seeds and the warning-free sensitivity view. |

Both workloads have 32,768 residents, uniform reads, 5% nominal writes across
the full key set, zero added heap ballast, 32 MiB/s offered churn, a fixed 512 MiB
heap, and a 12-CPU JVM budget. Saturated backends can complete different prefixes
of the same seeded operation stream. Each overwrite still creates a new array.
The `write-value-construction` interval covers allocation and filling. The
`write-cache-put` interval covers the adapter call, including the library's
copy or update work. Both durations can include pauses that occur during the
interval. The original operation timer retains both costs and any scheduled
response channel retains its original endpoint. These profiles are saturated.

The added histograms are updated after the original operation end timestamp.
The pilot measures the aggregate effect of the extra clock reads and recording
on the running worker. Each split fork also measures 4,096 back-to-back clock
read intervals outside the workload. A split p99 closer than four times the
clock p99 is flagged, and split endpoints with inadequate resolution or tail
support remain unresolved. Treat these comparisons as direct measurements of
each stage. Percentiles cannot be subtracted to recover a stage's latency.
Keep the 30-second windows and report the observed write count for each fork.
The previous saturated 4 KiB runs at 5% writes and zero ballast recorded
about 1.5–2.9 million writes per fork. The split run reports its own counts
and uses them to check percentile support.

Open the printed `suite-analysis-*/SUMMARY.md`. The pilot links to
`write-timing-qualification.json` with the per-seed timing shifts and gate
result. The research report includes each endpoint's paired ratios,
`point-conclusions.json`, and `percentiles.csv`. Check p99 and p99.9 first.
If the clean directions vary or the timer floor dominates, report the affected
endpoint as inconclusive. The 288 MiB pressure condition and the first-host
i7 are follow-up confirmation if a new claim requires them.

If the pilot fails, the command stops before research and retains all diagnostic
forks. Keep the failure evidence and investigate the recorded timing shift or
warning before planning a fresh attempt. Repeating the identical command reuses
verified sealed slots. An unsealed interrupted slot stops the resume, as in the
other portable suites. Preserve that attempt and its completed slots before
planning any recollection.

### Use in the preprint

After the pilot passes and the research forks are reconciled, use the split
research cohort as the primary evidence for the 256 B and 4 KiB write-cost
comparison. Build the comparison table from that one cohort. Show fresh-value
construction and adapter `put()` separately, alongside read-only and whole-
operation timings from the same forks. State the direction at each endpoint
with its clock, tail and warning checks. Keep mixed or unresolved findings
visible.

The split cohort covers 5% writes at zero added ballast. Keep the original
saturated matrix as evidence for the broader pressure and write-rate claims.
Keep the two-host scheduled-response locality reversal and the G1, write-rate
bracket, and memory findings tied to their own cohorts. The instrumentation
pilot serves as qualification evidence.

## Optional follow-up under heavier reads and writes

Test whether the 4 KiB scheduled-response p99.9 locality reversal persists
when read demand or write demand increases. Use the same Pop!_OS host and
runtime. Run the split-write experiment first and review its results before
scheduling this independent follow-up.

```sh
./gradlew -q tailCacheReproductionPlan -PtailcacheSuite=locality-arrival-rate
./gradlew --no-daemon tailCacheReproduce -PtailcacheSuite=locality-arrival-rate -PtailcacheOut=results/locality-arrival-popos-01
```

Use each setting below with 2,048 and 32,768 eligible write keys.

| Setting | Arrivals/s | Writes | Nominal writes/s |
|---|---:|---:|---:|
| Shared baseline | 50,000 | 5% | 2,500 |
| Heavier reads | 100,000 | 2.5% | 2,500 |
| Intermediate write mix | 50,000 | 10% | 5,000 |
| Heavier write mix | 50,000 | 20% | 10,000 |

Compare heavier reads against the baseline to add about 50,000 reads/s
at matched nominal write intensity. Compare 5%, 10%, and 20% at the same
arrival rate to step from 2,500 to 5,000 to 10,000 nominal writes/s.
Read traffic decreases from about 47,500 to 45,000 to 40,000 reads/s across
those three settings. Check achieved writes per second from the measurement
windows. Use 4 KiB values, zero ballast, and the same heap and churn settings
as the second-host locality experiment.

Use two fresh paired seeds per cell, 32 research JVMs in total. Both
comparisons use the same contemporaneous baseline. Allow 85–95 minutes
with dependencies cached, plus about five minutes for at most one eligible
external-noise retry pair. Use scheduled-response p99.9 as the primary
endpoint. Compare which backend wins at both write-set sizes within each
setting, then examine achieved writes, worker allocation, GC pauses, and
backlog. Report a censored arm as a completion failure and keep its evidence.
The two-seed results describe the tested workloads. Choose additional
independent seeds only if the result changes the paper's interpretation.

## Build a ZIP for offline transfer

From a checkout with Java 21 available to Gradle:

```sh
python3 scripts/tailcache_portable.py pack --out build/distributions/tailcache-portable-v1.zip
```

Use a fresh output filename for a new bundle. Copy the ZIP to the target and extract
it. It contains the application, resolved dependency JARs, helpers, source snapshot,
configuration profiles and SHA-256 inventory. Java itself is not bundled; runtime
identity is recorded, hashed and frozen per run. Use the same Java vendor/build on
different hosts when comparing machine effects. Dependency versions are declared
in the included build file; bundle hashes identify the exact resolved bytes.

## Check, preview and run

From the extracted `tailcache-portable` directory:

```sh
python3 tailcache.py doctor --java /path/to/jdk-21/bin/java
python3 tailcache.py plan --config configs/locality.json
python3 tailcache.py run --config configs/smoke.json --out ../results/smoke-01 --java /path/to/jdk-21/bin/java
python3 tailcache.py run --config configs/locality.json --out ../results/locality-01 --java /path/to/jdk-21/bin/java
```

`--java` is optional if `JAVA_HOME` or PATH selects Java 21. On Windows use `python`
and the Java executable's Windows path. Unset injected Java option environment
variables before running. Run directly on the host, with ample free memory/disk,
stable power and cooling, and no other benchmarks. A per-user OS lock prevents two
portable runs from overlapping. It cannot coordinate unrelated benchmarking tools
or another user. The runner is sequential and does not need a desktop or browser.

| Profile | Research workload JVMs | Nominal workload time | Question |
|---|---:|---:|---|
| `smoke.json` | 0 (4 diagnostic workers) | about 8 seconds | Does this installation work? |
| `locality.json` | 8 | about 21 minutes | Does the 2048/32768 update-population response reversal replicate? |
| `locality-long.json` | 16 | about 57 minutes | Does that reversal hold over 90 seconds with four fresh seeds? |
| `write-ratio.json` | 20 | about 51 minutes | How do 0/0.5/1/2/5% updates change the tails at 4 KiB? |
| `rq-matrix.json` | 64 | about 164 minutes | Original payload/pressure questions, both saturated service and scheduled response |

The table lists stand-alone profiles for individual `run` commands. The full
reproduction command combines their research cells in its own schedule. All times
exclude setup, functional validation, four controls and post-run HDR verification.

Defaults: G1, 512 MiB initial/max heap, one worker, 32768 residents, uniform reads,
fresh immutable writes, 32 MiB/s independent churn, 120 s warmup with zero explicit
priming calls, 4 s conditioning, 30 s measurement. Zero priming follows the
retained mechanism selection. Each treatment uses the
same seeds in both backends. Backend order reverses across seed blocks, and cell
order is deterministically shuffled. The stream never resets or wraps between
phases. Chronicle uses ordinary `get`, with analytics disabled; its capacity/tiering
configuration is retained. Persisted warm/cold behavior and `getUsing` are outside
this package's scope.

`activeProcessorCount: 12` fixes the JVM processor budget to the prior mechanism
host's 12 available logical CPUs. Java's GC/compiler/common-pool ergonomics therefore
do not silently scale up on a larger host. A flags-only JVM records the actual
ergonomic settings before collection. This is a JVM budget, not CPU affinity or
physical-core isolation. A host with fewer available CPUs gets an oversubscription
warning; lower the budget in a new configuration if needed, and label that as a
different experiment. The original cohorts used host-default ergonomics; they are
not retroactively relabeled as explicitly pinned runs.

## Configure and resume

Copy a configuration **outside** the bundle before editing it. The strict schema
rejects unknown fields, duplicate cells/seeds, invalid timing and unbalanced seed
counts. Pressure, payload, write ratio, update population and arrival rate are
explicit cell fields. `qps: 0` selects saturated closed-loop service; positive QPS
selects fixed-arrival no-skip response and also records service. Keep at least two
distinct seeds and an even seed count. Four or more seeds are needed before the
report supplies an exploratory paired bootstrap interval.

Repeat the identical `run` command to resume. Completed slots are checked against
their retained raw hashes and reused. Bundle/config/JDK/host/resource changes stop
resumption; use a separate run directory on another machine. An interrupted slot
without a completed receipt blocks resumption so it cannot be silently replaced.
Archive that attempt and create an explicitly new cohort if recollection is needed.
Completed failed workers (including OOM/censoring) stay in the manifest; other
scheduled slots can complete, and failures appear in the final report. No hidden
replacement or pooling occurs. Disk/RAM/power preflight failures stop before a new
slot and preserve finished work.

## Results and research interpretation

Each versioned `analysis-*` directory contains `RESULTS.md`, `percentiles.csv` and
`results.json`, plus `point-conclusions.json`. Re-analyze offline, without Java or the original host:

```sh
python3 tailcache.py analyze --run ../results/locality-01 --out ../reports/locality-review-01
```

Reports include per-fork/per-channel p50, p99, p99.9, p99.99 and p99.999; HDR count
support; bounded probabilities above 100 microseconds, 1 ms and 10 ms; GC pauses,
safepoints, occupancy, allocation, compiler time, realized churn and observed RSS.
Compressed HDR is independently decoded after collection and compared to bins and
percentiles. Read/update histograms must exactly reconstruct service. Fixed-arrival
pairs must have identical per-phase operation/write counts and final version digest.
Independent logical replay also checks every fork's phase writes and final versions.
Offline analysis reconstructs histogram/GC/allocation statistics from raw files and
compares them with the cached receipts before reporting. Timer-floor and known-pause
controls are retained separately in the report; timings are never floor-subtracted.

Paired Chronicle/Caffeine ratios below 1 favor Chronicle. Summaries report the
median, geometric mean, range, log-ratio spread and an unadjusted sign test across
independent seeds. Bootstrap intervals are exploratory, emitted only for at least
four pairs. They are not proof of rare-tail precision; the report flags fewer than
20 expected observations beyond a quantile. Thirty seconds at 50k requests/s has
only about **15** beyond p99.999. Increase duration/seeds prospectively if that tail
is central. Do not pool operation histograms across forks, seeds or machines.
Per-backend fork spread (SD, coefficient of variation, median absolute deviation)
is also reported. No outlier is removed automatically. `point-conclusions.json`
records each cell's direction and matched-input reversal brackets along pressure,
payload, write ratio and update-population axes. A direction requires all planned
seed pairs to agree; this descriptive rule is not a significance test. Failed or
missing pairs remain unresolved, and warning/rare-tail limits stay attached.

Warnings are shown both inclusively and in a separate warning-free pair summary.
Host paging is screened over **conditioning through measurement**, using overlapping
1 Hz brackets; whole-lifetime events are retained separately. Host-wide counters do
not identify the worker as the cause. Outside CPU is a conservative whole-machine
fraction, including read-bracket uncertainty. On native Linux the worker waits
after timing, for up to five seconds, for an observer sample taken after measurement
while worker counters are still readable. Missing attribution uses a separate
warning and whole-machine bound. Missing system CPU counters within the protected
window also trigger a warning. CPU load concentrated
on one core can still be obscured by the whole-machine denominator.
Compiler time is approximate accumulated compiler-thread activity, not application
pause time. Missing telemetry is explicit. GC evacuation failures remain reported
pressure outcomes, not automatically disqualifying noise. If the stall-event detail
reaches its export cap, the report records the omitted events and a warning. The
full histogram remains usable after count validation.

Each cell gets its own service and response comparison. A winner at one cell or
percentile does not establish a universal crossover. Compare pressures within the
same payload/workload, and distinguish a baseline advantage from a pressure-induced
reversal. Keep host replications separate. This tool does not change historical
acceptance gates, reclassify older warning-bearing evidence or fit a new predictor.

## Files worth retaining

Keep the original ZIP and SHA-256, `run.json`, `qualification.json`, functional and
control receipts, every slot directory and every analysis directory. Raw evidence
is created exclusively, never overwritten. Storage/mount metadata, JDK identity,
source and resolved runtime hashes distinguish configuration from host differences.
The portable bundle is a reproducibility artifact, not a claim that different CPUs,
operating systems or JDK builds produce identical results.
