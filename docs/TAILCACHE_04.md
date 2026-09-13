# TailCache 04 - Chronicle Map measured-path validation

## Goal

Validate the Chronicle Map backend with the same discipline used for the Caffeine baseline before any reportable backend comparison is attempted.

**Status: MERGED - POST-MERGE PEER-REVIEW HARDENING VALIDATED IN TAILCACHE 05**

TailCache 04 itself was merged in PR #3. TailCache 05 subsequently carried a small post-merge hardening pass: Chronicle analytics is disabled, segment-tiering behavior is frozen/logged explicitly, the constant-size contract has a negative test, and configuration wording is tightened. That hardened adapter was revalidated successfully on TailCache 05 revision `d98be0f34202d7bb3421d6d2c692741db6fc6501`.

## Fact-checked backend semantics

Chronicle Map is not simply an on-heap `Map` with a different implementation. The Java `ChronicleMap` object is an on-heap view over a data store whose entries are held off-heap. That makes lifecycle and sizing part of the experimental configuration rather than incidental implementation details.

TailCache makes the following Chronicle choices explicit:

- `entries(config.maximumEntries())` configures Chronicle Map's target entry count;
- `maxBloatFactor(1.0)` is set explicitly rather than relying on the current library default;
- `allowSegmentTiering(true)` is frozen explicitly. `maxBloatFactor(1.0)` does **not** guarantee that individual segments never tier because hash-distribution variance can overflow a segment; tiering therefore remains enabled rather than turning natural segment skew into an exception;
- `constantValueSizeBySample(new byte[config.valueSizeBytes()])` describes the actual benchmark workload: every `byte[]` value in a trial has the same exact payload length;
- no key-size setting is supplied because boxed primitive `Long` key size is statically known to Chronicle Map;
- `putReturnsNull(true)` is enabled because TailCache's shared `put` operation is `void` and must not pay to materialize a replaced value that the benchmark discards;
- `size()` delegates to Chronicle Map's `longSize()` so TailCache's `long`-valued adapter API does not inherit `Map.size()`'s `Integer.MAX_VALUE` saturation;
- `clear()` empties a live map for operation parity, while `close()` is the lifecycle boundary that releases the Chronicle Map instance and its off-heap resources;
- Chronicle analytics is disabled in test and benchmark JVMs with `-Dchronicle.analytics.disable=true` so vendor telemetry cannot add unrelated threads, networking, allocation, scheduling, or cache disturbance to latency measurements.

The adapter intentionally does **not** configure `actualChunkSize`. Chronicle Map treats this as a lower-level tuning control. For constant-size keys and values, Chronicle derives a fixed entry layout from the configured serializers and sample; manually forcing chunk size would add a backend-specific tuning variable before the primary comparison is frozen.

## Deep-review correction: fixed-size versus average-size configuration

The first TailCache 04 implementation used `averageValueSize(...)`. A deeper review against Chronicle Map's builder documentation found that this did not accurately describe the workload: within each TailCache trial, every value is exactly 256 B or exactly 4 KiB.

Chronicle recommends `constantValueSizeBySample(...)` when values are constant-sized. That choice can change Chronicle's derived entry/chunk layout, so the earlier average-size diagnostics are retained only as historical evidence and are not mixed with the corrected layout.

The correction was:

- `CacheConfig.averageValueSizeBytes` -> `CacheConfig.valueSizeBytes`;
- Chronicle builder `averageValueSize(...)` -> `constantValueSizeBySample(...)`;
- Chronicle tests insert values whose length exactly matches the configured fixed payload size;
- a negative test verifies that Chronicle rejects a value whose serialized size does not match the configured constant size;
- backend logging reports the experiment-relevant configuration, including `valueSizeBytes`, `valueSizing=constant`, `maxBloatFactor`, `allowSegmentTiering`, `putReturnsNull`, off-heap entry storage, checksum mode, and persistence mode.

## Entry-count and occupancy semantics

Chronicle Map's `entries(n)` is a target entry count, not a Java `HashMap`-style capacity/load-factor hint. `maxBloatFactor(1.0)` limits planned bloat relative to that target, but it is **not** equivalent to disabling segment tiering; `allowSegmentTiering(true)` remains explicit for normal per-segment variance.

Caffeine `maximumSize(n)` has different semantics: it is an eviction bound. TailCache therefore must not pretend the shared integer means the same thing for both backends.

The smoke harness uses:

```text
resident entries = 2048
configured entry setting = 4096
```

That is acceptable for harness validation because it stays away from eviction/capacity exhaustion, but it is **not automatically the reportable occupancy protocol**. Before the main campaign, TailCache must explicitly decide how Chronicle `entries`, Caffeine `maximumSize`, and resident working-set size relate to each other and document that choice.

## Measured-operation parity

TailCache keeps the same shared operations for both backends:

- `getHit`
- `getMiss`
- `putExisting`

For Chronicle Map, ordinary `get` remains the primary path. It materializes a Java `byte[]` from the off-heap representation on a hit. That API boundary is intentionally part of the end-to-end comparison.

`getUsing` is **not** substituted into the primary benchmark because object reuse changes the API contract and would no longer be the same operation as the shared `CacheAdapter.get`. A reuse-oriented Chronicle experiment can be added later as a clearly separate secondary comparison.

## Lifecycle and correctness tests

The Chronicle adapter tests cover:

- backend name and experiment-relevant configuration summary;
- fixed-size value configuration matching inserted values;
- rejection of a value whose size violates the configured constant-size contract;
- miss before insertion;
- hit after insertion;
- overwrite semantics without changing logical size;
- clear semantics;
- lifecycle close;
- rejection of access after close;
- repeated close safety;
- persisted close/reopen behavior in TailCache 05.

Benchmark trial teardown calls `CacheAdapter.close()`, so every Chronicle Map created by JMH trial setup has an explicit lifecycle endpoint.

## Corrected-layout diagnostic evidence

Executable revision `8dc42012e91608a2e1d605ece7393243c3a24d8b` first validated the corrected constant-size layout with:

```bash
./gradlew test --rerun-tasks
./gradlew jmhSmoke
./gradlew jmhChronicleAllocSmoke
./gradlew jmhChronicleJfrSmoke
```

That run produced:

| Operation | 256 B payload | 4 KiB payload |
|---|---:|---:|
| `getHit` | 272.367 B/op | 4116.698 B/op |
| `getMiss` | 0.088 B/op | 0.201 B/op |
| `putExisting` | 195.121 B/op | 194.414 B/op |

The qualitative interpretation was:

- `getHit` allocation scales almost one-for-one with payload size;
- `getMiss` is effectively allocation-free at the operation level;
- `putExisting` remains far below payload-size scaling after `putReturnsNull(true)`.

The representative corrected 4 KiB `getHit` JFR showed repeated worker-thread `byte[]` allocation samples through:

```text
ByteArraySizedReader.read
VanillaChronicleMap.searchValue
VanillaChronicleMap.tieredValue
VanillaChronicleMap.optimizedGet
```

The representative corrected 4 KiB `putExisting` recording showed Chronicle Bytes/reference-counting allocations through paths including:

```text
ByteArrayDataAccess.getData
BytesStore.wrap
HeapBytesStore.wrap
VanillaChronicleMap.put
```

No `ByteArraySizedReader` old-value materialization stack appeared in the inspected put recording. The conclusion is deliberately narrow: there was no sampled evidence of Chronicle old-value materialization on that put path, and normalized put allocation did not scale with the payload size.

## Post-merge peer-review hardening revalidation

TailCache 05 revision `d98be0f34202d7bb3421d6d2c692741db6fc6501` reran the hardened Chronicle adapter with analytics disabled and explicit segment-tiering/checksum configuration. All required operation-level commands completed successfully on JMH forks using JDK 21.0.12.1.

Normalized allocation was:

| Operation | 256 B payload | 4 KiB payload |
|---|---:|---:|
| `getHit` | 272.442 B/op | 4118.994 B/op |
| `getMiss` | 0.245 B/op | 0.200 B/op |
| `putExisting` | 197.520 B/op | 221.093 B/op |

The classification therefore survived the hardening:

- hit allocation still tracks returned payload size;
- misses remain effectively allocation-free;
- `putExisting` remains around a few hundred bytes per operation rather than scaling by the 4 KiB payload;
- JFR again attributes hit materialization to `ByteArraySizedReader` and write-side allocation to Chronicle Bytes/reference-counting machinery;
- the inspected long `ThreadPark` events belong to JMH/main coordination or process-reaper threads, not the benchmark worker.

The modest 256 B -> 4 KiB put increase in this short diagnostic is not interpreted as payload materialization: the increase is tens of bytes, not approximately 4 KiB, and the run is intentionally too short for stable performance conclusions.

The later TailCache 05 cursor hardening does not modify the Chronicle adapter or `CacheSmokeBenchmark`, so another Chronicle allocation/JFR cycle is not required solely for that change.

## Historical pre-correction diagnostics

The superseded average-size layout produced:

| Operation | 256 B payload | 4 KiB payload |
|---|---:|---:|
| `getHit` | 272.169 B/op | 4117.053 B/op |
| `getMiss` | 0.199 B/op | 0.076 B/op |
| `putExisting` | 192.657 B/op | 198.420 B/op |

Those results remain useful as provenance for why the measured-path semantics were investigated, but they are not mixed into the final constant-size-layout experiment as if they came from the same Chronicle layout.

## Interpretation guardrails

The profiler diagnostics validate measured-path semantics; they do not establish the final latency comparison.

In particular:

- JFR-profiled latency values are profiler-perturbed and must not be compared with non-profiled runs;
- the 1/1/1, 300 ms smoke distributions are too short for tail-latency conclusions;
- historical average-size results must not be mixed with corrected constant-size results as if they came from the same Chronicle layout;
- observed GC activity in the Chronicle hit path is expected from ordinary `get` materialization, but its steady-state tail effect must be measured in the reportable experiment;
- Chronicle's normal `get` and a future `getUsing`/reuse path answer different API-level questions and must remain separate experiments;
- JFR allocation events are sampled and zero counts for disabled or thresholded event types are not proof of universal absence.

## Post-merge hardening sign-off

The hardened Chronicle adapter has passed the intended TailCache 04 revalidation criteria:

- [x] unit tests passed, including the wrong-value-size negative test;
- [x] JMH VM arguments contained `-Dchronicle.analytics.disable=true` exactly once per fork;
- [x] Chronicle trial logs included `allowSegmentTiering=true` and experiment-relevant configuration;
- [x] cross-backend smoke succeeded;
- [x] Chronicle allocation smoke preserved the expected measured-path classification;
- [x] Chronicle JFR recordings were generated with explainable worker-thread allocation stacks;
- [x] no smoke latency number is promoted to a research conclusion.

TailCache 04 is therefore historically complete. TailCache 05 continues with workload distributions, persisted Chronicle mode, and same-JVM shared-cache contention while keeping two-JVM sharing separate.
