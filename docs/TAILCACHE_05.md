# TailCache 05 - workload distributions, persisted mode and concurrency matrix

## Goal

Expand TailCache from operation-level adapter smoke tests into a controlled mixed-workload harness without turning the smoke matrix into reportable results prematurely.

**Status: IMPLEMENTED - BASE VALIDATION PASSED; MEASURED-PATH HARDENING RERUN PENDING**

TailCache 05 adds three primary backend/storage modes:

1. Caffeine on-heap;
2. Chronicle Map in-memory/off-heap;
3. Chronicle Map persisted-warm using `createPersistedTo(...)`.

Two-JVM persisted sharing remains a separate secondary experiment.

## Peer-review blockers closed first

TailCache 05 carries the TailCache 04 post-merge peer-review hardening before expanding the matrix:

- `-Dchronicle.analytics.disable=true` is supplied to test and benchmark JVMs;
- `allowSegmentTiering(true)` is configured and logged explicitly;
- documentation no longer treats `maxBloatFactor(1.0)` as a guarantee that segments can never tier;
- the constant-size Chronicle adapter has a wrong-value-size negative test;
- backend configuration strings are described as experiment-relevant summaries rather than exhaustive internal configuration dumps.

The hardened Chronicle adapter and operation-level diagnostics were revalidated successfully on TailCache 05 revision `d98be0f34202d7bb3421d6d2c692741db6fc6501`. The later cursor-only hardening described below does not change the Chronicle adapter or `CacheSmokeBenchmark`, so the Chronicle allocation/JFR evidence from that revision remains the relevant adapter validation.

## Access distributions

The primary mixed workload uses:

- `UNIFORM`;
- `ZIPFIAN` with exponent **0.99** as the initial skew value.

The numeric value 0.99 is the same Zipfian constant used by YCSB's default Zipfian generators and is frozen rather than tuned after seeing results. TailCache uses its own deterministic finite Zipf sampler; this is not a claim of byte-for-byte trace equivalence with YCSB's generators.

Zipfian CDF construction and random sampling happen while the trace is generated before measurement. Cache operations therefore do not pay for distribution-generation or PRNG work.

Legacy `HOTSPOT` generation remains available for later sensitivity work but is not part of the TailCache 05 primary matrix.

## Read/existing-key-put mixes

The primary mixed traces use:

- `READ_95_WRITE_5`;
- `READ_70_WRITE_30`.

The generator creates the exact number of reads over each **complete generated trace** and deterministically shuffles the operation flags. Key selection and operation selection use separate seeded random streams. Therefore changing 95/5 to 70/30 does not silently change the logical key sequence when the other workload parameters and seed are unchanged.

JMH measurements are time-limited, so an individual measurement iteration may stop part-way through a trace cycle. The exact 95/5 or 70/30 guarantee therefore applies to the complete deterministic trace, not necessarily to every finite measurement window.

All mixed writes are existing-key `put` calls. There are no inserts or misses in this mixed workload; every read targets the prepopulated resident working set. Uniform versus Zipfian therefore measures locality/hot-key contention over an all-hit resident set, **not** admission, eviction policy, or cache-hit-rate behavior. Hit/miss operation baselines remain in `CacheSmokeBenchmark`.

## Write-value control and interpretation limit

One replacement `byte[]` is preallocated per logical key during trial setup. A write uses the replacement associated with the selected key.

This is intentional. Reusing one global replacement array for every key would progressively make many Caffeine entries point to the same Java object, reducing Caffeine's resident heap footprint in a way Chronicle Map cannot mirror because Chronicle serializes the bytes into its own storage. Per-key replacement payloads avoid that artifact while keeping value allocation outside the measured `put` path.

This design also means that after a key has received its replacement value once, later puts to that key can be logically idempotent and write the same bytes again. TailCache 05 therefore describes this workload as **existing-key put traffic**, not as guaranteed changing-value updates. If changing-value update semantics become important, a later sensitivity experiment can alternate between two preallocated deterministic values per key without adding allocation to the measured path.

The replacement-value bank is also a deliberate live heap shadow set for Chronicle. At 4 KiB x 2048 keys it retains roughly one resident working set of payload bytes on the Java heap even though Chronicle stores the cache entries off-heap. This makes the TailCache 05 mixed matrix suitable for latency/contention study, but **not** for conclusions about Chronicle reducing heap footprint or GC pressure. Constrained-heap/GC experiments require a separate value-supply design.

## Persisted Chronicle mode

`ChronicleStorageMode` distinguishes:

- `IN_MEMORY` -> `ChronicleMapBuilder.create()`;
- `PERSISTED` -> `ChronicleMapBuilder.createPersistedTo(tempFile)`.

Chronicle's normal mode-dependent behavior is to store entry checksums for persisted maps but not purely in-memory maps. TailCache freezes that behavior explicitly with `checksumEntries(false)` for `IN_MEMORY` and `checksumEntries(true)` for `PERSISTED`, and logs `entryChecksums` in the adapter summary. The primary persisted mode therefore represents Chronicle's normal persisted safety semantics rather than an artificially stripped-down mmap mode. It is a deployment-mode comparison, not a pure "mmap cost only" experiment. If checksum cost needs to be isolated later, that belongs in a separate sensitivity experiment.

For `CHRONICLE_PERSISTED`, `CacheWorkloadState`:

1. creates a unique temporary directory and map path during `@Setup(Level.Trial)`;
2. creates the Chronicle Map at that path;
3. prepopulates the full resident working set before measurement;
4. runs the same deterministic workload specification as the other modes;
5. closes the map during `@TearDown(Level.Trial)`;
6. explicitly deletes the persisted file and temporary directory.

The adapter closes the map but deliberately does **not** delete persisted data itself. Persistence lifecycle and benchmark temporary-file cleanup are separate concerns. A unit test closes and reopens the same persisted file to verify that the stored value survives the adapter lifecycle, which also establishes the basic prerequisite for later process-sharing work.

### What “persisted-warm” means here

Prepopulation touches the mapped entry data before measurement, so the primary persisted mode is intended as a warm steady-state experiment rather than a map-open benchmark.

That is an experimental intent, not proof that all relevant pages stay resident or that writeback cannot disturb the run. Chronicle persisted mode is memory-mapped operation latency, not a synchronous durable-commit benchmark. TailCache's pilot phase must capture filesystem/mount/device metadata and check page-fault/writeback behavior before persisted latency distributions become reportable.

The current smoke harness deliberately uses the platform temporary directory. Before reportable runs, the persisted benchmark root must be configurable and the actual filesystem, mount, and backing device must be recorded. Cold/open behavior belongs in a separate experiment.

## Shared-cache concurrency design

The old `CacheSmokeBenchmark` remains `Scope.Thread`; increasing its thread count would create independent caches and must not be called shared-cache contention.

The new mixed workload uses a different state design:

- `CacheWorkloadState` -> `@State(Scope.Benchmark)`: one cache shared by all JMH workers in the trial;
- `WorkloadCursorState` -> `@State(Scope.Thread)`: one cursor per worker;
- each worker consumes a deterministic staggered position of the **same cyclic trace**;
- the worker's JMH thread index, trace size, and initial offset are resolved in `@Setup(Level.Iteration)`, outside the measured benchmark invocation.

The measured cursor path now only advances and wraps the already initialized per-thread cursor. This avoids relying on JIT optimization to remove repeated thread-index or trace-size plumbing from a nanosecond-scale benchmark.

The 16-thread experiment is therefore genuine same-JVM shared-cache contention, but its client model is specifically **staggered consumers of one shared deterministic trace**, not 16 independently generated request streams. If independent deterministic client streams are needed, they should be added explicitly as a separate concurrency sensitivity design rather than silently changing this workload.

It is still **not** a two-JVM Chronicle sharing experiment.

## Configuration export

Every trial prints one `[TailCache][workload-config]` record containing the experiment-relevant configuration:

- backend/storage mode;
- adapter summary, including persisted/in-memory mode and entry-checksum setting;
- state scope;
- configured and populated entry counts;
- payload size;
- trace size and seed;
- access pattern;
- Zipf exponent when applicable;
- requested read/write ratios;
- pre-boxed key representation;
- persisted temporary file path when applicable.

The Gradle smoke tasks also ask JMH to retain machine-readable JSON:

```text
build/reports/jmh/workload-smoke-1t.json
build/reports/jmh/workload-smoke-16t.json
```

JMH's own output remains the authority for thread count, fork/warmup settings and benchmark parameters.

## Diagnostic commands

One shared-cache worker:

```bash
./gradlew jmhWorkloadSmoke
```

Sixteen workers sharing the same cache:

```bash
./gradlew jmhWorkloadShared16Smoke
```

Both are deliberately short 1/1/1, 300 ms smoke runs. With 3 backend/storage modes x 2 payloads x 2 distributions x 2 mixes, each task expands to 24 primary parameter combinations.

**These latency numbers are not reportable research results.**

## Validation provenance

The full TailCache 05 validation bundle was run successfully on executable revision `d98be0f34202d7bb3421d6d2c692741db6fc6501`:

```bash
./gradlew test --rerun-tasks
./gradlew jmhSmoke
./gradlew jmhChronicleAllocSmoke
./gradlew jmhChronicleJfrSmoke
./gradlew jmhWorkloadSmoke
./gradlew jmhWorkloadShared16Smoke
```

That run established:

- [x] unit tests pass, including wrong-size constant-value and persisted close/reopen tests;
- [x] actual JMH forks use JDK 21.0.12.1 via the project toolchain;
- [x] benchmark VM options include `-Dchronicle.analytics.disable=true` exactly once per fork;
- [x] Chronicle config logs include `allowSegmentTiering=true`;
- [x] in-memory Chronicle logs `entryChecksums=false`, while persisted Chronicle logs `entryChecksums=true`;
- [x] TailCache 04 allocation/JFR classifications remain explainable after peer-review hardening;
- [x] `jmhWorkloadSmoke` expands all 24 mode/payload/distribution/mix combinations;
- [x] `jmhWorkloadShared16Smoke` reports 16 JMH threads and uses `stateScope=Benchmark(shared-cache)`;
- [x] persisted trials use unique temp files and leave no trial temp directories after successful teardown;
- [x] both workload JSON exports exist with 24 benchmark records each;
- [x] no smoke latency percentile is treated as a research conclusion.

The validation preserved the Chronicle operation-level allocation classification: ordinary hit allocation scaled with returned payload size, misses remained effectively allocation-free, and `putExisting` allocation stayed far below payload-size scaling. Representative JFR stacks again attributed hit allocation to `ByteArraySizedReader` materialization and put allocation to Chronicle Bytes/reference-counting machinery.

### Narrow rerun required after measured-path hardening

After that bundle, peer review moved JMH thread-index/trace-size cursor initialization from the measured mixed-workload invocation into `@Setup(Level.Iteration)`. This changes only the mixed benchmark plumbing, not the Chronicle adapter or operation-level smoke benchmark.

Before merge, rerun:

```bash
./gradlew test --rerun-tasks
./gradlew jmhWorkloadSmoke
./gradlew jmhWorkloadShared16Smoke
```

Required checks:

- [ ] tests compile and pass with JMH state dependency injection in cursor setup;
- [ ] 1-thread workload smoke still expands all 24 combinations and writes its JSON result;
- [ ] 16-thread workload smoke still reports 16 workers against `stateScope=Benchmark(shared-cache)`, expands all 24 combinations, and writes its JSON result;
- [ ] persisted trial temp directories are still absent after successful teardown.

A new Chronicle allocation/JFR run is not required for this cursor-only change unless the adapter or `CacheSmokeBenchmark` is modified again.

## Before the reportable campaign

TailCache 05 deliberately does not settle every methodology question. The next trustworthy-harness work must still:

- quantify trace-selection/branch/Blackhole harness floor;
- verify warmup and JIT compilation stability;
- freeze how Caffeine `maximumSize`, Chronicle `entries`, and resident working set are related;
- capture host/JVM/CPU/heap metadata;
- make the persisted benchmark root configurable and capture filesystem, mount and storage-device metadata;
- verify warm persisted trials are not dominated by first-touch faults or setup-induced writeback;
- decide whether the staggered shared-trace client model remains primary or whether an independent deterministic per-thread trace sensitivity is required;
- decide whether both 1-thread and 16-thread levels survive the pilot into the reportable matrix.

Only after those controls are frozen should the full Caffeine vs Chronicle in-memory vs Chronicle persisted-warm campaign be treated as research data.
