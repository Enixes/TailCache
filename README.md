# TailCache

**Tail-Latency Trade-offs in On-Heap and Off-Heap Java Caching**

TailCache is a reproducible Java 21 benchmarking project for studying the latency characteristics of **on-heap and off-heap caching** under controlled workloads.

The primary comparison uses:

- **Caffeine** for on-heap caching
- **Chronicle Map in-memory** for off-heap storage
- **Chronicle Map persisted** for file-backed/memory-mapped off-heap storage
- **JMH** for measurement
- deterministic synthetic workloads so all modes see controlled inputs

The project focuses on **latency distributions**, especially tail latency, rather than headline throughput alone.

## What TailCache measures

TailCache is designed to answer questions such as:

- How do on-heap and off-heap caches differ for hits, misses and updates?
- How much of Chronicle Map's ordinary `get` cost comes from materializing a Java value from off-heap storage?
- Does warm, file-backed Chronicle Map behave differently from its non-persisted in-memory mode?
- How do uniform and skewed access distributions affect latency tails?
- How do 95/5 and 70/30 read/update mixes behave under one-thread and same-JVM shared-cache contention?

The smoke harness keeps the working set below the configured entry setting so validation runs avoid eviction/capacity exhaustion. The reportable experiment will freeze backend-specific occupancy semantics explicitly before comparing latency distributions, because Caffeine `maximumSize` and Chronicle Map `entries` are not equivalent controls.

## Benchmark modes

TailCache keeps two layers of benchmarks:

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
| Read/update mix | `READ_95_WRITE_5`, `READ_70_WRITE_30` |
| Resident entries | 2,048 |
| Configured entry setting | 4,096 (`maximumSize` for Caffeine; `entries` target for Chronicle Map) |
| Deterministic trace | 100,000 operations from seed `0x5EED` |

The mixed trace is generated before measurement. Read/write counts are exact over a complete trace and key generation uses a separate deterministic random stream so changing the read/write ratio does not silently change the key sequence.

Writes overwrite existing keys using preallocated per-key replacement payloads. This avoids payload construction inside the benchmark and avoids collapsing many Caffeine entries onto one shared replacement object.

## Persisted Chronicle mode

`CHRONICLE_PERSISTED` uses `ChronicleMapBuilder.createPersistedTo(...)` with a temporary file created for the JMH trial. The cache is populated before measurement, then explicitly closed and the temporary map file/directory are deleted during trial teardown.

The primary persisted result is intended to represent **warm steady-state mapped access**, not map-open time or deliberately cold page-fault behaviour. Prepopulation touches the mapped entry data before measurement; TailCache's pilot phase still has to verify page-fault/writeback effects and record the filesystem/storage environment before any persisted numbers become reportable.

Persisted mode is also **not the same thing as a two-JVM experiment**. Multi-process sharing adds inter-process locking, coherence and scheduling effects and is kept as a separate secondary study.

## Concurrency semantics

The mixed-workload cache state is explicitly `Scope.Benchmark`, so all JMH workers share one cache instance. Each worker gets its own `Scope.Thread` trace cursor with a deterministic staggered starting offset.

That means `-t 16` in `CacheWorkloadBenchmark` is intentionally a **same-JVM shared-cache contention** run. This is different from the older `CacheSmokeBenchmark`, whose `Scope.Thread` state remains an operation-level validation harness and must not be reinterpreted as shared-cache contention by merely increasing its thread count.

## Reproducibility controls

Keys, values, replacement payloads and access traces are generated before measurement. Benchmark methods therefore avoid random-number generation and payload construction in the measured path.

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

Run the benchmark suite:

```bash
./gradlew jmh
```

Or filter to one benchmark:

```bash
./gradlew jmh -PjmhInclude='.*CacheWorkloadBenchmark.*'
```

The benchmark classes declare 5 warmup iterations, 5 measurement iterations, 3 fresh JVM forks and sample-time measurements in nanoseconds as conservative direct-run defaults. These settings are not considered reportable until the harness floor, warmup stability, environment capture, occupancy semantics and experiment protocol are frozen.
