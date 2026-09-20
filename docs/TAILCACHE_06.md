# TailCache 06 - latency, allocation and GC result pipeline

**Status: VALIDATED - FINAL SMOKE + RAW RECONCILIATION PASSED AT `374cb697`**

## Purpose

TailCache 06 turns benchmark output into an analysis-ready record for the north-star question:

> At what JVM heap/live-set pressure does the GC benefit of moving cache data off-heap outweigh Chronicle Map's higher ordinary access/materialization cost?

The pipeline intentionally separates latency measurement from profiling so instrumentation does not become part of the latency result.

## Three-run measurement design

For the same benchmark parameters TailCache 06 runs three JMH trials:

1. **Latency** - unprofiled `Mode.SampleTime`, nanoseconds.
   - source of p50 / p95 / p99 / p99.9;
   - JMH raw sample histogram is retained;
   - this is the latency distribution used for crossover analysis.

2. **Throughput** - unprofiled `Mode.Throughput`, ops/s.
   - supporting context only;
   - it is a separate run and must not be treated as temporally simultaneous with the latency samples.

3. **Allocation / GC** - `Mode.Throughput` with:
   - JMH built-in `gc` profiler for `gc.alloc.rate`, `gc.alloc.rate.norm`, `gc.count` and `gc.time`;
   - TailCache `GcMeasurementWindowProfiler` to record the JMH internal-profiler envelope around each measurement iteration;
   - TailCache `G1GcLogProfiler` to retain raw G1 logs and derive stop-the-world pause count, total and max from those envelopes.

The result summarizer joins the three records by benchmark name, thread count and JMH parameters.

## Why GC pauses have their own profiler

JMH's built-in GC profiler obtains collection count/time from `GarbageCollectorMXBean` and allocation data from HotSpot allocation counters. Its `gc.time` is therefore retained as **collector-reported collection time** and is not renamed to "pause time".

TailCache additionally enables JDK 21 unified logging for the profiled fork:

```text
-Xlog:gc=info:file=<raw-log>:timenanos,level,tags:filecount=0
```

HotSpot's `timenanos` decorator is correlated with the `System.nanoTime()` start/end sidecar recorded by the internal profiler for each JMH measurement iteration. JMH deliberately starts internal profilers before worker submission and stops them after workers finish, so this is a **measurement-iteration profiler envelope**, not the exact 300 ms/1 s workload timer boundary. `G1GcLogProfiler` parses completed G1 `Pause ... <duration>` records inside that envelope. It exports:

- `gc.pause.count`
- `gc.pause.time`
- `gc.pause.max`

Concurrent G1 phases are deliberately not counted as stop-the-world pauses. Raw GC logs **and the measurement-window sidecars** are retained for auditability.

The parser is intentionally G1-specific. TailCache 06 pins `-XX:+UseG1GC`; a future ZGC sensitivity study must use collector-appropriate instrumentation rather than silently reusing the G1 parser.

## Primary default scope

The TailCache 06 tasks default to:

```text
CAFFEINE,CHRONICLE_IN_MEMORY
threads=1
```

This is deliberate: the result pipeline supports the GC-pressure crossover study first. Persisted Chronicle remains a secondary deployment-mode question.

Override these only for a deliberate pilot, for example:

```bash
./gradlew tailCache06Smoke -PtailcacheThreads=16
./gradlew tailCache06Smoke -PtailcacheModes=CAFFEINE,CHRONICLE_IN_MEMORY,CHRONICLE_PERSISTED
```

## Tasks

Short pipeline validation:

```bash
./gradlew tailCache06Smoke
```

Candidate run using the benchmark class's 5 warmup / 5 measurement / 3 fork defaults:

```bash
./gradlew tailCache06
```

The candidate task is **not automatically a reportable experiment**. Heap pressure, occupancy semantics, environment controls, workload replication and warmup stability still need to be frozen first.

## Output layout

Smoke:

```text
build/reports/tailcache06/smoke/
  latency.json
  latency.txt
  throughput.json
  throughput.txt
  gc-profile.json
  gc-profile.txt
  gc/
    gc-<benchmark-and-params>-<pid>.log
    gc-<benchmark-and-params>-<pid>.windows.csv
  run-metadata.json
  summary.json
  summary.csv
```

Candidate runs use the same structure under:

```text
build/reports/tailcache06/runs/<run-id>/
```

Pass a deliberate run id when retaining candidate data, for example:

```bash
./gradlew tailCache06 -PtailcacheRunId=20260920-pilot01
```

If no run id is supplied, the non-reportable default directory is `runs/candidate/`.

## Summary schema

Each joined row contains:

- backend/storage mode and workload parameters;
- thread count;
- latency p50 / p95 / p99 / p99.9 and sampled-observation count;
- throughput and unit;
- allocation MB/s and B/op;
- MXBean collection count/time;
- G1 pause count/total/max;
- JMH/JDK/VM/fork/warmup/measurement metadata.

`run-metadata.json` additionally records:

- Git commit and dirty-tree status;
- Java executable/version used by the Java 21 toolchain;
- Gradle/JMH/backend/result-tool versions;
- collector;
- selected TailCache modes/threads;
- metric provenance and expected raw files.

## Validation provenance

Initial end-to-end smoke validation passed at tested Git head `51ae404449166e5a9d2cedc12aaa478d5a115133` on 2026-09-20:

- Java/Gradle compilation and unit tests passed;
- the smoke pipeline completed successfully with configuration cache stored;
- the default scope expanded to 16 joined rows: 2 backends x 2 payloads x 2 access distributions x 2 read/existing-key-put mixes;
- one G1 raw log and one measurement-window sidecar were retained per profiled condition;
- run metadata recorded a clean tested tree and the Java 21 benchmark executable;
- the summary schema and row count were produced successfully.

That validation predates a post-review profiler-ordering fix which places the measurement-window profiler outside JMH's built-in GC profiler. Because that change affects allocation/collection attribution, the current head requires one final smoke rerun before TailCache 06 can be marked validated.

The retained raw JSON / GC artifact bundle is also required for the final manual reconciliation of percentiles, allocation/collection metrics and pause totals.

## Final validation provenance

Final post-review smoke validation passed at exact tested Git head `374cb697fe9738acf458944e8743797a99ac5b33` on 2026-09-20 with a clean working tree.

The retained artifact bundle was reconciled manually against the generated summary:

- all three JMH sources contained exactly 16 matching conditions: 2 backends x 2 payloads x 2 access distributions x 2 read/existing-key-put mixes;
- the summary's p50 / p95 / p99 / p99.9 values matched the raw JMH SampleTime JSON exactly for every condition;
- retained SampleTime histogram counts matched the summary for every condition (6,246 to 11,347 samples in this short smoke);
- throughput values matched the separate unprofiled Throughput JSON exactly;
- allocation MB/s and B/op plus JMH `gc.count` / `gc.time` matched the profiled JMH JSON exactly;
- 16 raw G1 logs and 16 measurement-envelope sidecars were retained, one pair per profiled condition;
- G1 pause count / total / max in the summary matched an independent re-parse of every raw log against its recorded `System.nanoTime()` envelope exactly;
- the smoke exercised both zero-pause and non-zero-pause paths: Caffeine had no G1 collections in the profiled 300 ms windows, while Chronicle conditions recorded 5-9 pauses;
- the recorded profiler envelopes were about 303-312 ms around the configured 300 ms measurement, which is consistent with JMH's documented internal-profiler placement outside the worker timing boundary;
- the Java 21 benchmark JVM was explicitly pinned to G1 and Chronicle analytics remained disabled;
- metadata recorded the exact tested Git head, `gitDirty=false`, JMH 1.37, Caffeine 3.2.4 and Chronicle Map 2026.1.

As an additional mechanism sanity check, Chronicle's mixed-workload allocation rates were consistent with the earlier operation-level allocation measurements: approximately 268 B/op for the 256 B 95/5 cases and 3.92 KiB/op for the 4 KiB 95/5 cases, with the 70/30 mixes dropping as expected because existing-key puts allocate far less than ordinary Chronicle reads.

This validation establishes that the **result pipeline** is internally consistent. It does not make the smoke latency values reportable research results.

## Interpretation guardrails

- Latency, throughput and GC/allocation numbers come from **separate runs** with the same parameterization. They can explain the same condition, but are not event-by-event correlated.
- JMH SampleTime measures a sampled operation-latency distribution under closed-loop worker load.
- JMH `SampleTime` randomly samples benchmark invocations rather than timing every cache operation. This is appropriate for ordinary percentile estimation, but a rare stop-the-world pause can be missed if the invocation spanning that pause was not selected for sampling. **Do not interpret a low sampled p99/p99.9 as proof that GC pauses did not affect service latency.** The crossover study must validate pause sensitivity separately before reportable conclusions.
- `gc.time` and `gc.pause.time` are different metrics and must remain separately named.
- GC pause totals are attributed to the JMH internal-profiler envelope around a measurement iteration; they are not claimed to be event-by-event correlated with the separate unprofiled latency samples.
- p99.9 is only meaningful when the retained sample count is sufficient; the summary includes that count rather than hiding it.
- Smoke results validate the pipeline only.
- The current mixed-workload replacement-value bank still prevents this TailCache 05 workload from making heap-footprint/GC-savings claims. The dedicated pressure workload remains a separate Milestone 1 requirement.

## TailCache 05 measured-path cleanup

The last TailCache 05 peer review found that the existing-key put branch resolved the trace logical index twice. TailCache 06 resolves each trace entry once and reuses that logical index for both key and replacement-value lookup. This closes the post-merge measured-path cleanup before building the result pipeline on top of it.
