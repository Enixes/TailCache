# TailCache 08 — final baseline review (2026-10-04)

## Final decision

**TailCache 08 is closed, but its latency numbers are not promoted as reportable research results.** The access-cost harness, provenance capture, counterbalanced ordering, persisted diagnostics and quality gate are implemented and exercised. A cleaner second full candidate removed the host/page-state failure seen in candidate A, and a targeted longer replication repaired the earlier cross-order p99 instability. However, separate compiler diagnostics still show material whole-JVM compilation throughout measurement, so the JIT/warmup acceptance gate remains open.

This is a valid negative gate result. TailCache 08 must not be stretched into RQ1/RQ2: the workload still retains the Chronicle replacement-value bank on heap and does not implement the live-set/GC-pressure crossover experiment.

## Evidence sequence

### Candidate A — rejected for host instability

`08-candidate-20261004-a` used 8 warmups, 5 measurements and 2 primary forks. It completed, but the host accumulated swap and memory pressure and the reverse-order 4-KiB block slowed all three backends dramatically. That run remains a negative pilot; see `TAILCACHE_08_CANDIDATE_REVIEW.md`.

### Candidate B — cleaner host, narrower failure

`08-candidate-20261004-b` ran the same complete 12-block matrix from clean commit `9033e608246959784af10cd23c933a43922adf70`.

- every invocation exited successfully;
- memory full PSI was 0.00 at every recorded block boundary;
- swap use fell rather than rose in every block;
- all six OS-counter diagnostic conditions recorded zero major faults and zero process read bytes;
- all 4-KiB counterbalanced p99 ratios were within the 1.25 screening limit;
- persisted 256-B p99 was stable (2788 ns vs 2728 ns);
- Caffeine 256-B p99 was 2448 ns vs 1328 ns (1.84x);
- Chronicle in-memory 256-B p99 was 3072 ns vs 2204 ns (1.39x).

The second candidate therefore ruled out the broad host-collapse explanation from candidate A but still failed the 8/5/2 p99 replication screen.

## Targeted replication and protocol repair

A clean-host diagnostic repeated only the unresolved 256-B latency conditions without CPU affinity, using **12 one-second warmups, 8 one-second measurements and 3 independent forks** in both backend orders. Memory PSI remained 0.00 during the probes.

| Backend | Order A p99 | Order B p99 | Ratio |
|---|---:|---:|---:|
| Caffeine | 2275.08 ns | 2288 ns | 1.006x |
| Chronicle in-memory | 2884 ns | 3100 ns | 1.075x |
| Chronicle persisted | 2480 ns | 2772 ns | 1.118x |

The same protocol retained roughly 0.55–0.87 million sampled invocations per backend/order block. This shows that the two-order aggregate instability can be controlled by stronger replication. A single-CPU `taskset` probe was explicitly rejected because pinning the entire Gradle/JMH/compiler process set to one logical CPU starved JIT/helper work and changed the benchmark environment rather than merely reducing scheduler migration.

The TailCache 08 runner and Gradle task defaults are therefore raised from 8/5/2 to **12/8/3**. The 1.25 counterbalanced p99 screen remains a descriptive replication gate, not a significance test.

## JIT gate remains failed

Longer warmup did **not** establish a compilation-free measurement interval. A separate 12/8/1 compiler diagnostic for 256-B recorded:

- Caffeine: 246 ms of profiled compiler time over 8 measured seconds;
- Chronicle in-memory: 190 ms;
- Chronicle persisted: 167 ms.

The compiler activity was not confined to the first measured iteration. For example, Caffeine reported per-iteration compiler times of 14, 10, 14, 4, 16, 58, 96 and 34 ms. Chronicle conditions likewise showed non-monotonic compilation later in measurement.

These are whole-JVM compiler counters from separate diagnostic forks, not proof that the benchmark method itself was recompiled and not a latency correction. But they fail the deliberately conservative 1% screening policy and prevent a claim that the primary measurement interval is JIT-stable.

## Persisted-state interpretation

Candidate B materially improved the persisted evidence: diagnostic forks recorded zero major faults and zero process read bytes for both payload sizes, with no boundary memory pressure. This is encouraging evidence for the prefault path, but the counters are still process-wide and come from separate forks. They do not prove residency of each unprofiled primary fork. Persisted mode therefore remains a secondary deployment stratum rather than a headline result.

## Closure and hand-off to the primary study

TailCache 08 is complete as an engineering/research gate:

1. the harness and raw-evidence pipeline work;
2. the catastrophic host-instability failure was reproduced and removed on a cleaner interval;
3. insufficient replication at 256 B was identified and repaired by the 12/8/3 minimum;
4. CPU pinning was tested and rejected as a confounding control on this host;
5. the remaining JIT-stability limitation is explicit rather than hidden.

No TailCache 08 backend ranking should be published. The next primary work is the Milestone-1/Milestone-2 crossover harness: pause-sensitive latency validation, backend-neutral allocation/churn, live-set pressure controls, removal of the Chronicle heap shadow bank, and the actual RQ1/RQ2 sweep.
