# Midpoint implementation review — before collection

10 November 2026. This is an implementation/research-method self-review, not independent human peer review.

## Reviewed changes

- Python now passes an explicit seed to the Java runner's preexisting option, records it in every slot/protocol and checks the actual worker configuration. The compiled Java workload was not changed. All **68 runtime files** match the retained later-runtime 8 November response-bracket protocol byte for byte; classpath matches too.
- Different seeds cannot be aggregated by the focused summary helper. The new controller uses separate primary, seed24302, seed24303 and optional adaptive cohorts with frozen settings and a 36-workload-fork cap.
- Once-per-second status-file reads record JVM RSS/high-water/anonymous/file residency with monotonic sample bounds. Only samples wholly within actual measurement clocks enter the measured RSS maximum. This is coarse resident memory, not PSS, exact native allocation, process-wide profiling or fixed-total-memory validation. Observer effects remain possible and are declared.
- Actual child PID/cgroup identity is retained and checked against native accounting. Spawned workers are killed/reaped after timeout or exceptional cleanup. Host-monitor errors remain visible. Unreconciled CPU intervals become warnings rather than erasing a completed batch.
- Controls and workload slots both recheck retained raw hashes on resume. Existing slots are not relaunched. Failed/incomplete stages stop dependent stages and preserve receipts. Source/runtime changes block continuation. The existing native flock prevents competing controllers.
- Mount, filesystem/storage, CPU, JVM and Git metadata are collected outside worker measurement. No environment secrets or page-table walks are added. No analytics, tiering, heap, collector, workload values or measured Java instructions were changed.
- Adaptive search requires all three pairs at every primary point to be usable and warning-free, plus the predeclared consistent endpoint directions. Mixed, warned, incomplete or contrary results cannot trigger bisection. Optional seed cohorts are still reported if the primary result is mixed.
- Between slots, collection pauses below 512 MiB free disk or 1 GiB available memory, on disconnected external power or growth in swap-in/out counters. Historical host/JIT warnings are not retroactively reclassified; measured GC/churn/queue outcomes remain visible.

## Verification before freeze

Ten focused-runner unit tests and two adaptive-rule tests passed, including explicit launch-argument propagation, seed isolation, missing-process memory reads, resumed-control tamper detection and no adaptive search from incomplete/noisy pairs. Twenty-three existing native-launch/accounting/retry tests also passed. No Java rebuild is needed because measured runtime and Java source are unchanged. Existing native controls and the injected-stall/request-conservation check will run in every new batch. Final hashes, runtime identity and this review are retained with each batch before its workload starts.

## Interpretation limits

The planned 18-slot primary cohort describes a fresh replication of the instrumented scheduled-response p99.9 result, not a new unconditional qualification of the historical joint-observer protocol. The two additional seeds have one pair per pressure point; do not invent seed-level confidence intervals. All percentiles, warnings, raw counts and strict exceedance bounds must be reported. The adaptive point is exploratory, not a preregistered independent threshold confirmation. No exact monotonic or universal pressure threshold, production-network response, event-by-event GC causality or journal acceptance is established by this unit.
