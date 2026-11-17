# Cache-policy mechanism check — prospective plan, 17 November 2026

Motivation is the completed, independently reconciled saturated-service replication: at 512 B/zero ballast, reads contribute approximately 57–72% of observations strictly above Caffeine's combined p99.9 boundary, despite the fresh-update path. This supports a bounded policy sensitivity check; it does not identify the cause of individual slow reads. Caffeine's configured size bound tracks admission/eviction metadata even though this workload never exceeds the resident count, whereas Chronicle is not an automatic eviction cache. A whole-library comparison cannot isolate heap placement from that contract difference.

## Fixed budget and design

Run **512 B and 4 KiB, zero additional ballast, two fresh repetitions**, with four explicitly labelled configurations:

- Caffeine, existing size bound and default common-pool executor;
- Caffeine, the same size bound and a direct executor;
- Caffeine, unbounded and the default executor;
- ordinary in-memory Chronicle, unchanged capacity/tiering settings.

This is **16 workload JVMs**. Freeze a deterministic shuffled cell order and rotate/reverse arm order before collection; two repetitions are not perfect order balance. No adaptive extra cells or replacement forks. Use seed 24301, the 1,000,003-operation trace, 32,768 residents, 512 MiB G1, common offered 32 MiB/s churn and contiguous 12/2/30-second phases. Keep the existing service timing/classification boundary, immutable fresh writes and full value/resident validation. Primary endpoint is combined service p99.9; conditional read/update tails, p99/p99.99/p99.999, allocation, throughput, GC, trace coverage, RSS and demand losses are diagnostics. No timing-floor subtraction.

Declare the policy in source and raw configuration, including actual implementation class, size limit (or its absence), executor and frequency-sketch availability. Legacy constructor/enum paths keep their existing behavior; experimental modes require explicit selection. Unbounded Caffeine must not fail a validation that specifically requires a bounded-cache frequency sketch, and bounded arms must still satisfy that validation. Every arm must retain exactly the same logical entries and pass complete value checks.

Compile a separate runtime after all earlier performance collection ends, preserving earlier binaries and sources. Before research workloads, run one bounded functional qualification JVM covering all configurations and exact fresh-value equivalence, plus the same four matched timer/injected-stall/fresh-supply controls. Qualification/control failures block dependent collection; preserve failed attempts. Retain source/runtime copies and independent raw histogram/GC/event reconciliation. New allocation/host/JIT warnings remain visible. Data are never pooled with prior cohorts or used to retroactively change their endpoints.

## Interpretation and stopping

Compare default versus direct executor as an executor-policy sensitivity at the same declared size bound. Unbounded Caffeine changes policy, metadata, implementation layout and its capacity contract; it is **not** a fair drop-in replacement for an application requiring bounded automatic eviction, nor an isolated test of one instruction or heap placement. It is relevant here because there are no admissions beyond the fixed resident set or actual evictions. Do not replace the main bounded-library result with a favorable alternative.

Report every configuration/repetition, warning and contrary endpoint. A changed small-payload ordering would limit a heap-placement explanation; an unchanged ordering would not establish a unique cause. Two repeats are descriptive and cannot establish significance or a universal policy effect. Stop after the fixed 16 workloads, then audit and integrate the results. No additional pressure sweep is justified by this protocol.
