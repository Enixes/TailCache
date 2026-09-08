# TailCache 03 - Caffeine measured-path validation

## Goal

Establish a Caffeine baseline whose measured path is understood well enough to trust before expanding the benchmark matrix or interpreting latency differences.

**Status: COMPLETE**

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

Occasional single GC events occurred in some 4 KiB smoke trials, but normalized allocation remained sub-byte/op. The JFR inspection below did not show GC activity in the representative foreground-hit recording.

### JFR smoke - PASS

`jmhCaffeineJfrSmoke` completed successfully on JDK 21.0.12.1 and generated a separate `profile.jfr` under `build/reports/jmh/jfr/` for each Caffeine operation/payload combination.

The JFR profiler materially perturbs the smoke latency numbers, so those timings must not be compared to the non-profiled allocation smoke or used as research results. The recording is diagnostic only.

A representative 256 B `getHit` recording was inspected with `jfr summary` and targeted event printing. It contained:

- 0 recorded `jdk.JavaMonitorEnter` events;
- 0 recorded `jdk.ClassLoad` events;
- 0 recorded `jdk.ObjectAllocationInNewTLAB` events;
- 0 recorded `jdk.ObjectAllocationOutsideTLAB` events;
- 0 recorded garbage-collection events;
- 2 `jdk.Compilation` events, both C2 compiling `java.util.concurrent.ForkJoinPool.scan` on a compiler thread rather than the TailCache/Caffeine measured path.

The sampled allocation and park events were also classified:

- JFR internal string-pool allocation occurred on the Attach Listener;
- JMH `InputStreamDrainer`, result aggregation and worker-data capture produced framework allocations;
- process-reaper allocation/parking belonged to JVM process management;
- JMH result aggregation allocated `Double` objects after sampling;
- one small Caffeine-related allocation sample occurred on `ForkJoinPool.commonPool-worker-2` while draining Caffeine's read buffer (`BoundedLocalCache.drainReadBuffer` / `Node.inMainProbation`), not on the JMH benchmark worker executing the foreground lookup;
- `ThreadPark` events came from ForkJoinPool idle workers, JMH/main-thread coordination and the process reaper, not from the measured cache access path.

The Caffeine maintenance sample is worth retaining as part of the backend model: foreground reads can trigger or feed asynchronous maintenance work even when the measured lookup itself is essentially allocation-free. That background work is not a benchmark-plumbing confound, but it may matter later if TailCache studies whole-process CPU/allocation effects in addition to operation latency.

Together with the GC-profiler result, the representative recording provides no evidence of per-operation boxed-key allocation, payload copying, monitor contention, class-loading leakage or benchmark-path compilation in the Caffeine foreground `getHit` path.

This is not a universal zero-allocation guarantee; it is a validation that the current benchmark plumbing is not obviously injecting the allocations or synchronization artifacts TailCache 03 was designed to eliminate.

### Unit tests - PASS

A fresh `./gradlew test` completed successfully after the TailCache 03 changes.

## TailCache 03 conclusion

The Caffeine baseline is now sufficiently understood for the next phase:

- adapter semantics are tested;
- measured results are consumed correctly;
- benchmark keys are pre-boxed;
- backend configuration is logged;
- the JMH runner/forks are pinned to Java 21;
- foreground operations show sub-byte normalized allocation in the smoke profiler;
- representative JFR inspection found no obvious foreground allocation, locking, class-loading, GC or benchmark-path compilation confound;
- asynchronous Caffeine maintenance activity has been identified and documented rather than silently ignored.

TailCache 03 is complete. The next backend-validation slice should apply the same measured-path scrutiny to Chronicle Map before reportable Caffeine-vs-Chronicle comparisons begin.

## Interpretation guardrail

The short 1/1/1, 300 ms smoke runs exist to validate benchmark plumbing and measured-path behaviour. Their p50/p99/p99.9 values are not evidence about Caffeine's steady-state tail latency and must not appear in the eventual research conclusions.
