# TailCache 04 - Chronicle Map measured-path validation

## Goal

Validate the Chronicle Map backend with the same discipline used for the Caffeine baseline before any reportable backend comparison is attempted.

**Status: DEEP-REVIEW FIX APPLIED - FINAL REVALIDATION PENDING**

## Fact-checked backend semantics

Chronicle Map is not simply an on-heap `Map` with a different implementation. The Java `ChronicleMap` object is an on-heap view over a data store whose entries are held off-heap. That makes lifecycle and sizing part of the experimental configuration rather than incidental implementation details.

TailCache 04 makes the following choices explicit:

- `entries(config.maximumEntries())` configures Chronicle Map's target entry count;
- `maxBloatFactor(1.0)` is set explicitly rather than relying on the current library default;
- `constantValueSizeBySample(new byte[config.valueSizeBytes()])` describes the actual benchmark workload: every `byte[]` value in a trial has the same exact payload length;
- no key-size setting is supplied because boxed primitive `Long` key size is statically known to Chronicle Map;
- `putReturnsNull(true)` is enabled because TailCache's shared `put` operation is `void` and must not pay to materialize a replaced value that the benchmark discards;
- `size()` delegates to Chronicle Map's `longSize()` so TailCache's `long`-valued adapter API does not inherit `Map.size()`'s `Integer.MAX_VALUE` saturation;
- `clear()` empties a live map for operation parity, while `close()` is the lifecycle boundary that releases the Chronicle Map instance and its off-heap resources.

The adapter intentionally does **not** configure `actualChunkSize`. Chronicle Map documents this as a lower-level tuning control. For constant-size keys and values, Chronicle can derive a fixed entry layout from the configured serializers and sample. Hand-tuning chunk size here would add a backend-specific tuning variable before the primary comparison is frozen.

## Deep-review correction: fixed-size versus average-size configuration

The first TailCache 04 implementation used `averageValueSize(...)`. A deeper review against Chronicle Map's builder documentation found that this was not the best description of the workload: within each TailCache trial, every value is exactly 256 B or exactly 4 KiB.

Chronicle explicitly recommends `constantValueSizeBySample(...)` when values are constant-sized. That choice is not just terminology; it can change Chronicle's derived entry/chunk layout. Therefore the earlier average-sized runtime diagnostics remain useful historical evidence about ordinary `get`/`put` semantics, but they are **not the final validation of the corrected branch layout**.

The configuration and tests were corrected as follows:

- `CacheConfig.averageValueSizeBytes` -> `CacheConfig.valueSizeBytes`;
- Chronicle builder `averageValueSize(...)` -> `constantValueSizeBySample(...)`;
- Chronicle tests now insert values whose length exactly matches the configured fixed payload size;
- backend logging now reports `valueSizeBytes`, `valueSizing=constant`, `entryStorage=off-heap`, and `persisted=false`.

Final Java 21 smoke/allocation/JFR validation must be rerun after this correction before TailCache 04 is considered complete.

## Entry-count and occupancy semantics

Chronicle Map's `entries(n)` is a target entry count, not a Java `HashMap`-style capacity/load-factor hint. With `maxBloatFactor(1.0)`, Chronicle documents that target as the no-bloat boundary and warns against adding arbitrary margin over the actual target entry count.

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

- backend name and complete configuration summary;
- fixed-size value configuration matching inserted values;
- miss before insertion;
- hit after insertion;
- overwrite semantics without changing logical size;
- clear semantics;
- lifecycle close;
- rejection of access after close;
- repeated close safety.

Benchmark trial teardown calls `CacheAdapter.close()`, so every Chronicle Map created by JMH trial setup has an explicit lifecycle endpoint.

## Historical pre-correction runtime diagnostics

Before the fixed-size layout correction, the average-size implementation was validated on JDK 21.0.12.1 with:

```bash
./gradlew test --rerun-tasks
./gradlew jmhSmoke
./gradlew jmhChronicleAllocSmoke
./gradlew jmhChronicleJfrSmoke
```

All four commands completed successfully. These results are retained because they established important API-path behavior, but they are now considered **historical diagnostics**, not final corrected-layout validation.

### Allocation profile from the historical run

| Operation | 256 B payload | 4 KiB payload |
|---|---:|---:|
| `getHit` | 272.169 B/op | 4117.053 B/op |
| `getMiss` | 0.199 B/op | 0.076 B/op |
| `putExisting` | 192.657 B/op | 198.420 B/op |

The pattern was internally coherent:

- `getHit` allocation scaled almost one-for-one with payload size;
- `getMiss` was effectively allocation-free at the operation level;
- `putExisting` remained roughly payload-size independent after `putReturnsNull(true)`.

### JFR classification from the historical run

A representative 4 KiB `getHit` recording showed repeated sampled `byte[]` allocations on the JMH worker through:

```text
ByteArraySizedReader.read
VanillaChronicleMap.searchValue
VanillaChronicleMap.tieredValue
VanillaChronicleMap.optimizedGet
```

That provided direct sampled-stack evidence that ordinary Chronicle Map `get` materializes the returned Java `byte[]` from off-heap storage.

The representative 4 KiB `putExisting` recording showed Chronicle Bytes/reference-counting allocations through:

```text
ByteArrayDataAccess.getData
BytesStore.wrap
HeapBytesStore.wrap
VanillaChronicleMap.put
```

No sampled `byte[]` allocation or `ByteArraySizedReader` old-value materialization stack appeared in that put recording. Combined with the payload-size-independent allocation profile, there was no evidence that `putExisting` materialized the replaced payload after `putReturnsNull(true)`. This remains sampled evidence, not a universal zero-allocation claim.

The put recording also captured C2 compilation of `MapMethods.put` during the short diagnostic window. That is why TailCache now has an explicit warmup/compilation-stability task before any reportable campaign.

## Interpretation guardrails

The profiler diagnostics validate measured-path semantics; they do not establish the final latency comparison.

In particular:

- JFR-profiled latency values are profiler-perturbed and must not be compared with non-profiled runs;
- the 1/1/1, 300 ms smoke distributions are too short for tail-latency conclusions;
- historical average-size results must not be mixed with corrected constant-size results as if they came from the same Chronicle layout;
- observed GC activity in a Chronicle hit path must be evaluated again on the corrected layout before final conclusions;
- Chronicle's normal `get` and a future `getUsing`/reuse path answer different API-level questions and must remain separate experiments;
- JFR zero counts for disabled or thresholded event types are not proof of universal absence.

## Completion criteria

TailCache 04 is complete when the **corrected constant-size branch head** satisfies all of the following:

- [ ] `./gradlew test --rerun-tasks` passes on Java 21;
- [x] lifecycle tests cover close/repeated-close behavior;
- [ ] `jmhSmoke` succeeds for both backends after the fixed-size layout correction;
- [ ] Chronicle trial logs show `entries`, `valueSizeBytes`, `valueSizing=constant`, `maxBloatFactor`, `putReturnsNull`, off-heap entry storage and non-persisted mode;
- [ ] `jmhChronicleAllocSmoke` completes on the corrected layout and its per-operation allocation profile is reviewed;
- [ ] `jmhChronicleJfrSmoke` generates recordings for all Chronicle operation/payload combinations on the corrected layout;
- [ ] representative corrected-layout Chronicle hit and put recordings are inspected;
- [x] no smoke latency number is promoted to a research conclusion.

After that, the next trustworthy-harness work is to quantify the benchmark harness floor, capture environment metadata, verify warmup/compilation stability, freeze backend-specific occupancy semantics, and then freeze the reportable experiment protocol before running the Caffeine-vs-Chronicle campaign.
