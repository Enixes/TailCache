# TailCache 06 - latency, allocation and GC result pipeline

**Status: IMPLEMENTED - RUNTIME VALIDATION PENDING**

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
   - TailCache `GcPauseProfiler` for G1 stop-the-world pause count, total and max.

The result summarizer joins the three records by benchmark name, thread count and JMH parameters.

## Why GC pauses have their own profiler

JMH's built-in GC profiler obtains collection count/time from `GarbageCollectorMXBean` and allocation data from HotSpot allocation counters. Its `gc.time` is therefore retained as **collector-reported collection time** and is not renamed to "pause time".

TailCache additionally enables JDK 21 unified logging for the profiled fork:

```text
-Xlog:gc=info:file=<raw-log>:uptimemillis,level,tags:filecount=0
```

`GcPauseProfiler` parses only completed G1 `Pause ... <duration>` records whose uptime timestamps fall inside JMH's measurement window. It exports:

- `gc.pause.count`
- `gc.pause.time`
- `gc.pause.max`

Concurrent G1 phases are deliberately not counted as stop-the-world pauses. Raw GC logs are retained for auditability.

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
  run-metadata.json
  summary.json
  summary.csv
```

Candidate runs use the same structure under:

```text
build/reports/tailcache06/run/
```

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

## Interpretation guardrails

- Latency, throughput and GC/allocation numbers come from **separate runs** with the same parameterization. They can explain the same condition, but are not event-by-event correlated.
- JMH SampleTime measures a sampled operation-latency distribution under closed-loop worker load.
- `gc.time` and `gc.pause.time` are different metrics and must remain separately named.
- p99.9 is only meaningful when the retained sample count is sufficient; the summary includes that count rather than hiding it.
- Smoke results validate the pipeline only.
- The current mixed-workload replacement-value bank still prevents this TailCache 05 workload from making heap-footprint/GC-savings claims. The dedicated pressure workload remains a separate Milestone 1 requirement.

## TailCache 05 measured-path cleanup

The last TailCache 05 peer review found that the existing-key put branch resolved the trace logical index twice. TailCache 06 resolves each trace entry once and reuses that logical index for both key and replacement-value lookup. This closes the post-merge measured-path cleanup before building the result pipeline on top of it.
