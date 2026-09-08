# TailCache 03 - Caffeine measured-path validation

## Goal

Establish a Caffeine baseline whose measured path is understood well enough to trust before expanding the benchmark matrix or interpreting latency differences.

## Measured-path decisions

- Benchmark keys are pre-boxed as `Long` objects during trial setup. The cache-operation timer therefore does not include synthetic `long` -> `Long` boxing allocation.
- Caffeine uses a manual cache with only `maximumSize` configured; there is no loader or async access path in the adapter.
- `getHit` and `getMiss` explicitly feed their results to JMH `Blackhole` so returned values cannot be optimized away.
- `putExisting` remains a `void` benchmark because the cache mutation itself is observable state; adding a validation `get` inside that benchmark would measure a different operation.
- Trial setup performs hit/miss sanity checks before measurement starts.

## Configuration logging

Each trial prints one `[TailCache][config]` line containing:

- backend and adapter name;
- backend-specific configuration;
- logical capacity and populated entries;
- payload size;
- trace size and fixed seed;
- the pre-boxed key representation.

This output should be retained alongside any smoke or reportable benchmark output.

## Caffeine correctness checks

The unit tests cover:

- miss before insertion;
- hit after insertion;
- overwrite semantics;
- clear semantics;
- `maximumSize` enforcement after Caffeine maintenance;
- reference-return behaviour for cached `byte[]` values;
- configuration-summary output.

The reference-return assertion is methodologically useful: normal Caffeine `get` returns the cached Java object, while Chronicle Map access may materialize a value across the off-heap serialization boundary.

## Validation commands

```bash
./gradlew test
./gradlew jmhCaffeineAllocSmoke
./gradlew jmhCaffeineJfrSmoke
```

All benchmark JavaExec tasks are pinned to the Java 21 toolchain so the JMH runner and its forks do not silently inherit a newer Gradle JVM.

## Validation status

### Allocation smoke - PASS

The Caffeine-only allocation smoke completed successfully on JDK 21.0.12.1. Normalized allocation remained sub-byte per operation across the smoke matrix:

| Operation | 256 B | 4 KiB |
|---|---:|---:|
| `getHit` | 0.438 B/op | 0.509 B/op |
| `getMiss` | 0.075 B/op | 0.075 B/op |
| `putExisting` | 0.326 B/op | 0.368 B/op |

This is consistent with the measured path not performing one fresh boxed-key or payload allocation per cache operation. These values are smoke diagnostics, not reportable performance results.

Occasional single GC events occurred in some 4 KiB smoke trials, but normalized allocation remained sub-byte/op. Do not attribute those collections to Caffeine's per-operation access path without profiler evidence.

### JFR smoke - RECORDING PASS / REPRESENTATIVE INSPECTION MOSTLY CLEAN

`jmhCaffeineJfrSmoke` completed successfully on JDK 21.0.12.1 and generated a separate `profile.jfr` under `build/reports/jmh/jfr/` for each Caffeine operation/payload combination.

The JFR profiler materially perturbs the smoke latency numbers, so those timings must not be compared to the non-profiled allocation smoke or used as research results. The recording is diagnostic only.

A representative 256 B `getHit` recording was inspected with `jfr summary` plus explicit event printing. The recording contained:

- 0 recorded `jdk.JavaMonitorEnter` events;
- 0 recorded `jdk.ClassLoad` events;
- 0 recorded `jdk.ObjectAllocationInNewTLAB` events;
- 0 recorded `jdk.ObjectAllocationOutsideTLAB` events;
- 0 recorded garbage-collection events;
- 2 `jdk.Compilation` events, both C2 compiling `java.util.concurrent.ForkJoinPool.scan` on a compiler thread rather than the TailCache/Caffeine measured path.

This representative check does not show an obvious cache-path locking, class-loading, compilation or GC confound.

The same recording also contains 9 `jdk.ObjectAllocationSample` events. Those sampled allocation events should be inspected once before closing TailCache 03 so their stack traces can be classified as benchmark/JFR/background activity or cache-path activity.

Useful final inspection command:

```bash
jfr print \
  --events jdk.ObjectAllocationSample \
  build/reports/jmh/jfr/io.github.enixes.tailcache.benchmark.CacheSmokeBenchmark.getHit-SampleTime-backend-CAFFEINE-payloadSize-BYTES_256/profile.jfr
```

Event counts alone are not a universal zero-allocation guarantee; the separate JMH GC-profiler result remains the quantitative allocation smoke check.

### Unit tests

A fresh `./gradlew test` result for this branch should be retained with the validation record if it has not already been run after the TailCache 03 changes.

## Interpretation guardrail

The short 1/1/1, 300 ms smoke runs exist to validate benchmark plumbing and measured-path behaviour. Their p50/p99/p99.9 values are not evidence about Caffeine's steady-state tail latency and must not appear in the eventual research conclusions.
