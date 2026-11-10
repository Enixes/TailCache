# Bounded midpoint follow-up — implementation and execution declaration

Declared before collection. Planning date: 10 November 2026 (Asia/Kolkata). This implements the [preprint plan](TAILCACHE_PREPRINT_PLAN.md); it is a fresh cohort, separate from all historical evidence.

## Implementation unit

Keep the existing compiled Java workload and its measured code unchanged. Its existing `--seed` option is not currently exposed by the Python controller. Add explicit seed propagation and retained seed identity, reject mixed-seed aggregation, and add cheap once-per-second `/proc/PID/status` resident-memory observations with phase and monotonic clocks. Do not walk page tables or use a profiler during timing. Capture filesystem/mount/block-device and hardware/JVM metadata outside timing. Record actual JVM cgroup membership. Fix/verify resume integrity for controls and preserve all preexisting source/evidence.

Tests must exercise seed delivery to actual launch arguments, workload-seed isolation, resident-memory parsing and process-disappearance handling, and resumed-control hash verification. Run existing focused-runner tests and the matching Java correctness tests if the runtime must be rebuilt. Review these changes before freezing and launching. Record the exact source and runtime hashes and retained implementation review in every new cohort.

## Collection and stopping rules

- Primary batch: 4 KiB, ordinary get, 0/104/208 MiB common retained ballast; three independent pairs per point, **18 workload JVMs**. Same fixed 512 MiB G1 heap, 32,768 entries, uniform approximately 95/5, seed 24301, 32 MiB/s offered churn, 50,000 scheduled requests/s. Phases: 12 s warmup, 2 s conditioning, 30 s offered measurement; retain drain.
- Seed robustness: same three points, one pair each on seeds **24302 and 24303**, **12 workload JVMs** in two independent batches. Same exact compiled Java runtime. No seed-level confidence intervals from one pair.
- At most one adaptive midpoint: **6 workload JVMs**, seed 24301, three pairs. Choose 52 MiB only when all three valid primary pairs favour Caffeine at 0 and Chronicle at 104/208; choose 156 MiB only when all three favour Caffeine at 0/104 and Chronicle at 208. Otherwise collect no adaptive point. Mark it adaptive exploration; no exact interpolation or monotonicity claim.
- Maximum **36 workload JVMs**, plus three small controls per batch. No extra collector, concurrency, reuse or payload matrix in this unit. Total offered measurement time at the cap is 18 minutes; setup/warmup/verification add time. Per-batch budgets allow completion but do not require extending scope.
- Source/runtime/manifest mismatch or failed functional/control integrity blocks dependent collection. Acquire the existing exclusive native benchmark lock and retain native host accounting. No duplicate controller, replacement fork, erased evidence or pooling with historical cohorts.
- Preserve every completed slot; recover interrupted slots as explicit outcomes. External noise is a retained warning, not a whole-study restart trigger. Stop between slots on unsafe resource conditions (low disk/available memory, active paging or disconnected AC); resume remaining slots under the frozen settings after recovery. Do not alter workload acceptance to obtain a favourable result. GC stalls, churn drops and censored queues remain outcomes with explicit limitations.

## Analysis and deliverable

Primary endpoint: scheduled response p99.9. Secondary: p99/p99.99/p99.999, all full-tail thresholds (>100 microseconds, >1 ms, >10 ms), service and gap channels, allocation, GC, occupancy, churn and sampled process RSS. Include per-fork counts, finite tail support and warning-inclusive/clean-pair views. Three valid matching pairs are needed to call the primary direction consistent; missing/mixed pairs are unresolved. RSS samples are coarse resident-memory observations, not total committed/native allocation or a fixed-total-memory experiment.

Export a separate accepted/rejected/inconclusive follow-up dataset, machine-readable per-point conclusions, static graphs and researcher review. Independently verify raw HDR distributions and strict threshold bounds. Integrate the cohort into the local explorer only with separate source/seed identities; preserve old evidence and frozen historical claims. No deployment/publication or submission is implied by this declaration.
