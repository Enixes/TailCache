# TailCache 07 review and 08–10 execution plan

**Prepared before implementation.** Source tasks: TickTick TailCache 07, 08, 09, and 10. The 07 pilot is diagnostic and failed its warm-state, JIT, and run-stability gates; its numbers cannot be promoted to baseline evidence.

## Sequence and acceptance gates

### 1. Repair and review TailCache 07

Audit the exact JMH workload boundary, trace/branch floor, Blackhole and observable writes, persisted prefault path, process-counter attribution, analytics/tiering controls, configuration exports, and raw evidence. Split unprofiled latency from compiler/OS-counter diagnostic forks. Retain a researcher review that distinguishes verified controls from unverified assumptions. Validate compilation, unit tests, setup/teardown, and a focused persisted fork.

**Gate:** 07 is code-valid when the checks pass. It becomes *measurement-valid* only when warmup/JIT, host stability, and persisted page-state evidence pass on a quiet host. Code validity alone must not promote the 07 pilot data.

### 2. TailCache 08: minimum baseline matrix

Freeze one worker, uniform access, a 95/5 read/existing-key-put mix, 256 B and 4 KiB payloads, and a stated 2,048-resident/4,096-configured occupancy protocol for the **baseline access-cost** question. Run Caffeine and Chronicle in-memory as the primary single-JVM pair. Run persisted Chronicle on the same factor levels as a clearly marked warm deployment-mode stratum; reject any condition that fails the warm-state gate. Counterbalance backend order across repeated runs. Keep unprofiled SampleTime JSON/CSV separate from JFR, compiler, OS-counter, and GC diagnostics. Capture JDK/flags, code revision, trace fingerprint, system/storage metadata, raw failures, and integrity checks. Do not call these data a heap-pressure crossover experiment: the current replacement bank shadows off-heap payloads on the Java heap.

**Gate:** A baseline condition is eligible only if its setup/teardown and raw artifact checks pass, measured JIT activity and host disturbance are acceptably small, repeat runs agree at the planned effect scale, and persisted conditions show no material page-fault or storage disturbance. If the host fails, retain the run as a negative pilot and mark the reportable matrix incomplete.

### 3. TailCache 09: isolated sizing-misestimation experiment

Implement an explicit Chronicle-only sizing study. Vary configured average value size against actual fixed payload sizes, with the existing constant-size builder as a reference. Record target entries, actual successful inserts, first failure type/message, file/off-heap size when measurable, and resolved configuration. Benchmark throughput and SampleTime on a stable, prefilled subset below the observed capacity boundary; keep insertion-to-failure timing out of steady-state latency. Use deterministic synthetic keys/values and independent fresh maps. Validate that perturbations really change layout/capacity and that failures are retained rather than hidden.

**Gate:** Review whether each condition measures sizing rather than changing data semantics or mixing capacity exhaustion into steady-state latency. This is a separate sensitivity result and cannot repair an invalid 08 baseline.

### 4. TailCache 10: secondary-work decision

Record a reproducible go/no-go decision using schedule, RQ1/RQ2 quality, and persisted-warm quality. If either primary question or persisted data is unsound, defer two-JVM sharing, `getUsing`, and cold/open expansion. If sound, prioritize two-JVM sharing, then `getUsing`/reuse, then cold/open behavior. Eviction simulation is the first cut. TailCache 09 tooling may exist regardless, but a failed gate bars its use as an explanation of a primary crossover.

## Research review after each step

After 07, 08, and 09: review construct validity, confounders, measurement boundaries, sample and replication adequacy, missing or excluded conditions, negative results, and exact claim limits. Record concrete fixes and rerun the narrowest affected check. After 10: audit that the decision follows the recorded quality/schedule evidence and does not silently promote secondary diagnostics.
