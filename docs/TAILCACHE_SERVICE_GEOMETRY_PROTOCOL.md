# Equal-array trace-pattern control — prospective plan, 17 November 2026

The completed 60-second-warmup baseline trace comparison reproduces opposite scheduled-response p99.9 directions: short-trace Caffeine is approximately 24–25 µs versus Chronicle 134–245 µs; long-trace Caffeine is approximately 8.6–8.8 ms versus Chronicle 160–223 µs. Two long-trace forks retain compiler warnings and one short-trace fork an external-CPU warning. This does not isolate trace coverage from its different retained array geometry. The effect is large enough to justify one compact control rather than another pressure sweep.

## Fixed eight-workload design

At **4 KiB/zero ballast**, compare both original backends with two trace patterns, **two paired repetitions per pattern: eight workload JVMs**. Both patterns retain precisely **1,000,003 long keys and 1,000,003 boolean read flags**, with identical primitive-array payload and types. Keep 32,768 cache residents, seed 24301, 512 MiB G1, 32 MiB/s common offered churn, ordinary immutable 95/5 operations, 50,000 intended arrivals/s and **60/4/30-second phases**. Every phase must complete all intended operations; paired write counts and trace fingerprints must match within a pattern. Freeze shuffled pattern/repetition order and alternating backend order before capture.

- **Uniform-long:** the existing deterministic 1,000,003-operation uniform trace.
- **Repeated-short in long arrays:** deterministically repeat the existing 40,001-operation trace into arrays of length 1,000,003. Truncation can slightly change the full-array operation mix; correct only the minimum required final operation flags to reach exactly 950,003 reads and 50,000 updates. Prefer keys already updated by the short source when converting a read to an update, preserving the small mutation set. Log corrections and actual distinct read/update keys. Do not retain the temporary short source after setup.

The repeated pattern is a new explicit workload, not an assertion of bit-for-bit equivalence to the original short-trace loop. Both cases have equal retained array lengths/types and should reproduce the same humongous-array region geometry. Verify actual GC-region metadata rather than assume equal total occupancy. Cache and application data remain identical in shape; logical operation order, active keys and mutation/lifetime patterns intentionally differ.

## Implementation and controls

Use a separate workload/runner class and separately compiled directory, preserving every earlier runtime. Its cache-operation body, service/queue-debt boundary and recording logic must match the prior runner, apart from the experimental workload type. Both treatments use this same new binary. Fresh uniform-long anchors are necessary because class/caller compilation can itself matter; never substitute historical long-trace numbers.

One bounded functional-qualification JVM must prove exact full-trace read/write counts, equal long-array geometry, distinct pattern fingerprints, small versus broad mutation coverage, full backend value/resident correctness, and no retained short-source field. Then run four matched **60/4/4-second** arrival controls: timer floor, injected 20 ms stall, fresh-supply floor under each pattern. Controls verify request accounting, per-bin union and pause visibility; no floor subtraction or observer-neutrality claim.

Capture source/runtime/dependency/qualification bindings, raw per-operation HDRs and timestamps, per-phase allocation/churn/compiler counters, actual GC intervals/regions, sampled RSS and host metadata. Preserve every source, failure, warning and contrary fork. Independent raw and GC/event reconciliation is required. Source/runtime remain frozen throughout collection and audits; never overlap performance JVMs.

## Interpretation and stopping

Primary endpoint is scheduled-response **p99.9**. Paced service and p99/p99.99/p99.999, survival/stall probabilities, allocation, GC, throughput and occupancy are secondary diagnostics. No endpoint replacement or pooled fork percentiles.

A persistent direction difference would show that unequal raw trace-array geometry is insufficient to explain the response result. It would still be a **logical trace-pattern sensitivity**, not isolation of mutation-set size alone: active read keys, temporal ordering and lifetime patterns change together. A smaller, mixed, absent or reversed effect is also informative and must narrow the paper's claims. Fixed warmup does not prove steady state; all compiler warnings remain visible.

Stop after the fixed eight workloads and their audits. No pressure expansion, new pattern or favorable replacement is triggered by this protocol. Two pairs are descriptive and do not establish a precise crossover, significance or a general production workload model.
