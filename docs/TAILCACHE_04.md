# TailCache 04 - Chronicle Map measured-path validation

## Goal

Validate the Chronicle Map backend with the same discipline used for the Caffeine baseline before any reportable backend comparison is attempted.

**Status: IMPLEMENTED - RUNTIME VALIDATION PENDING**

## Fact-checked backend semantics

Chronicle Map is not simply an on-heap `Map` with a different implementation. The Java `ChronicleMap` object is an on-heap view over a data store whose entries are held off-heap. That makes lifecycle and sizing part of the experimental configuration rather than incidental implementation details.

TailCache 04 therefore makes the following choices explicit:

- `entries(config.maximumEntries())` configures the Chronicle Map target entry count;
- `maxBloatFactor(1.0)` is set explicitly rather than relying on the current library default;
- `averageValueSize(config.averageValueSizeBytes())` supplies the serialized value-size estimate Chronicle Map requires for variable-size `byte[]` values;
- no key-size setting is supplied because boxed primitive `Long` key size is statically known to Chronicle Map;
- `putReturnsNull(true)` is enabled because TailCache's shared `put` operation is `void` and must not pay to materialize a replaced value that the benchmark discards;
- `size()` delegates to Chronicle Map's `longSize()` so TailCache's `long`-valued adapter API does not inherit `Map.size()`'s `Integer.MAX_VALUE` saturation;
- `clear()` empties a live map for operation parity, while `close()` is the actual lifecycle boundary that releases the Chronicle Map instance and its off-heap resources.

The adapter intentionally does **not** configure `actualChunkSize`. Chronicle Map documents that as a lower-level tuning knob and provides layout heuristics from the entry/value-size configuration. Choosing a hand-tuned chunk size here would introduce a backend-specific tuning variable before the primary comparison is frozen.

## Capacity terminology

Chronicle Map's `entries(n)` is a target entry count rather than a Java `HashMap`-style capacity/load-factor hint. With `maxBloatFactor(1.0)`, Chronicle documents that target as the configured maximum-bloat boundary, but insertion beyond it may fail rather than promising a precisely testable `n + 1` rejection point.

TailCache therefore logs the builder terms directly (`entries` and `maxBloatFactor`) instead of claiming that Chronicle Map has exactly the same capacity semantics as Caffeine's `maximumSize` eviction policy.

The primary experiment still keeps the resident working set below both configured limits, so eviction/capacity exhaustion is not part of the first latency comparison.

## Measured-operation parity

TailCache keeps the same shared operations for both backends:

- `getHit`
- `getMiss`
- `putExisting`

For Chronicle Map, ordinary `get` remains the primary path. It may deserialize/materialize a `byte[]` from the off-heap representation. That API boundary is intentionally part of the end-to-end comparison.

`getUsing` is **not** substituted into the primary benchmark because object reuse changes the API contract and would no longer be the same operation as the shared `CacheAdapter.get`. A reuse-oriented Chronicle experiment can be added later as a clearly separate secondary comparison.

## Lifecycle and correctness tests

The Chronicle adapter tests now cover:

- backend name and complete configuration summary;
- miss before insertion;
- hit after insertion;
- overwrite semantics without changing logical size;
- clear semantics;
- lifecycle close;
- rejection of access after close;
- repeated close safety.

Benchmark trial teardown already calls `CacheAdapter.close()`, so every Chronicle Map created by JMH trial setup has an explicit lifecycle endpoint.

## Validation commands

Run on the TailCache 04 branch:

```bash
./gradlew test --rerun-tasks
./gradlew jmhSmoke
./gradlew jmhChronicleAllocSmoke
./gradlew jmhChronicleJfrSmoke
```

The two Chronicle-only profiler tasks use the same 1 warmup / 1 measurement / 1 fork / 300 ms smoke policy as the Caffeine validation tasks and run through the Java 21 toolchain.

## Allocation-smoke interpretation

The Chronicle allocation smoke is **not** expected to match Caffeine's near-zero foreground allocation profile.

In particular:

- a `getHit` may allocate when the off-heap value is materialized as a Java `byte[]`;
- a `getMiss` should not need to materialize a payload;
- `putExisting` should not allocate merely to return the replaced value because `putReturnsNull(true)` is configured;
- any remaining allocation must be classified rather than automatically treated as a failure.

The goal is to identify which allocation is intrinsic to the API boundary and which would be accidental benchmark plumbing.

## JFR interpretation

The same guardrails from TailCache 03 apply. JMH 1.37's default JFR `profile` configuration is sampled and thresholded; disabled or thresholded zero-count events are not proof of universal absence.

Use JFR to inspect representative stacks, GC/runtime activity and unexpected synchronization. Do not use JFR-profiled latency values as research results.

## Completion criteria

TailCache 04 is complete when the final branch head satisfies all of the following:

- `./gradlew test --rerun-tasks` passes on Java 21;
- lifecycle tests confirm close/repeated-close behavior;
- `jmhSmoke` succeeds for both backends after the Chronicle changes;
- Chronicle trial logs show explicit `entries`, `averageValueSizeBytes`, `maxBloatFactor`, `putReturnsNull` and off-heap storage metadata;
- `jmhChronicleAllocSmoke` completes and its per-operation allocation profile is reviewed;
- `jmhChronicleJfrSmoke` generates recordings for all Chronicle operation/payload combinations;
- at least one representative Chronicle hit recording is inspected for allocation/runtime behavior;
- no smoke latency number is promoted to a research conclusion.

After this milestone, the next trustworthy-harness work is to quantify the benchmark harness floor and freeze the reportable experiment protocol before running the Caffeine-vs-Chronicle campaign.
