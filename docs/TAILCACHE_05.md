# TailCache 05 - workload distributions, persisted mode and concurrency matrix

## Goal

Expand TailCache from operation-level adapter smoke tests into a controlled mixed-workload harness without turning the smoke matrix into reportable results prematurely.

**Status: IMPLEMENTED - RUNTIME VALIDATION PENDING**

TailCache 05 adds three primary backend/storage modes:

1. Caffeine on-heap;
2. Chronicle Map in-memory/off-heap;
3. Chronicle Map persisted-warm using `createPersistedTo(...)`.

Two-JVM persisted sharing remains a separate secondary experiment.

## Peer-review blockers closed first

TailCache 05 starts from the TailCache 04 peer-review follow-up rather than expanding a known-noisy harness:

- `-Dchronicle.analytics.disable=true` is supplied to test and benchmark JVMs;
- `allowSegmentTiering(true)` is configured and logged explicitly;
- documentation no longer treats `maxBloatFactor(1.0)` as a guarantee that segments can never tier;
- the constant-size Chronicle adapter has a wrong-value-size negative test;
- backend configuration strings are described as experiment-relevant summaries rather than exhaustive internal configuration dumps.

These changes still require one final local rerun of the TailCache 04 validation bundle on the hardened head.

## Access distributions

The primary mixed workload uses:

- `UNIFORM`;
- `ZIPFIAN` with exponent/theta **0.99** as the initial skew value.

The 0.99 choice matches YCSB's long-standing default Zipfian constant and is frozen rather than tuned after seeing results. TailCache uses its own deterministic finite Zipf sampler; this is not a claim of byte-for-byte trace equivalence with YCSB's generators.

Zipfian CDF construction and random sampling happen while the trace is generated before measurement. Cache operations therefore do not pay for distribution generation or PRNG work.

Legacy `HOTSPOT` generation remains available for later sensitivity work but is not part of the TailCache 05 primary matrix.

## Exact read/update mixes

The primary mixed traces use:

- `READ_95_WRITE_5`;
- `READ_70_WRITE_30`.

The generator creates the exact number of reads over each complete trace and deterministically shuffles the operation flags. Key selection and operation selection use separate seeded random streams. Therefore changing 95/5 to 70/30 does not silently change the logical key sequence when the other workload parameters and seed are unchanged.

All mixed writes update existing keys. There are no inserts or misses in this mixed workload yet; hit/miss operation baselines remain in `CacheSmokeBenchmark`.

## Write-value control

One replacement `byte[]` is preallocated per logical key during trial setup. A write uses the replacement associated with the selected key.

This is intentional. Reusing one global replacement array for every key would progressively make many Caffeine entries point to the same Java object, reducing Caffeine's resident heap footprint in a way Chronicle Map cannot mirror because Chronicle serializes the bytes into its own storage. Per-key replacement payloads avoid that benchmark artifact while keeping allocation outside the measured path.

## Persisted Chronicle mode

`ChronicleStorageMode` distinguishes:

- `IN_MEMORY` -> `ChronicleMapBuilder.create()`;
- `PERSISTED` -> `ChronicleMapBuilder.createPersistedTo(tempFile)`.

Chronicle's own default is to store entry checksums for persisted maps but not purely in-memory maps. TailCache freezes that mode-dependent default explicitly with `checksumEntries(false)` for `IN_MEMORY` and `checksumEntries(true)` for `PERSISTED`, and logs `entryChecksums` in the adapter summary. This means the primary persisted mode represents Chronicle's normal persisted safety semantics rather than an artificially stripped-down mmap mode. If checksum cost needs to be isolated later, that belongs in a separate sensitivity experiment.

For `CHRONICLE_PERSISTED`, `CacheWorkloadState`:

1. creates a unique temporary directory and map path during `@Setup(Level.Trial)`;
2. creates the Chronicle Map at that path;
3. prepopulates the full resident working set before measurement;
4. runs the same deterministic trace as the other modes;
5. closes the map during `@TearDown(Level.Trial)`;
6. explicitly deletes the persisted file and temporary directory.

The adapter closes the map but deliberately does **not** delete persisted data itself. Persistence lifecycle and benchmark temporary-file cleanup are separate concerns. A unit test closes and reopens the same persisted file to verify that the stored value survives the adapter lifecycle, which also establishes the basic prerequisite for later process-sharing work.

### What “persisted-warm” means here

Prepopulation touches the mapped entry data before measurement, so the primary persisted mode is intended as a warm steady-state experiment rather than a map-open benchmark.

That is an experimental intent, not yet proof that all relevant pages stay resident or that writeback cannot disturb the run. TailCache's pilot phase must capture filesystem/mount/device metadata and check page-fault/writeback behaviour before persisted latency distributions become reportable.

Cold/open behaviour belongs in a separate experiment.

## Shared-cache concurrency design

The old `CacheSmokeBenchmark` remains `Scope.Thread`; increasing its thread count would create independent caches and must not be called shared-cache contention.

The new mixed workload uses a different state design:

- `CacheWorkloadState` -> `@State(Scope.Benchmark)`: one cache shared by all JMH workers in the trial;
- `WorkloadCursorState` -> `@State(Scope.Thread)`: one cursor per worker;
- each worker starts at a deterministic staggered trace offset derived from its JMH thread index.

This removes a global atomic cursor from the measured path and makes `-t 16` a real same-JVM shared-cache contention experiment.

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
- read/write ratios;
- pre-boxed key representation;
- persisted temporary file path when applicable.

The Gradle smoke tasks also ask JMH to retain machine-readable JSON:

```text
build/reports/jmh/workload-smoke-1t.json
build/reports/jmh/workload-smoke-16t.json
```

JMH's own output remains the authority for thread count, fork/warmup settings and benchmark parameters.

## New diagnostic commands

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

## Validation checklist

Run:

```bash
./gradlew test --rerun-tasks
./gradlew jmhSmoke
./gradlew jmhChronicleAllocSmoke
./gradlew jmhChronicleJfrSmoke
./gradlew jmhWorkloadSmoke
./gradlew jmhWorkloadShared16Smoke
```

Check:

- [ ] unit tests pass, including wrong-size constant-value and persisted close/reopen tests;
- [ ] benchmark VM options include `-Dchronicle.analytics.disable=true` exactly once;
- [ ] Chronicle config logs include `allowSegmentTiering=true`;
- [ ] in-memory Chronicle logs `entryChecksums=false`, while persisted Chronicle logs `entryChecksums=true`;
- [ ] TailCache 04 allocation/JFR classifications remain explainable after the peer-review hardening;
- [ ] `jmhWorkloadSmoke` expands all 24 mode/payload/distribution/mix combinations;
- [ ] `jmhWorkloadShared16Smoke` reports 16 JMH threads and uses `stateScope=Benchmark(shared-cache)`;
- [ ] uniform and Zipfian traces use the same fixed seed;
- [ ] 95/5 and 70/30 mixes log the expected ratios;
- [ ] persisted trials create unique temp files, complete successfully, and leave no trial files behind after normal teardown;
- [ ] JSON result exports are created for 1-thread and 16-thread smokes;
- [ ] no smoke latency percentile is promoted to a project conclusion.

## Before the reportable campaign

TailCache 05 deliberately does not settle every methodology question. The next trustworthy-harness work must still:

- quantify trace-selection/branch/Blackhole harness floor;
- verify warmup and JIT compilation stability;
- freeze how Caffeine `maximumSize`, Chronicle `entries`, and resident working set are related;
- capture host/JVM/CPU/heap metadata;
- capture persisted filesystem, mount and storage-device metadata;
- verify warm persisted trials are not dominated by first-touch faults or setup-induced writeback;
- decide whether both 1-thread and 16-thread levels survive the pilot into the reportable matrix.

Only after those controls are frozen should the full Caffeine vs Chronicle in-memory vs Chronicle persisted-warm campaign be treated as research data.
