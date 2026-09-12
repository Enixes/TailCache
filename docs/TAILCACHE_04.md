# TailCache 04 - Chronicle Map measured-path validation

## Goal

Validate the Chronicle Map backend with the same discipline used for the Caffeine baseline before any reportable backend comparison is attempted.

**Status: COMPLETE**

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

The first TailCache 04 implementation used `averageValueSize(...)`. A deeper review against Chronicle Map's builder documentation found that this did not accurately describe the workload: within each TailCache trial, every value is exactly 256 B or exactly 4 KiB.

Chronicle recommends `constantValueSizeBySample(...)` when values are constant-sized. That choice can change Chronicle's derived entry/chunk layout, so the earlier average-size diagnostics were retained only as historical evidence and the full validation was repeated after correcting the layout.

The correction was:

- `CacheConfig.averageValueSizeBytes` -> `CacheConfig.valueSizeBytes`;
- Chronicle builder `averageValueSize(...)` -> `constantValueSizeBySample(...)`;
- Chronicle tests now insert values whose length exactly matches the configured fixed payload size;
- backend logging reports `valueSizeBytes`, `valueSizing=constant`, `entryStorage=off-heap`, and `persisted=false`.

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

## Final corrected-layout validation

The corrected executable branch head `8dc42012e91608a2e1d605ece7393243c3a24d8b` was validated with:

```bash
./gradlew test --rerun-tasks
./gradlew jmhSmoke
./gradlew jmhChronicleAllocSmoke
./gradlew jmhChronicleJfrSmoke
```

All four commands completed successfully. The validation working tree had only unrelated untracked local JFR log files, so no modified tracked source or build file was involved in the run.

The host shell and Gradle launcher were running JDK 26, while the benchmark JavaExec/JMH VMs were explicitly launched with JDK 21.0.12.1 via the project toolchain. The benchmark runtime therefore remained the pinned Java 21 runtime.

Chronicle trial logs showed the expected corrected configuration for both payload sizes:

```text
entries=4096
valueSizeBytes=256 | 4096
valueSizing=constant
maxBloatFactor=1.0
putReturnsNull=true
entryStorage=off-heap
persisted=false
```

### Corrected-layout allocation profile

| Operation | 256 B payload | 4 KiB payload |
|---|---:|---:|
| `getHit` | 272.367 B/op | 4116.698 B/op |
| `getMiss` | 0.088 B/op | 0.201 B/op |
| `putExisting` | 195.121 B/op | 194.414 B/op |

The corrected layout preserves the same qualitative pattern as the historical average-size run:

- `getHit` allocation scales almost one-for-one with payload size;
- `getMiss` remains effectively allocation-free at the operation level;
- `putExisting` remains roughly payload-size independent after `putReturnsNull(true)`.

The tiny differences from the earlier diagnostic values are not treated as performance changes; these are short smoke/profiler runs. What matters here is that the measured-path allocation semantics survived the layout correction.

### Corrected-layout JFR classification

The representative corrected 4 KiB `getHit` recording again shows repeated `byte[]` allocation samples on the JMH worker through:

```text
ByteArraySizedReader.read
VanillaChronicleMap.searchValue
VanillaChronicleMap.tieredValue
VanillaChronicleMap.optimizedGet
```

This directly confirms, under the final constant-size layout, that ordinary Chronicle Map `get` materializes the returned Java `byte[]` from off-heap entry storage. The recording contains five young G1 collections during the short profiled run, consistent with the high payload-sized allocation rate.

The representative corrected 4 KiB `putExisting` recording shows Chronicle Bytes/reference-counting allocations on the worker through paths including:

```text
ByteArrayDataAccess.getData
BytesStore.wrap
HeapBytesStore.wrap
VanillaChronicleMap.put
```

No `ByteArraySizedReader` old-value materialization stack appears in the inspected put recording. A sampled worker-thread `byte[]` allocation does appear during JMH/warmdown support code (`Class.getPackageName`/string processing), so the conclusion is deliberately narrow: there is no sampled evidence of Chronicle old-value materialization on the put path, and the GC-profiler allocation remains payload-size independent at about 194-195 B/op.

The corrected get-hit recording contains two long compilation events, but they are `InnerClassLambdaMetafactory.generateInnerClass()` and `ByteArrayOutputStream.ensureCapacity(int)`, not the Chronicle measured-path method previously observed in the historical put run. There are no recorded `jdk.Compilation` events in the inspected corrected put JFR. This does not remove the need for a reportable warmup/compilation-stability check.

Thread-park events in the representative corrected recordings belong to the JMH/main thread or process reaper rather than the benchmark worker.

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

## Completion criteria

TailCache 04 completion checks are satisfied on the corrected constant-size layout:

- [x] `./gradlew test --rerun-tasks` passes after the correction;
- [x] lifecycle tests cover close/repeated-close behavior;
- [x] `jmhSmoke` succeeds for both backends after the correction;
- [x] Chronicle trial logs show `entries`, `valueSizeBytes`, `valueSizing=constant`, `maxBloatFactor`, `putReturnsNull`, off-heap entry storage and non-persisted mode;
- [x] `jmhChronicleAllocSmoke` completes and its corrected-layout per-operation allocation profile is reviewed;
- [x] `jmhChronicleJfrSmoke` generates recordings for all Chronicle operation/payload combinations;
- [x] representative corrected-layout Chronicle hit and put recordings are inspected;
- [x] no smoke latency number is promoted to a research conclusion.

TailCache 04 is therefore complete. The next trustworthy-harness work is to quantify the benchmark harness floor, capture environment metadata, verify warmup/compilation stability, freeze backend-specific occupancy semantics, capture useful resolved Chronicle layout metadata where possible, and then freeze the reportable experiment protocol before running the Caffeine-vs-Chronicle campaign.
