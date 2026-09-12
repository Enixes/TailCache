# TailCache 04 - Chronicle Map measured-path validation

## Goal

Validate the Chronicle Map backend with the same discipline used for the Caffeine baseline before any reportable backend comparison is attempted.

**Status: IMPLEMENTATION COMPLETE - PEER-REVIEW REVALIDATION PENDING**

## Fact-checked backend semantics

Chronicle Map is not simply an on-heap `Map` with a different implementation. The Java `ChronicleMap` object is an on-heap view over a data store whose entries are held off-heap. That makes lifecycle and sizing part of the experimental configuration rather than incidental implementation details.

TailCache 04 makes the following choices explicit:

- `entries(config.maximumEntries())` configures Chronicle Map's target entry count;
- `maxBloatFactor(1.0)` is set explicitly rather than relying on the current library default;
- `allowSegmentTiering(true)` is also frozen explicitly. Chronicle documents that `maxBloatFactor(1.0)` does **not** guarantee that individual segments never tier because normal hash-distribution variance can overflow a segment; tiering therefore remains enabled rather than converting natural segment skew into an exception;
- `constantValueSizeBySample(new byte[config.valueSizeBytes()])` describes the actual benchmark workload: every `byte[]` value in a trial has the same exact payload length;
- no key-size setting is supplied because boxed primitive `Long` key size is statically known to Chronicle Map;
- `putReturnsNull(true)` is enabled because TailCache's shared `put` operation is `void` and must not pay to materialize a replaced value that the benchmark discards;
- `size()` delegates to Chronicle Map's `longSize()` so TailCache's `long`-valued adapter API does not inherit `Map.size()`'s `Integer.MAX_VALUE` saturation;
- `clear()` empties a live map for operation parity, while `close()` is the lifecycle boundary that releases the Chronicle Map instance and its off-heap resources;
- Chronicle analytics is disabled in test and benchmark JVMs with `-Dchronicle.analytics.disable=true` so vendor telemetry cannot add unrelated threads, networking, allocation, scheduling or cache disturbance to latency measurements.

The adapter intentionally does **not** configure `actualChunkSize`. Chronicle Map treats this as a lower-level tuning control. For constant-size keys and values, Chronicle derives a fixed entry layout from the configured serializers and sample; manually forcing chunk size would add a backend-specific tuning variable before the primary comparison is frozen.

## Deep-review correction: fixed-size versus average-size configuration

The first TailCache 04 implementation used `averageValueSize(...)`. A deeper review against Chronicle Map's builder documentation found that this did not accurately describe the workload: within each TailCache trial, every value is exactly 256 B or exactly 4 KiB.

Chronicle recommends `constantValueSizeBySample(...)` when values are constant-sized. That choice can change Chronicle's derived entry/chunk layout, so the earlier average-size diagnostics are retained only as historical evidence and are not mixed with the corrected layout.

The correction was:

- `CacheConfig.averageValueSizeBytes` -> `CacheConfig.valueSizeBytes`;
- Chronicle builder `averageValueSize(...)` -> `constantValueSizeBySample(...)`;
- Chronicle tests insert values whose length exactly matches the configured fixed payload size;
- a negative test verifies that Chronicle rejects a value whose serialized size does not match the configured constant size;
- backend logging reports the experiment-relevant configuration, including `valueSizeBytes`, `valueSizing=constant`, `maxBloatFactor`, `allowSegmentTiering`, `putReturnsNull`, off-heap entry storage and persistence mode.

## Entry-count and occupancy semantics

Chronicle Map's `entries(n)` is a target entry count, not a Java `HashMap`-style capacity/load-factor hint. `maxBloatFactor(1.0)` limits planned bloat relative to that target, but it is **not** equivalent to disabling segment tiering; `allowSegmentTiering(true)` remains explicit for normal per-segment variance.

Caffeine `maximumSize(n)` has different semantics: it is an eviction bound. TailCache therefore must not pretend the shared integer means the same thing for both backends.

The current smoke harness uses:

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
- repeated close safety.

Benchmark trial teardown calls `CacheAdapter.close()`, so every Chronicle Map created by JMH trial setup has an explicit lifecycle endpoint.

## Corrected-layout diagnostic evidence

Before the final peer-review hardening above, executable revision `8dc42012e91608a2e1d605ece7393243c3a24d8b` was validated with:

```bash
./gradlew test --rerun-tasks
./gradlew jmhSmoke
./gradlew jmhChronicleAllocSmoke
./gradlew jmhChronicleJfrSmoke
```

All four commands completed successfully. The actual JMH VMs ran on JDK 21.0.12.1 via the project toolchain even though the host shell/Gradle launcher used JDK 26.

That run used the corrected constant-size layout and produced:

| Operation | 256 B payload | 4 KiB payload |
|---|---:|---:|
| `getHit` | 272.367 B/op | 4116.698 B/op |
| `getMiss` | 0.088 B/op | 0.201 B/op |
| `putExisting` | 195.121 B/op | 194.414 B/op |

The qualitative interpretation was:

- `getHit` allocation scales almost one-for-one with payload size;
- `getMiss` is effectively allocation-free at the operation level;
- `putExisting` remains roughly payload-size independent after `putReturnsNull(true)`.

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

No `ByteArraySizedReader` old-value materialization stack appeared in the inspected put recording. The conclusion is deliberately narrow: there was no sampled evidence of Chronicle old-value materialization on that put path, and normalized put allocation was payload-size independent at roughly 194-195 B/op.

These numbers remain diagnostic provenance, not reportable latency results. The newest peer-review hardening explicitly disables Chronicle analytics and freezes segment-tiering behavior, so the validation bundle must be rerun before TailCache 04 receives final merge sign-off.

## Historical pre-correction diagnostics

The superseded average-size layout produced:

| Operation | 256 B payload | 4 KiB payload |
|---|---:|---:|
| `getHit` | 272.169 B/op | 4117.053 B/op |
| `getMiss` | 0.199 B/op | 0.076 B/op |
| `putExisting` | 192.657 B/op | 198.420 B/op |

Those results remain useful as provenance for why the measured-path semantics were investigated, but they are not mixed into the final constant-size-layout experiment as if they were one dataset.

## Interpretation guardrails

The profiler diagnostics validate measured-path semantics; they do not establish the final latency comparison.

In particular:

- JFR-profiled latency values are profiler-perturbed and must not be compared with non-profiled runs;
- the 1/1/1, 300 ms smoke distributions are too short for tail-latency conclusions;
- historical average-size results must not be mixed with corrected constant-size results as if they came from the same Chronicle layout;
- observed GC activity in the Chronicle hit path is expected from ordinary `get` materialization, but its steady-state tail effect must be measured in the reportable experiment;
- Chronicle's normal `get` and a future `getUsing`/reuse path answer different API-level questions and must remain separate experiments;
- JFR allocation events are sampled and zero counts for disabled or thresholded event types are not proof of universal absence.

## Peer-review revalidation criteria

The latest implementation must be rerun with:

```bash
./gradlew test --rerun-tasks
./gradlew jmhSmoke
./gradlew jmhChronicleAllocSmoke
./gradlew jmhChronicleJfrSmoke
```

Final TailCache 04 sign-off requires:

- [ ] unit tests pass, including the wrong-value-size negative test;
- [ ] JMH VM arguments contain `-Dchronicle.analytics.disable=true` exactly once;
- [ ] Chronicle trial logs include `allowSegmentTiering=true` and the experiment-relevant configuration;
- [ ] cross-backend smoke succeeds;
- [ ] Chronicle allocation smoke preserves the expected measured-path classification or any change is investigated;
- [ ] Chronicle JFR recordings are generated and contain no unexplained benchmark-worker interference;
- [ ] no smoke latency number is promoted to a research conclusion.

After that, TailCache 04 is merge-ready. The next phase adds controlled workload distributions, read/write mixes and persisted Chronicle mode while keeping multi-JVM sharing separate.
