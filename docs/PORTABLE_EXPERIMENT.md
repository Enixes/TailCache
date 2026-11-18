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
python3 scripts/tailcache_portable.py reproduce --out results/replication-01
```

The command runs Gradle's Java test suite and the portable Python checks, saves a
copy of the exact runtime bundle, then runs the functional check, timer floor,
known-pause controls and diagnostic smoke before research collection. Use a quiet
Linux host for research measurements.

| Option | Research JVMs | Nominal workload time | Coverage |
|---|---:|---:|---|
| `--suite quick` | 0 | 8 seconds | Correctness, timing controls and four diagnostic workers |
| `--suite locality` | 8 | 21 minutes | Quick checks and update-locality replication |
| `--suite all` (default) | 84 | 3 hours 36 minutes | Quick checks, locality, write ratio and pressure/payload comparisons |

Times exclude dependency downloads, correctness tests, setup, timing controls and
evidence verification. Use `reproduce --plan` to inspect the full frozen design
before building or running. Add `--java /path/to/jdk-21/bin/java` if your default
Java is a different version.

The full suite uses one counterbalanced schedule. The shared 4 KiB, 5% write,
zero-ballast, 50k requests/s cell has the same seeds and inputs across all three
profiles, so the suite measures it once. The summary maps every profile to its
research cell numbers. Results are scoped to this suite's schedule and host.

Repeat the same command with the same output directory to resume. The frozen
bundle and completed forks are verified and reused. Choose a new directory for an
independent replication or a different suite. See the printed
`suite-analysis-*/SUMMARY.md` for completion status, usable pairs, warning counts
and links to the phase reports and point conclusions. `suite.json` records the
design, and `setup-*/` holds Python and Gradle check logs. A failed diagnostic phase
stops the suite before research. An interrupted worker without a complete receipt
needs a separate attempt, as described below.

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
| `write-ratio.json` | 20 | about 51 minutes | How do 0/0.5/1/2/5% updates change the tails at 4 KiB? |
| `rq-matrix.json` | 64 | about 164 minutes | Original payload/pressure questions, both saturated service and scheduled response |

The table lists stand-alone profiles for individual `run` commands. The full
reproduction command combines their research cells in its own schedule. All times
exclude setup, functional validation, four controls and post-run HDR verification.

Defaults: G1, 512 MiB initial/max heap, one worker, 32768 residents, uniform reads,
fresh immutable writes, 32 MiB/s independent churn, 120 s warmup (including four
1 s priming calls), 4 s conditioning, 30 s measurement. Each treatment uses the
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
fraction, including read-bracket uncertainty, not an application slowdown estimate.
Compiler time is approximate accumulated compiler-thread activity, not application
pause time. Missing telemetry is explicit. GC evacuation failures remain reported
pressure outcomes, not automatically disqualifying noise.

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
