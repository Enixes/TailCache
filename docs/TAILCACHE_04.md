# TailCache 04 - Chronicle Map measured-path validation

## Goal

Validate the Chronicle Map backend with the same discipline used for the Caffeine baseline before any reportable backend comparison is attempted.

**Status: COMPLETE**

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

For Chronicle Map, ordinary `get` remains the primary path. It deserializes/materializes a Java `byte[]` from the off-heap representation on a hit. That API boundary is intentionally part of the end-to-end comparison.

`getUsing` is **not** substituted into the primary benchmark because object reuse changes the API contract and would no longer be the same operation as the shared `CacheAdapter.get`. A reuse-oriented Chronicle experiment can be added later as a clearly separate secondary comparison.

## Lifecycle and correctness tests

The Chronicle adapter tests cover:

- backend name and complete configuration summary;
- miss before insertion;
- hit after insertion;
- overwrite semantics without changing logical size;
- clear semantics;
- lifecycle close;
- rejection of access after close;
- repeated close safety.

Benchmark trial teardown already calls `CacheAdapter.close()`, so every Chronicle Map created by JMH trial setup has an explicit lifecycle endpoint.

## Runtime validation

The final TailCache 04 branch was validated on JDK 21.0.12.1 with:

```bash
./gradlew test --rerun-tasks
./gradlew jmhSmoke
./gradlew jmhChronicleAllocSmoke
./gradlew jmhChronicleJfrSmoke
```

All four commands completed successfully. `jmhSmoke` exercised both Caffeine and Chronicle Map after the adapter changes, and Chronicle trial logging showed the expected configuration for both payload sizes:

```text
entries=4096
averageValueSizeBytes=256 | 4096
maxBloatFactor=1.0
putReturnsNull=true
storage=off-heap
```

The profiler tasks used the Java 21 toolchain and the same 1 warmup / 1 measurement / 1 fork / 300 ms diagnostic policy as the Caffeine validation tasks.

## Allocation-smoke results

The Chronicle allocation smoke produced the following normalized allocation:

| Operation | 256 B payload | 4 KiB payload |
|---|---:|---:|
| `getHit` | 272.169 B/op | 4117.053 B/op |
| `getMiss` | 0.199 B/op | 0.076 B/op |
| `putExisting` | 192.657 B/op | 198.420 B/op |

These results have a useful internal-control pattern:

- `getHit` allocation scales almost one-for-one with payload size;
- `getMiss` is effectively allocation-free at the operation level;
- `putExisting` remains roughly payload-size independent after `putReturnsNull(true)`.

That pattern is consistent with successful ordinary `get` calls materializing a Java `byte[]`, while misses do not materialize a payload and `putExisting` does not materialize the replaced value merely to satisfy `Map.put` return semantics.

The absolute allocation values are diagnostic smoke results, not reportable performance measurements.

## JFR classification

A representative 4 KiB `getHit` JFR recording confirms the allocation source directly. Repeated sampled allocations on the JMH worker are `byte[]` objects with stacks through:

```text
ByteArraySizedReader.read
VanillaChronicleMap.searchValue
VanillaChronicleMap.tieredValue
VanillaChronicleMap.optimizedGet
```

This provides direct sampled-stack evidence that ordinary Chronicle Map `get` materializes the returned Java `byte[]` from the off-heap representation. The recording also contained multiple young-GC events, which is consistent with the high allocation rate of the 4 KiB hit path.

The representative 4 KiB `putExisting` recording shows a different allocation shape. Sampled worker-thread allocations are dominated by Chronicle Bytes/reference-counting objects such as `HeapBytesStore`, `VanillaReferenceCounted`, `ReferenceChangeListenerManager`, and related support objects. The stacks flow through:

```text
ByteArrayDataAccess.getData
BytesStore.wrap
HeapBytesStore.wrap
VanillaChronicleMap.put
```

No sampled `byte[]` allocation or `ByteArraySizedReader` materialization stack appeared in that put recording. Together with the payload-size-independent ~193-198 B/op GC-profiler result, this provides no evidence that `putExisting` is materializing the replaced 256 B/4 KiB value after `putReturnsNull(true)`. It does **not** claim universal zero old-value allocation; JFR allocation events are sampled.

The put recording also captured a C2 compilation of `MapMethods.put` during the short diagnostic run. This is another reason the 300 ms smoke latency distributions are not steady-state research results and motivates an explicit warmup/compilation-stability check before the reportable campaign.

Thread-park samples in the inspected recordings were JMH/main-thread coordination or process-reaper activity rather than the benchmark worker. The default JFR profile remains sampled and thresholded, so zero counts for disabled or thresholded event types are not interpreted as proof of universal absence.

## Interpretation guardrails

The allocation and JFR diagnostics validate measured-path semantics; they do not establish the final latency comparison.

In particular:

- JFR-profiled latency values are profiler-perturbed and must not be compared with non-profiled runs;
- the 1/1/1, 300 ms smoke distributions are too short for tail-latency conclusions;
- observed GC events in the Chronicle hit path are expected consequences of normal `get` materialization, but their steady-state effect must be measured in the reportable experiment rather than inferred from these smoke runs;
- Chronicle's normal `get` and a future `getUsing`/reuse path answer different API-level questions and must remain separate experiments.

## Completion criteria

TailCache 04 completion checks are all satisfied:

- [x] `./gradlew test --rerun-tasks` passes on Java 21;
- [x] lifecycle tests confirm close/repeated-close behavior;
- [x] `jmhSmoke` succeeds for both backends after the Chronicle changes;
- [x] Chronicle trial logs show explicit `entries`, `averageValueSizeBytes`, `maxBloatFactor`, `putReturnsNull` and off-heap storage metadata;
- [x] `jmhChronicleAllocSmoke` completes and its per-operation allocation profile is reviewed;
- [x] `jmhChronicleJfrSmoke` generates recordings for all Chronicle operation/payload combinations;
- [x] representative Chronicle hit and put recordings are inspected for allocation/runtime behavior;
- [x] no smoke latency number is promoted to a research conclusion.

The next trustworthy-harness work is to quantify the benchmark harness floor, capture environment metadata, verify warmup/compilation stability, and freeze the reportable experiment protocol before running the Caffeine-vs-Chronicle campaign.
