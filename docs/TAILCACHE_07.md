# TailCache 07 — pilot matrix and bias controls

**Status: diagnostic pilot completed; latency results rejected for research use.**

## What changed

- `traceAndBranchFloor` measures deterministic trace lookup, branch selection, and Blackhole cost without a cache operation. It is a diagnostic lower bound, never a value to subtract from cache latency.
- Mixed read results go to JMH `Blackhole`. Trial teardown checks how many resident entries hold the replacement value, so the write branch has an observable effect. The floor benchmark should leave zero entries updated.
- Persisted trials can use `-Dtailcache.persistedRoot=...` instead of the platform temporary directory. Trial setup loads the file into the page cache and sweeps all resident keys through Chronicle's own mapping. Before each timed iteration the final harness touches the mapped file pages without materializing a fresh payload per entry. Map files are still closed and deleted at trial teardown.
- Linux pilot OS counters record minor/major process faults and process read/write bytes around each JMH iteration. These profiler envelopes include iteration setup and JVM activity; they are conservative disturbance indicators, **not** map-specific or exact timed-operation attribution.
- The pilot task now pins G1 and a 512 MiB heap (`-Xms512m -Xmx512m`), retains raw JMH histograms, and runs JMH's compiler profiler. The first two exploratory matrices below predate the heap/JIT-profiler addition and are identified separately.
- The normal TailCache 05/06 tasks select `mixedWorkload` explicitly, so adding a floor benchmark does not silently expand their matrix.
- `tailCache07OpenDiagnostic` separately measures map reopen and first/second full-key sweeps. It does not evict the OS page cache and therefore must not be called a true cold-cache measurement.

## Focused pilot actually run

All mixed runs used one worker, uniform access, 95% reads / 5% existing-key puts, 2,048 resident keys, a 100,000-entry deterministic trace from seed `0x5EED`, Java 21.0.12.1, and G1. Each exploratory condition used eight 1 s warmups, five 1 s measurement iterations, and two forks.

| Run | Conditions | Purpose |
|---|---|---|
| `matrix-1t-a` | Caffeine, Chronicle in-memory, Chronicle persisted × 256 B, 4 KiB | Initial narrow matrix |
| `matrix-1t-b` | Same three modes, 256 B, reverse backend order | Run-to-run check and write-observation check |
| `floor-1t` | Caffeine trial state, 256 B, floor method | Harness floor |
| `jit-pinned-1t` | Caffeine and persisted Chronicle, 256 B, one fork | Fixed-heap compiler diagnostic; not directly comparable to unpinned runs |
| `postfix-validation` | Persisted Chronicle 256 B, one fork, two warmups | Short functional check of allocation-free mapped-page touches; not a stable latency run |
| `open-diagnostic` | Five new-file reopen trials each at 256 B and 4 KiB, fixed 512 MiB heap | Separate open/first-touch behavior |

The raw JSON, JMH text, per-fork OS CSVs, environment snapshots, and analysis table are retained with the pilot artifact bundle. The local checkout also retains them under `build/reports/tailcache07/` until cleaned.

The exploratory matrices and fixed-heap JIT diagnostic used an earlier iteration setup that swept resident keys via ordinary Chronicle `get()`. That prefaulted Chronicle's own mapping but also materialized payload arrays before every timed iteration, adding avoidable garbage. The final harness replaces that repeated sweep with allocation-free mapped-page touches; the earlier data remain useful as bias diagnostics only. A short post-fix validation is retained separately and is not folded into the pilot comparison.

The post-fix validation completed and deleted its map file. It recorded zero major faults and zero process reads in five measurement envelopes, but one envelope still recorded 26,390,528 process write bytes. This is process-wide I/O rather than proof of a particular Chronicle writeback event. It is enough to keep the warm persisted acceptance gate open.

## Bias checks and observed failures

| Check | Evidence | Decision |
|---|---|---|
| Harness floor | Floor p50 39 ns, p99 840 ns; initial Caffeine 256 B p50 88 ns, p99 1,130 ns. Floor p99 is large relative to the cache signal. | Do not subtract floor or claim small tail differences are resolved. |
| Dead-code elimination | Every reverse-order mixed fork ended with 1,888 / 2,048 entries holding the replacement payload; both floor forks ended with zero. Reads are consumed by JMH Blackhole. | The measured branches have observable effects; no DCE evidence in this pilot. |
| Warmup / JIT | Eight warmup iterations still showed large swings. In the separate fixed-heap compiler diagnostic, JMH reported 108 ms of total JVM compilation during five Caffeine measurement iterations and 201 ms for persisted Chronicle. This is whole-JVM compiler activity, not proof that the benchmark method itself was recompiled. | JIT/warmup stability is **not established**. |
| Cache/page state | Persisted 4 KiB in `matrix-1t-a` had two major process faults and 35,724 minor faults in measurement envelopes. Persisted 256 B in `matrix-1t-b` had 1,033 major faults, 78,180,352 process read bytes, and 5,586,944 process write bytes. The envelope includes setup and unrelated JVM activity, but this level of disturbance invalidates the warm-state claim. | Reject these persisted latency distributions as warm steady-state measurements. |
| Run-to-run variance | Caffeine 256 B p99 changed from 1,130 ns to 2,460 ns; p50 changed from 88 ns to 101 ns. Persisted 256 B p99 changed from 2,008 ns to 2,488 ns while the second run faulted heavily. | The host/run state overwhelms precise comparisons. |
| Outliers | Persisted 256 B had 5 samples over 100 µs in the first run and 116 in the second. Persisted 4 KiB had 69 such samples in one run. JMH SampleTime can miss rare stalls altogether. | Keep raw histograms; do not report p99.9 as an established cache effect. |
| Analytics and tiering | Every pilot JMH JSON record had exactly one `-Dchronicle.analytics.disable=true`; workload setup fails if it is absent. Chronicle config logs include `allowSegmentTiering=true`, `maxBloatFactor=1.0`, and checksum/storage mode. | Controls verified. |
| Storage environment | Persisted root was on `/dev/sda2`, ext4, a nonrotating `HFS128G39TND-N21` device; `/tmp` was tmpfs. CPU governor was `powersave`. The 7.6 GiB host had about 8.6 GiB swap used in the during-pilot snapshot; five-minute memory and I/O pressure was substantial. | The machine was not quiet enough for reportable tail latency. |

The 16-worker candidate was not run after the one-worker warm-state and stability gates failed. It would add contention and oversubscription (16 workers on 12 logical CPUs) without making the baseline interpretable.

## Cold/open diagnostic boundary

The separate reopen test includes constructor/open time, then two full-key sweeps. Across five repetitions per payload, open time ranged from about 2.6 to 31.1 ms; first sweeps ranged from about 2.4 to 44.5 ms. The variability and uncontrolled OS page cache preclude a cold-cache latency estimate. These observations are intentionally excluded from the warm JMH sample distributions.

## Rerun gates

1. Use a quiet host with memory headroom, little or no swap activity, and recorded CPU frequency/thermal state. Keep persisted storage on a specified filesystem and retain mount/device metadata.
2. Keep the 512 MiB fixed heap, G1, analytics-disabled flag, and explicit tiering/checksum summaries. Reevaluate the heap size if the future pressure workload needs a different setting; pin it per campaign.
3. Pilot warmup again with compiler profiling. Accept a setting only after late warmup and measured-iteration distributions are stable and measurement-period compiler activity is negligible. A benchmark-specific compilation log can resolve any ambiguity left by whole-JVM compiler time.
4. For persisted-warm cases, inspect per-iteration faults and process I/O after prefaulting. Any major fault or material read/write disturbance triggers investigation; use map-specific tracing if attribution is needed. Never mix reopen/first-touch time into the warm distribution.
5. Compare replicated runs and raw histograms. Pre-register a stability threshold based on the effect size the study aims to resolve; do not hide failed conditions or pool across materially different run states.
6. Only then pilot shared-worker contention and the separate GC-pressure crossover workload. The present replacement-value bank remains an on-heap shadow set, and the current 2,048/4,096 occupancy setting is not a frozen crossover protocol.

## Commands

```bash
./gradlew --offline tailCache07Pilot -Ptailcache07RunId=pilot-a
./gradlew --offline tailCache07Pilot -Ptailcache07RunId=pilot-b -Ptailcache07Modes=CHRONICLE_PERSISTED,CHRONICLE_IN_MEMORY,CAFFEINE -Ptailcache07Payloads=BYTES_256
./gradlew --offline tailCache07Pilot -Ptailcache07RunId=floor -Ptailcache07Benchmark=traceAndBranchFloor -Ptailcache07Modes=CAFFEINE -Ptailcache07Payloads=BYTES_256
./gradlew --offline tailCache07OpenDiagnostic
```

`tailcache07Threads`, `tailcache07WarmupIterations`, and `tailcache07Forks` can narrow or extend the pilot deliberately. The task is diagnostic and does not promote its output to the TailCache 06 result pipeline.
