# TailCache 08 full candidate — researcher review (2026-10-04)

> **Historical note:** this file reviews candidate A only. Candidate B and the final 12/8/3 stability probes supersede its next-attempt section; see `TAILCACHE_08_FINAL_REVIEW.md`.


## Decision

**Reject the full candidate for performance claims.** The complete 12-block run (`08-candidate-20261004-a`) executed from the clean `3899f27` checkout with eight one-second warmups, five one-second measurements, and two unprofiled primary forks for each backend/payload/order condition. Separate one-fork compiler/OS and JFR blocks also completed. All JMH tasks exited successfully, raw hashes and factor checks passed, source fingerprints stayed fixed, and six JFR recordings were retained. The quality gate failed because host conditions and run-to-run tail latency were unstable.

## Primary latency stability

The table gives the unprofiled mixed-workload p99 in nanoseconds. Order A was Caffeine → Chronicle in-memory → persisted; order B reversed it. The 1.25 ratio was encoded in the runner before this candidate, but it is a screening threshold, not a significance test.

| Payload | Backend | Order A p99 | Order B p99 | Larger/smaller |
|---|---|---:|---:|---:|
| 256 B | Caffeine | 3,080 | 2,756 | 1.12× |
| 256 B | Chronicle in-memory | 3,624 | 4,120 | 1.14× |
| 256 B | Chronicle persisted | 2,584 | 6,232 | 2.41× |
| 4 KiB | Caffeine | 2,144 | 64,128 | 29.91× |
| 4 KiB | Chronicle in-memory | 19,296 | 112,325 | 5.82× |
| 4 KiB | Chronicle persisted | 21,103 | 73,344 | 3.48× |

The reverse-order 4-KiB slowdown affected **all three backends**, including Caffeine. Caffeine's p50 moved from 86 to 788 ns. Within that reverse block, Caffeine's two forks were themselves different: the first fork's approximate p99 from raw histograms was 64,640 ns and the second 63,360 ns, whereas both first-order forks were around 1,852–2,440 ns. Chronicle in-memory and persisted forks were also substantially elevated. This pattern argues against interpreting the difference as a backend effect. It is consistent with host disturbance, though the available counters do not identify a single cause.

## Host, JIT and persisted-state evidence

- The 20-minute run began with about 2.4 GiB of swap in use and ended near 5.3 GiB. Swap use rose about 0.85 GiB during the first 256-B latency block and 1.63 GiB during the reverse 4-KiB latency block. Some block-boundary memory `full` PSI 10-second averages exceeded 1%; the 4-KiB diagnostic block ended near 14%. Boundary snapshots can miss disturbances within a block, so these are lower-resolution warnings. The host used a `powersave` CPU governor. The persisted files were on ext4 `/dev/sda2` with `rw,noatime`, backed by a nonrotating SATA device.
- Separate compiler diagnostic forks recorded 62–173 ms of whole-JVM compiler time during five measured seconds, above the audit's conservative 1% screening threshold. Eight warmup iterations did not establish a compilation-free interval. These values cannot identify the compiled method and are not latency corrections.
- The 256-B Chronicle in-memory diagnostic fork recorded 242 process major faults during measurement; other diagnostics recorded zero major faults. Persisted diagnostics recorded 8 KiB and 4 KiB of process read bytes for 256 B and 4 KiB respectively, with zero major faults. These counters cover the whole profiled JVM, not a specific map access, and were gathered in separate forks. Thus they cannot prove warm residency of the unprofiled persisted forks. The 4-KiB persisted diagnostic wrote about 40 MiB during measurement; mixed puts legitimately dirty mapped pages, so write bytes alone do not identify cold/open contamination.

## Construct and inference limits

This remains an all-hit, one-worker, 95/5 read/existing-key-put access-cost protocol at 2,048 resident and 4,096 configured entries. It is not a live-heap-pressure or GC-tail crossover experiment: the replacement-value bank shadows Chronicle values on the Java heap. SampleTime p99 and p99.9 are sampled invocation tails, not pause-sensitive response-time percentiles. The two order blocks and two forks do not support a backend rank after the observed host-wide shifts. Do not selectively promote the two 256-B in-memory conditions that passed the ratio screen; the candidate as a whole and its common host were unstable.

The updated `scripts/tailcache08.py` now writes explicit host swap/PSI and diagnostic compiler/fault observations into derived `quality.json`, using screening thresholds: more than 256 MiB swap growth in a block, more than 1% memory `full` PSI at a block boundary, more than 1% measured compiler time, or any diagnostic major fault. **Those host and diagnostic thresholds were added after inspecting this candidate** and are descriptive sensitivity screens, not preregistered inclusion criteria. The four pre-run p99 ratio failures already reject the candidate. These checks are not causal attribution or a substitute for researcher review. The raw candidate files were not modified by the re-audit.

## Next attempt

Wait for a host interval with stable free memory, no active swapping and negligible memory/I/O pressure. Run a fresh ID under the same committed source, retain the full two-order matrix, and inspect per-fork trajectories. A stronger primary-fork page-residency observation is still needed before accepting persisted warm-state claims. TailCache 10 remains **NO GO** until RQ1/RQ2 are implemented and persisted-warm primary evidence is sound.
