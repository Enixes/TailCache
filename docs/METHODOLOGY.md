# Methodology

## 1. What is being compared

The primary experiment compares Caffeine and Chronicle Map through the same narrow adapter API using `long` keys and byte-array values. The goal is to measure observable cache-operation latency distributions under controlled synthetic workloads.

This is **not** a claim that the products have identical semantics. In particular:

- Caffeine is an on-heap cache with eviction.
- Chronicle Map is an off-heap concurrent key-value store whose `entries()` and sizing parameters reserve capacity; it is not being treated as if it had Caffeine's eviction semantics.

Therefore primary measurements use a working set below configured capacity. Capacity exhaustion and sizing sensitivity belong to the separate #533 experiment.

A second semantic difference must remain visible in the analysis: Caffeine returns the cached Java object reference, while a normal Chronicle Map `get` crosses the off-heap serialization boundary and may materialize/copy the value. The common adapter therefore measures **end-to-end API access cost**, not an abstract "hash lookup" stripped of representation costs. A future Chronicle-specific `getUsing` experiment, if added, must be reported separately rather than silently substituted into the primary comparison. Byte-array values are treated as immutable by convention.

## 2. Reproducibility rules

- Java version is pinned to 21 for the study.
- Dependency versions are pinned in `build.gradle.kts`.
- Workloads are generated from explicit fixed seeds.
- Synthetic keys and payload bytes are generated during benchmark setup, not inside measured operations.
- Benchmark setup generates the trace before measurement; random-number generation is not part of measured cache-operation latency.
- The iteration cursor is reset at the start of every JMH iteration so each iteration starts from the same logical trace position.
- Warmup, measurement and fork counts must be recorded with raw JMH output.
- Machine, OS, JVM, CPU topology, heap settings and relevant JVM flags must accompany reportable results.
- A benchmark campaign should use the same machine in as quiet a state as practical.
- Do not compare numbers collected under materially different thermal/power modes as if they were one experiment.

## 3. Metrics

Primary latency metrics:

- median (p50);
- p95;
- p99;
- p99.9 where sample count supports it;
- maximum only as descriptive evidence, never as a stable estimator by itself.

Throughput can be retained as supporting context, but it is not the primary outcome.

## 4. Initial factors

Start small. Candidate controlled factors for the main campaign:

- backend: Caffeine / Chronicle Map;
- access distribution: uniform / hotspot;
- read ratio: read-only baseline, then one mixed ratio if time permits;
- value size: **256 B** and **4 KiB** initial payloads;
- occupancy/working-set ratio: safely below capacity, with a small number of levels.

The TailCache 02 smoke state uses 2,048 resident entries against a configured 4,096-entry capacity. This is intentionally capacity-safe so the smoke suite validates harness behaviour rather than eviction or sizing limits.

Do not create a combinatorial grid. Each added factor must answer a specific hypothesis.

## 5. JMH scaffold and smoke warning

`CacheSmokeBenchmark` is a harness check. The class declares 5 warmup iterations, 5 measurement iterations and 3 JVM forks as a conservative direct-run default. The Gradle `jmhSmoke` task deliberately overrides those settings to 1 warmup iteration, 1 measurement iteration and 1 fork, with 300 ms warmup/measurement windows.

The smoke matrix covers both backends and both payload sizes. Its purpose is to prove that setup, teardown, parameter expansion, Chronicle JVM flags and basic cache operations all work. **Smoke numbers must never appear as research results.**

## 6. Chronicle Map sizing / issue #533 track

The upstream track should vary Chronicle Map sizing assumptions systematically while holding the generated dataset constant. At minimum record:

- configured `entries()`;
- configured average value size;
- actual value-size distribution;
- insertion count at first failure, if any;
- exception/error text;
- Chronicle Map version and JVM flags;
- whether the result reproduces across clean runs.

Do not patch Chronicle Map before establishing a minimal, repeatable reproducer. A useful upstream contribution may be a reproducer/test, documentation clarification, diagnosis, or code fix; do not pre-commit to a code fix if evidence points elsewhere.

## 7. Negative-result policy

Keep and report:

- no meaningful difference;
- a result opposite the initial hypothesis;
- a benchmark configuration that proved invalid;
- failure to reproduce issue #533 under a stated configuration;
- instability or excessive variance.

Invalid measurements should be excluded from conclusions but documented with the reason for exclusion.

## 8. Data restrictions

All workloads must be synthetic or derived from public information. Never copy XTP code, traces, customer data, schemas, log fragments, proprietary configuration values, or confidential workload statistics into TailCache.
