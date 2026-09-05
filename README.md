# TailCache

**Tail-Latency Trade-offs in On-Heap and Off-Heap Java Caching**

TailCache is a small, reproducible Java 21 benchmark study comparing an on-heap cache (Caffeine) with an off-heap key-value store used as a cache substrate (Chronicle Map), with emphasis on latency distributions rather than headline throughput.

## Research question

Under controlled Java workloads, what latency and tail-latency trade-offs appear when the same logical key/value working set is served from Caffeine versus Chronicle Map, and how sensitive is Chronicle Map to sizing assumptions?

The project intentionally separates two questions:

1. **Primary study:** Caffeine vs Chronicle Map latency under capacity-safe, deterministic workloads.
2. **Upstream contribution:** reproduce and characterize Chronicle Map sizing fragility related to [OpenHFT/Chronicle-Map#533](https://github.com/OpenHFT/Chronicle-Map/issues/533).

Eviction-policy simulation is secondary and may be cut entirely.

## Non-goals

No UI, Spring Boot, cloud deployment, custom ML eviction policy, proprietary XTP code, or proprietary XTP data. Negative and unsuccessful results are part of the record and must not be discarded because they are inconvenient.

## Toolchain

- Java 21
- Gradle Kotlin DSL
- Caffeine 3.2.4
- Chronicle Map 2026.1
- JMH 1.37
- JUnit Jupiter 6.1.3

The dependency versions are pinned intentionally. Upgrade only as an explicit experimental decision, not casually during a benchmark campaign.

## Repository layout

```text
src/main/java/   cache abstraction, adapters, deterministic workload model
src/test/java/   contract and determinism tests
src/jmh/java/    JMH benchmarks
docs/            scope, methodology and time budget
```

## Build

This repository targets Gradle 9.7.1. Generate the standard wrapper once after cloning if it is not present:

```bash
gradle wrapper --gradle-version 9.7.1
./gradlew test
```

Chronicle on Java 21 requires module export/open flags. The Gradle `test`, `jmh`, and `jmhSmoke` tasks provide the required flags. If you run tests or main classes directly from an IDE, copy the flags from `build.gradle.kts` into the IDE run configuration.

## Smoke benchmark

```bash
./gradlew jmhSmoke
```

Or run the JMH suite/filter explicitly:

```bash
./gradlew jmh
./gradlew jmh -PjmhInclude='.*CacheSmokeBenchmark.getHit.*'
```

**Do not publish smoke numbers.** The smoke suite exists only to catch harness/configuration failures. Reportable experiments require the protocol in `docs/METHODOLOGY.md`.

## Current scope guard

Before adding a feature, ask whether it directly strengthens one of these deliverables:

- defensible Caffeine vs Chronicle Map tail-latency measurements;
- a reproducible Chronicle Map sizing experiment useful to issue #533;
- reproducibility/reporting for those experiments.

If not, it is scope creep until the primary study is complete.
