# Methodology

## 1. What is being compared

The primary experiment compares Caffeine and Chronicle Map through the same narrow adapter API using pre-boxed `Long` keys and fixed-size `byte[]` values. The goal is to measure observable cache-operation latency distributions under controlled synthetic workloads.

This is **not** a claim that the products have identical semantics. In particular:

- Caffeine is an on-heap cache with eviction and returns the cached Java object reference.
- Chronicle Map is an off-heap concurrent key-value store. Ordinary `get` crosses the serialization boundary and materializes a Java value from off-heap entry storage.
- Caffeine `maximumSize` and Chronicle Map `entries` are not equivalent capacity controls.
- Chronicle Map persisted mode is file-backed/memory-mapped; it is not equivalent to a two-JVM contention experiment and it must not be described as direct disk-I/O latency.

The common adapter therefore measures **end-to-end API access cost**, not an abstract hash lookup stripped of representation costs. A future Chronicle-specific `getUsing` experiment, if added, must be reported separately rather than silently substituted into the primary comparison. Byte-array values are treated as immutable by convention.

Within each benchmark trial every payload has one exact configured size. Chronicle Map is therefore configured with `constantValueSizeBySample(...)`, not `averageValueSize(...)`. This matches Chronicle's documented constant-size configuration path and avoids benchmarking a variable-size layout for a fixed-size workload.

Chronicle's `maxBloatFactor(1.0)` and `allowSegmentTiering(true)` are both frozen explicitly. A bloat factor of 1.0 must not be described as disabling tiering: Chronicle documents that individual segments can still tier because of normal hash-distribution variance. Vendor analytics is disabled in all test and benchmark JVMs with `-Dchronicle.analytics.disable=true` so telemetry cannot introduce unrelated benchmark activity.

## 2. Reproducibility rules

- Java version is pinned to 21 for the study.
- Dependency versions are pinned in `build.gradle.kts`.
- Workloads are generated from explicit fixed seeds.
- Synthetic keys and payload bytes are generated during benchmark setup, not inside measured operations.
- Benchmark setup generates the trace before measurement; random-number generation is not part of measured cache-operation latency.
- Keys are pre-boxed during setup so measured operations do not include synthetic `Long` boxing allocation.
- Mixed-workload key selection and read/write selection use separate deterministic random streams so changing the read/write ratio does not silently change the logical key sequence.
- The 95/5 and 70/30 mixes contain exact aggregate operation counts over a complete generated trace; the operation flags are deterministically shuffled.
- Mixed writes use one preallocated replacement payload per logical key, avoiding both measured allocation and the artifact of making many Caffeine entries point at one shared replacement object.
- Operation-level `CacheSmokeBenchmark` cursors reset at each JMH iteration.
- Mixed-workload `WorkloadCursorState` is per-thread and resets at each iteration; workers use deterministic staggered offsets over the shared immutable trace.
- Warmup, measurement and fork counts must be recorded with raw JMH output.
- Machine, OS, JVM, CPU topology, heap settings and relevant JVM flags must accompany reportable results.
- A benchmark campaign should use the same machine in as quiet a state as practical.
- Do not compare numbers collected under materially different thermal/power modes as if they were one experiment.
- Backend configuration summaries must be retained with raw results. They are experiment-relevant summaries, not claims to enumerate every internal library setting.
- Chronicle analytics must remain disabled for all benchmark forks.

## 3. Metrics

Primary latency metrics:

- median (p50);
- p95;
- p99;
- p99.9 where sample count supports it;
- maximum only as descriptive evidence, never as a stable estimator by itself.

Throughput can be retained as supporting context, but it is not the primary outcome.

Mixed-workload percentiles describe the **workload-level operation distribution**. They should not be mislabelled as read-only or write-only percentiles. Operation-specific hit/miss/update baselines remain separate measurements.

## 4. Initial factors

Start small. Candidate controlled factors for the main campaign:

- backend/storage mode: Caffeine / Chronicle Map in-memory / Chronicle Map persisted-warm;
- access distribution: uniform / Zipfian with an initial frozen exponent of 0.99;
- read/write mix: 95/5 and 70/30, with read-only operation-level baselines retained separately;
- value size: **256 B** and **4 KiB** initial payloads;
- concurrency: one worker and a candidate 16-worker same-JVM shared-cache level, subject to pilot stability;
- occupancy/working-set ratio: a small number of explicitly defined levels.

The current smoke state uses 2,048 resident entries with a shared configured entry setting of 4,096. This is useful for harness validation, but it is **not automatically the final occupancy protocol**. Before reportable runs, TailCache must explicitly decide how Chronicle Map's `entries` target and Caffeine's `maximumSize` should be related to the resident working set. That decision must be documented rather than inherited accidentally from the smoke harness.

Persisted Chronicle results must distinguish warm steady-state mapped access from cold/open/page-fault behaviour. Prepopulation before measurement is necessary but not by itself sufficient evidence that page faults/writeback cannot influence a run; that must be checked in the pilot and the filesystem/storage environment must be recorded.

Two-JVM sharing is a separate experiment because it adds inter-process locking, coherence and scheduler effects.

Do not create a combinatorial grid merely because parameters are available. Each factor retained in the reportable campaign must answer a specific hypothesis.

## 5. JMH scaffold and smoke warning

`CacheSmokeBenchmark` is an operation-level harness check. It uses `@State(Scope.Thread)`. Increasing its thread count creates independent per-worker caches and therefore must **not** be interpreted as shared-cache contention.

`CacheWorkloadBenchmark` uses a different ownership model. `CacheWorkloadState` is `@State(Scope.Benchmark)`, so all workers in a run share one cache instance; `WorkloadCursorState` remains `@State(Scope.Thread)` so trace progress does not require a global atomic counter in the measured path. Under this benchmark, `-t 16` is a deliberate same-JVM shared-cache contention configuration.

Both benchmark classes declare 5 warmup iterations, 5 measurement iterations and 3 JVM forks as conservative direct-run defaults. The Gradle smoke tasks override those settings to 1 warmup iteration, 1 measurement iteration and 1 fork, with 300 ms windows.

`jmhWorkloadSmoke` uses one worker. `jmhWorkloadShared16Smoke` uses 16 workers sharing the same benchmark-scoped cache. Both export JMH JSON for configuration/result inspection.

**Smoke numbers must never appear as research results.**

Profiler smoke runs are diagnostic as well. JFR perturbs latency and uses sampled/thresholded event streams; `-prof gc` is useful for normalized allocation but short smoke runs remain unsuitable for final tail-latency claims.

## 6. Chronicle Map sizing and robustness track

Sizing sensitivity is a secondary experiment and must remain separate from the primary latency comparison. Relevant controls include:

- configured `entries()` target;
- resident entry count / occupancy ratio;
- fixed value size and sizing mode;
- `maxBloatFactor` and segment-tiering policy;
- Chronicle Map version and JVM flags;
- resolved layout metadata such as segment/chunk information when it can be captured reliably;
- capacity headroom and insertion behaviour near configured limits;
- persisted filesystem/mount/device characteristics when file-backed mode is measured.

The primary fixed-size workload should use Chronicle's constant-size configuration. Deliberately perturbed or average-size configurations may be useful later as robustness checks, but they must be labelled as separate sizing experiments rather than mixed into the main comparison.

## 7. Negative-result policy

Keep and report:

- no meaningful difference;
- a result opposite the initial hypothesis;
- a benchmark configuration that proved invalid;
- instability or excessive variance;
- a sizing assumption that materially changes the result.

Invalid measurements should be excluded from conclusions but documented with the reason for exclusion.

## 8. Data restrictions

All workloads must be synthetic or derived from public information. Never copy XTP code, traces, customer data, schemas, log fragments, proprietary configuration values, or confidential workload statistics into TailCache.
