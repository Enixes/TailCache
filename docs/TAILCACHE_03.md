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

### Allocation smoke

`jmhCaffeineAllocSmoke` runs the short Caffeine-only smoke matrix with JMH's built-in `gc` profiler. Inspect `gc.alloc.rate.norm` in particular.

The goal is to detect avoidable benchmark-created allocation, not to declare a universal zero-allocation guarantee. Tiny framework/background values or occasional cache-maintenance allocation should be investigated rather than hidden.

### JFR smoke

`jmhCaffeineJfrSmoke` records Java Flight Recorder profiles under `build/reports/jmh/jfr/`.

Inspect the recording for:

- allocations in the measured cache access path;
- unexpected locking/contention;
- class loading or compilation leaking into the measurement window;
- surprising runtime activity that would make the smoke result hard to interpret.

These are validation runs only. Their latency numbers are **not reportable research results**.
