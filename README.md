# TailCache

**Tail-Latency Trade-offs in On-Heap and Off-Heap Java Caching**

TailCache is a reproducible Java 21 benchmarking project for studying the latency characteristics of **on-heap and off-heap caching** under controlled workloads.

The initial comparison uses:

- **Caffeine** for on-heap caching
- **Chronicle Map** for off-heap storage
- **JMH** for measurement
- deterministic synthetic workloads so both backends see the same inputs

The project focuses on **latency distributions**, especially tail latency, rather than headline throughput alone.

## What TailCache measures

TailCache is designed to answer questions such as:

- How do on-heap and off-heap caches differ for cache hits and misses?
- How does payload size affect operation latency?
- How stable are p50, p95, p99 and p99.9 latencies across repeated runs?
- What trade-offs appear between direct on-heap access and off-heap value materialization?

The smoke harness keeps the working set below the configured entry setting so validation runs avoid eviction/capacity exhaustion. The reportable experiment will freeze backend-specific occupancy semantics explicitly before comparing latency distributions, because Caffeine `maximumSize` and Chronicle Map `entries` are not equivalent controls.

## Current benchmark model

The initial harness covers:

| Factor | Values |
|---|---|
| Backend | `CAFFEINE`, `CHRONICLE_MAP` |
| Payload size | `BYTES_256` (256 B), `KIB_4` (4 KiB) |
| Resident entries | 2,048 |
| Configured entry setting | 4,096 (`maximumSize` for Caffeine; `entries` target for Chronicle Map) |
| Deterministic trace | 100,000 logical key selections |
| Operations | `getHit`, `getMiss`, `putExisting` |

Keys, values and access traces are generated before measurement. Benchmark methods therefore avoid random-number generation and payload construction in the measured path. Within a trial, every `byte[]` payload has the exact configured size.

## Project structure

```text
src/main/java/
├── cache/       shared cache API and backend adapters
└── workload/    deterministic workload and synthetic key/value generation

src/test/java/   correctness and determinism tests
src/jmh/java/    shared JMH state and benchmark methods
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

Chronicle Map on Java 21 requires module export/open flags. The Gradle test and benchmark runners provide the required JVM arguments; JMH then inherits those arguments into its forked benchmark VMs.

## Smoke benchmark

Run:

```bash
./gradlew jmhSmoke
```

The smoke suite runs all current backend/payload combinations with a deliberately short configuration:

- 1 warmup iteration
- 1 measurement iteration
- 1 JVM fork
- 300 ms per iteration

Its purpose is to verify that the benchmark harness works end to end.

**Smoke numbers are not intended as benchmark results.**

## Backend validation smoke checks

TailCache has backend-specific allocation and JFR diagnostics:

```bash
./gradlew jmhCaffeineAllocSmoke
./gradlew jmhCaffeineJfrSmoke
./gradlew jmhChronicleAllocSmoke
./gradlew jmhChronicleJfrSmoke
```

The allocation smokes use JMH's GC profiler. The JFR smokes are for diagnostic stack/context inspection; their timings are profiler-perturbed and are not research results. See `docs/TAILCACHE_03.md` and `docs/TAILCACHE_04.md` for backend-specific interpretation limits.

Chronicle Map's primary adapter uses ordinary `get`, fixed-size value configuration via `constantValueSizeBySample`, explicit `entries`, `maxBloatFactor(1.0)`, and `putReturnsNull(true)`. Ordinary Chronicle `get` materializes a Java value from off-heap entry storage; object-reuse alternatives such as `getUsing` are intentionally kept out of the primary parity path.

## Run JMH directly

Run the benchmark suite:

```bash
./gradlew jmh
```

Or filter to one benchmark:

```bash
./gradlew jmh -PjmhInclude='.*CacheSmokeBenchmark.getHit.*'
```

The benchmark class currently declares:

- 5 warmup iterations
- 5 measurement iterations
- 3 fresh JVM forks
- sample-time measurements in nanoseconds

These settings establish a reusable baseline for the larger experiment matrix that will follow. They are not considered reportable until the harness floor, warmup stability, environment capture, and experiment protocol are frozen.
