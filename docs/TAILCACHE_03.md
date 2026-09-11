# TailCache 03 - Caffeine measured-path validation

## Goal

Establish a Caffeine baseline whose measured path is understood well enough to trust before expanding the benchmark matrix or interpreting latency differences.

**Status: COMPLETE**

## Measured-path decisions

- Benchmark keys are pre-boxed as `Long` objects during trial setup. The cache-operation timer therefore does not include synthetic `long` -> `Long` boxing allocation.
- Caffeine uses a manual cache with only `maximumSize` explicitly configured; no loader or async cache API is used.
- Caffeine's executor is left at its library default, `ForkJoinPool.commonPool()`, and is recorded in the backend configuration summary because bounded-cache maintenance may run asynchronously there.
- `getHit` and `getMiss` explicitly feed their results to JMH `Blackhole` so returned values remain observable to the benchmark harness.
- `putExisting` remains a `void` benchmark because the cache mutation itself is observable state; adding a validation `get` inside that benchmark would measure a different operation.
- Trial setup performs hit/miss sanity checks before measurement starts.
- Chronicle-required module flags come from the shared Gradle `chronicleJvmArgs` list on the JMH runner tasks. With no benchmark-specific JVM arguments, JMH inherits the runner's input arguments into forked benchmark VMs, avoiding the duplicate flags that appeared when the same flags were also appended by `@Fork`.

## Configuration logging

Each trial prints one `[TailCache][config]` line containing:

- backend and adapter name;
- backend-specific configuration;
- logical capacity and populated entries;
- payload size;
- trace size and fixed seed;
- the pre-boxed key representation.

For Caffeine, the backend-specific summary includes both `maximumSize` and the effective default executor.

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

The reference-return assertion is methodologically useful: normal Caffeine `getIfPresent` returns the cached Java object, while Chronicle Map's ordinary `get` may materialize a value across the off-heap serialization boundary.

## Validation commands

```bash
./gradlew test --rerun-tasks
./gradlew jmhCaffeineAllocSmoke
./gradlew jmhCaffeineJfrSmoke
```

All benchmark JavaExec tasks use the Java 21 toolchain. The JMH fork inherits the runner JVM arguments when benchmark-specific JVM arguments are absent.

## Final validation - PASS

The final post-review validation completed successfully on JDK 21.0.12.1.

### Unit tests

`./gradlew test --rerun-tasks` completed successfully with all test tasks actually executed.

### Allocation smoke

The final Caffeine-only allocation smoke completed successfully on Java 21. Normalized allocation remained sub-byte per operation across the matrix:

| Operation | 256 B | 4 KiB |
|---|---:|---:|
| `getHit` | 0.336 B/op | 0.308 B/op |
| `getMiss` | 0.084 B/op | 0.088 B/op |
| `putExisting` | 0.279 B/op | 0.303 B/op |

This is the primary allocation evidence from TailCache 03. It is consistent with the measured path not performing one fresh boxed-key or payload allocation per cache operation. These values are smoke diagnostics, not reportable performance results.

Single GC events still occurred in some 4 KiB smoke trials, but normalized allocation remained sub-byte/op. The short smoke duration is not suitable for interpreting those isolated collections as steady-state behaviour.

The final JMH fork output showed each required Chronicle/JDK module flag once rather than duplicated, and the trial configuration line included `maximumSize=4096,executor=ForkJoinPool.commonPool(default)` as intended.

### JFR smoke

`jmhCaffeineJfrSmoke` completed successfully on Java 21 and generated a separate `profile.jfr` under `build/reports/jmh/jfr/` for all six Caffeine operation/payload combinations.

JMH 1.37's JFR profiler defaults to the JDK `profile` recording configuration unless another `configName` is supplied. That configuration is deliberately sampled and thresholded, so zero event counts must be interpreted in terms of what the profile actually enables:

- `jdk.ObjectAllocationInNewTLAB` and `jdk.ObjectAllocationOutsideTLAB` are not enabled at the default profile GC-detail level, so zero counts for those event types are not evidence of zero allocation;
- `jdk.ClassLoad` is disabled by default in the profile configuration, so a zero count does not establish that no class loading occurred;
- `jdk.JavaMonitorEnter` is thresholded at 10 ms in the profile configuration, so a zero count means no recorded monitor-enter blocking at or above that threshold, not "no contention" in general;
- `jdk.Compilation` is also thresholded in the profile configuration, so absence of a TailCache/Caffeine compilation event only applies to compilations that met the recording threshold.

A representative 256 B `getHit` recording inspected during validation showed:

- no recorded garbage-collection events during that recording window;
- no `jdk.JavaMonitorEnter` events crossing the profile threshold;
- two recorded C2 compilation events, both compiling `java.util.concurrent.ForkJoinPool.scan` on a compiler thread rather than TailCache or the foreground Caffeine lookup path;
- sampled allocation and park events that could be classified by thread and stack.

The sampled allocation/park events were:

- JFR internal string-pool allocation on the Attach Listener;
- JMH `InputStreamDrainer`, result aggregation and worker-data capture allocations;
- process-reaper allocation/parking belonging to JVM process management;
- JMH result aggregation allocating `Double` objects after sampling;
- one Caffeine-related allocation sample on `ForkJoinPool.commonPool-worker-2` while draining Caffeine's read buffer (`BoundedLocalCache.drainReadBuffer` / `Node.inMainProbation`), not on the JMH worker executing the foreground lookup;
- `ThreadPark` events from ForkJoinPool idle workers, JMH/main-thread coordination and the process reaper.

The Caffeine maintenance sample is part of the backend behaviour rather than benchmark plumbing. Foreground reads can feed asynchronous policy-maintenance work, and that background work may still influence whole-process CPU, allocation, cache pressure or tail behaviour even when it is not executed directly on the benchmark worker.

Taken together, the GC-profiler result and sampled JFR stacks provide no evidence of systematic per-operation boxed-key allocation or payload copying in the foreground Caffeine `getHit` path. They do **not** establish a universal zero-allocation or zero-contention guarantee.

The JFR profiler also perturbs latency, so JFR smoke timings must not be compared with non-profiled latency results or used as research results.

## Review corrections

The review pass made the following corrections before completion:

- removed duplicate Chronicle/JDK module flags from `@Fork`; the shared Gradle `chronicleJvmArgs` list remains the source for JMH runner arguments and JMH inherits them into forks;
- added Caffeine's default `ForkJoinPool.commonPool()` executor to configuration logging;
- corrected JFR interpretation so disabled or thresholded event types are not treated as proof of absence;
- aligned the README and delivery plan with the committed Gradle 9.7.1 wrapper;
- removed the stale public issue-specific sizing/upstream plan while retaining general sizing-sensitivity work as a secondary experiment.

## TailCache 03 conclusion

The Caffeine measured path is sufficiently understood for the next phase:

- adapter semantics are tested;
- measured reads are consumed explicitly;
- benchmark keys are pre-boxed;
- backend configuration is logged;
- runner and forks use Java 21;
- module flags are no longer duplicated;
- foreground operations remain sub-byte/op in the GC-profiler smoke;
- JFR recordings are generated successfully and interpreted with the correct configuration limitations;
- asynchronous Caffeine maintenance is identified as backend behaviour rather than hidden as benchmark noise.

TailCache 03 is complete. The next backend-validation slice should apply the same measured-path scrutiny to Chronicle Map before reportable Caffeine-vs-Chronicle comparisons begin.

## Interpretation guardrail

The short 1/1/1, 300 ms smoke runs exist to validate benchmark plumbing and measured-path behaviour. Their p50/p99/p99.9 values are not evidence about Caffeine's steady-state tail latency and must not appear in the eventual research conclusions.
