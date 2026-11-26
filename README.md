# TailCache

TailCache is a Java 21 benchmark experiment comparing tail latency in Caffeine
(on heap) and in-memory Chronicle Map (off heap). The harness runs controlled
workloads and records per-fork latency distributions, allocation, and garbage
collection. It also supports separate diagnostics for file-backed Chronicle Map.

The research manuscript is distributed through Zenodo. This repository is the
companion research artifact: benchmark code, workload definitions, experimental
results, verification tools, and supporting documentation. The interactive
results are a data explorer, not a copy of the manuscript.

## Experiment questions and results

| Question | Result under the tested settings |
| --- | --- |
| **RQ1.** Does added application data cause a crossover in ordinary service p99 or p99.9? | No robust pressure-induced crossover was observed. Caffeine led at 4 KiB throughout the tested saturated-service matrix. |
| **RQ2.** Does the value size change the service-latency ranking? | At p99 and p99.9, Chronicle led at 256 B and Caffeine led at 4 KiB. This comparison covers one cache worker and the tested cache settings. |
| **RQ3.** Can the set of keys eligible for writes reverse scheduled-response p99.9 at the same write rate? | At 4 KiB, 5% writes, and 50,000 intended arrivals/s, Caffeine led with 2,048 eligible write keys and Chronicle led with all 32,768. The reversal repeated on two hosts and held at 100,000 arrivals/s on the second host with roughly 2,500 writes/s. |

Service latency measures the time to perform a benchmark operation, including
fresh value construction on writes. Scheduled response measures from the intended
arrival through completion, including time spent waiting for the worker. At 10%
and 20% writes in the follow-up, Chronicle led with the full write set and the
concentrated pairs were mixed. A separate four-seed sweep on the second host
bracketed a response p99.9 reversal between 1.25% and 1.5% writes; earlier
intermediate cells were mixed. These are workload-specific observations.

The saturated matrix retained all 48 first-pass pairs (36 warning-free, 37 in
the clean sensitivity view after one bounded retry); some high-pressure 4 KiB
cells had endogenous churn drops. Lower retained Java heap does not imply lower
process RSS, and ordinary Chronicle reads allocate materialized values. Both
split-write timing pilots failed their predeclared qualification gate, so
component-level `put()` costs remain unresolved. See the [claim-to-evidence map](docs/preprint/CLAIMS.md).

[Second-host results](docs/second-host-20261120/) ·
[Pop!_OS follow-up](docs/nov23-popos-followup/) ·
[Interactive results](output/html/tailcache-preprint-reader.html) ·
[Experiment status](docs/TAILCACHE_CURRENT_STATE.md)

## Run the benchmarks

From the default checkout, use Java 21 and Python 3.10+ to run the default suite.
Use a quiet native Linux host for comparisons intended to meet the host gates.

```sh
./gradlew --no-daemon tailCacheReproduce
```

Add `-PtailcacheSuite=locality` to run only the eight-JVM locality comparison,
or `-PtailcacheSuite=quick` for a diagnostic. Use
`-PtailcacheOut=results/my-replication` to select an output directory. Repeat
the same command to reuse verified completed forks when the bundle, configuration,
JDK, and host still match.
[Portable collection guide](docs/PORTABLE_EXPERIMENT.md) ·
[Evidence and offline verification](docs/EXPERIMENT_EVIDENCE.md)

## Methods and experiment records

- [Scope](docs/SCOPE.md), [methodology](docs/METHODOLOGY.md), and [experiment plan](docs/PLAN.md)
- [Original heap-pressure campaign](docs/TAILCACHE_12_FINAL_OUTCOME_REVIEW.md)
  and [acceptance record](docs/TAILCACHE_12_FINAL_ACCEPTANCE.json). The completed
  dataset supports an observer-conditional analysis. The unconditional protocol
  remains `NO_GO`.
- [Historical cliff diagnostic](docs/TAILCACHE_12_CLIFF_DIAGNOSTIC_AND_SYNTHESIS.md)
  uses synthetic arrival correction and includes a separate `getUsing()` arm.

## Benchmark modes

TailCache provides the portable experiment and two JMH validation harnesses.

### Portable experiment

The main comparisons use one cache worker, ordinary `get`, and fresh immutable
values on writes. Positive arrival rates measure responses against independently
scheduled arrivals. A zero arrival rate selects saturated, back-to-back service
measurement. See the [suite table](docs/PORTABLE_EXPERIMENT.md#run-from-a-fresh-checkout).

### Operation-level validation

`CacheSmokeBenchmark` validates individual `getHit`, `getMiss` and `putExisting` paths for Caffeine and Chronicle Map. It is used for adapter validation, allocation profiling and JFR diagnostics.

### Mixed-workload matrix

`CacheWorkloadBenchmark` adds the TailCache 05 factors:

| Factor | Values |
|---|---|
| Backend/storage mode | `CAFFEINE`, `CHRONICLE_IN_MEMORY`, `CHRONICLE_PERSISTED` |
| Payload size | `BYTES_256` (256 B), `KIB_4` (4 KiB) |
| Access distribution | `UNIFORM`, `ZIPFIAN` |
| Zipfian exponent | 0.99 initial value |
| Read/existing-key-put mix | `READ_95_WRITE_5`, `READ_70_WRITE_30` |
| Resident entries | 2,048 |
| Configured entry setting | 4,096 (`maximumSize` for Caffeine; `entries` target for Chronicle Map) |
| Deterministic trace | 100,000 operations from seed `0x5EED` |

The mixed trace is generated before measurement. Read/write counts are exact over a complete trace and key generation uses a separate deterministic random stream so changing the read/write ratio does not silently change the key sequence.

Writes overwrite existing keys using preallocated per-key replacement payloads. This avoids payload construction inside the benchmark and avoids collapsing many Caffeine entries onto one shared replacement object.

## Persisted Chronicle mode

`CHRONICLE_PERSISTED` uses `ChronicleMapBuilder.createPersistedTo(...)` with a temporary file created for the JMH trial. The cache is populated before measurement, then explicitly closed and the temporary map file/directory are deleted during trial teardown.

The persisted JMH path is intended to represent **warm steady-state mapped access**, not map-open time or deliberately cold page-fault behaviour. The TailCache 07 pilot loads and sweeps mapped pages before measurement, records the filesystem/storage environment and process fault/I/O counters, and keeps map reopen/first-touch timing in a separate diagnostic. The first pilot found major faults and unstable host conditions, so its persisted latencies are not reportable. See [TailCache 07](docs/TAILCACHE_07.md).

Persisted mode is also **not the same thing as a two-JVM experiment**. Multi-process sharing adds inter-process locking, coherence and scheduling effects and is kept as a separate secondary study.

## Concurrency semantics

The mixed-workload cache state is explicitly `Scope.Benchmark`, so all JMH workers share one cache instance. Each worker gets its own `Scope.Thread` trace cursor with a deterministic staggered starting offset.

That means `-t 16` in `CacheWorkloadBenchmark` is intentionally a **same-JVM shared-cache contention** run. This is different from the older `CacheSmokeBenchmark`, whose `Scope.Thread` state remains an operation-level validation harness and must not be reinterpreted as shared-cache contention by merely increasing its thread count.

## Reproducibility controls

The JMH validation harness prepares its keys, trace, and replacement values
before measurement. The portable experiment generates fresh values inside its
measured writes and keeps the offered application churn separate.

Chronicle Map is configured with fixed-size value layout through `constantValueSizeBySample(...)`, explicit `entries`, `maxBloatFactor(1.0)`, explicit `allowSegmentTiering(true)`, and `putReturnsNull(true)`. `maxBloatFactor(1.0)` does not mean segment tiering is impossible; tiering remains enabled for normal per-segment variance.

Chronicle vendor analytics is disabled in test and benchmark JVMs with:

```text
-Dchronicle.analytics.disable=true
```

so telemetry cannot create unrelated network/thread activity during the experiment.

## Project structure

```text
src/main/java/
├── cache/       shared cache API and backend adapters
└── workload/    deterministic workload and synthetic key/value generation

src/test/java/   correctness and determinism tests
src/jmh/java/    JMH state and benchmark methods
docs/            methodology and experiment notes
```

## Toolchain

- Java 21
- Gradle Wrapper 9.7.1
- Gradle Kotlin DSL
- Caffeine 3.2.4
- Chronicle Map 2026.1
- JMH 1.37
- JUnit Jupiter 6.1.3

Dependency and wrapper versions are pinned so benchmark runs remain reproducible.

## Build

Use the committed Gradle wrapper rather than a system Gradle installation:

```bash
./gradlew --version
./gradlew clean test
```

Chronicle Map on Java 21 requires module export/open flags. The Gradle test and benchmark runners provide the required JVM arguments; JMH inherits those arguments into its forked benchmark VMs.

## Smoke benchmarks

Operation-level harness smoke:

```bash
./gradlew jmhSmoke
```

TailCache 05 mixed-workload smoke with one worker:

```bash
./gradlew jmhWorkloadSmoke
```

Same mixed-workload matrix with 16 workers sharing one cache:

```bash
./gradlew jmhWorkloadShared16Smoke
```

The workload smoke tasks also export JMH JSON to:

```text
build/reports/jmh/workload-smoke-1t.json
build/reports/jmh/workload-smoke-16t.json
```

All smoke tasks deliberately use 1 warmup iteration, 1 measurement iteration, 1 fork and 300 ms windows. Their purpose is to validate harness behaviour and configuration expansion.

**Smoke numbers are not research results.**

## Backend validation smoke checks

TailCache has backend-specific allocation and JFR diagnostics:

```bash
./gradlew jmhCaffeineAllocSmoke
./gradlew jmhCaffeineJfrSmoke
./gradlew jmhChronicleAllocSmoke
./gradlew jmhChronicleJfrSmoke
```

The allocation smokes use JMH's GC profiler. The JFR smokes are for diagnostic stack/context inspection; their timings are profiler-perturbed and are not research results. See `docs/TAILCACHE_03.md`, `docs/TAILCACHE_04.md` and `docs/TAILCACHE_05.md` for interpretation limits.

Chronicle Map's primary adapter uses ordinary `get`. Ordinary Chronicle `get` materializes a Java value from off-heap entry storage; object-reuse alternatives such as `getUsing` are intentionally kept out of the primary parity path.

## Run JMH directly

The [Task 12 runbook](docs/TAILCACHE_12_RUNBOOK.md) records the original JMH and every-operation protocols. Use the [portable collection guide](docs/PORTABLE_EXPERIMENT.md) for new runs.

Run the benchmark suite:

```bash
./gradlew jmh
```

Or filter to one benchmark:

```bash
./gradlew jmh -PjmhInclude='.*CacheWorkloadBenchmark.*'
```

The benchmark classes declare 5 warmup iterations, 5 measurement iterations, 3 fresh JVM forks and sample-time measurements in nanoseconds as conservative direct-run defaults. These settings are not considered reportable until the harness floor, warmup stability, environment capture, occupancy semantics and experiment protocol are frozen.
