# Deep review and next experiments — 18 November 2026

This review follows the completed predictor study at `3b2f175`. It rechecks source, retained schedules, GC/stall evidence, model calibration, manuscript boundaries and follow-up value. It includes new **posthoc, development-only analysis of existing data**, with **zero new JVM executions**. It does not reopen completed cohorts, change frozen models, remove warnings, reactivate recovery or establish a newly validated predictor. This is agent-assisted review, not independent human peer review.

## Assessment

The evidence supports a bounded empirical paper about workload-dependent response reversals and measurement/model limitations. It does not yet support a portable write-rate threshold, a precise before-run selector, an isolated object-survival explanation, or the original general ordinary-service p99/p99.9 crossing. More points alone would not fix those gaps.

The strongest current findings remain: response p99.9 endpoint directions at 0% and 5% writes agree in the primary and fresh cohorts; 0.5% is mixed in the fresh cohort; conditional M1/M2 winner accuracy ties total GC pause time; queue modeling improves aggregate numerical error but the original constant baseline is better for Chronicle alone. Source/value/count/HDR audits and reproducible exports are strengths. The original unconditional NO_GO and new finite-window qualification remain unchanged.

The earlier review missed a schedule imbalance and did not give sufficient prominence to collector failures or the limitations of the occupancy diagnostic. Those omissions need disclosure before author release.

## 1. Execution order was not adequately counterbalanced

The frozen prose described alternating/counterbalanced backend order. The retained schedules show:

| Write rate | Primary: Caffeine first / Chronicle first | Fresh: Caffeine first / Chronicle first |
| --- | --- | --- |
| 0% | 1 / 2 | 2 / 0 |
| 0.5% | 3 / 0 | 0 / 2 |
| 1% | 1 / 2 | Not tested |
| 2% | 2 / 1 | Not tested |
| 5% | 1 / 2 | 2 / 0 |

In particular, every primary 0.5% pair ran Caffeine first, and every fresh 0.5% pair ran Chronicle first. The fresh schedule also clustered write rates as 5%, then 0%, then 0.5%. A shuffled list need not be balanced, and the `(cellIndex + block) % 2` reversal rule does not enforce the claimed constraint. The existing schedule test checks pairing, labels and seeds, but not first-backend balance.

This is a protocol-description/execution discrepancy and a potential order/time confound, not proof that the rankings are artifacts. Each primary endpoint (0% and 5%) includes both backend orders, and its ranking is consistent across those orders. Both fresh 0.5% pairs have the same order yet disagree, so order alone cannot deterministically explain that mixed result. Nevertheless, the fresh point-specific design cannot estimate order effects separately. Do not delete results or rewrite the frozen protocol to make it match. Disclose actual order and add a dated correction to current methods before release.

For a new two-repetition-per-seed design, explicitly require one Caffeine-first and one Chronicle-first pair within every treatment/seed, then shuffle those constrained pairs. Test the constraint before launch and retain actual timestamps. With three repetitions, declare the unavoidable 2/1 imbalance and counterbalance the excess direction across cells. Randomize temporal blocks as well as backend order.

## 2. Seed variation and run variation are confounded

Each primary seed has one pair per write point; each fresh seed also has one pair per point. The ranges therefore combine seed effects, GC-cycle phase, JVM stochastic variation and temporal host effects. They are not estimates of within-seed repeatability. The two cohorts remain separate; a pooled five-pair percentile or confidence claim would be inappropriate.

If a tighter 0.5% statement is needed, two seeds × two repeats × two backends = **eight JVMs** is more informative than more one-pair midpoints. Balance backend order within each seed. Predeclare that a contrary/mixed result remains informative; do not bisect until Chronicle wins.

## 3. Evacuation failures are intrinsic outcomes, not external noise

Measured G1 evacuation failures occur in **five primary Caffeine forks** and **two fresh Caffeine forks**, with none in Chronicle. All five 0.5% Caffeine holdout forks have at least one; two of the three primary 1% forks also do. No measured full GC is recorded in these holdouts. These events are present in the portable/raw evidence but underemphasized in the manuscript.

Both fresh 0.5% Caffeine forks have an evacuation failure, including the contrary Caffeine-lower fork. Failure presence therefore does not by itself explain their different ranking. Conversely, every 5% holdout endpoint lacks measured evacuation failure, so the repeated 5% Chronicle advantage cannot simply be dismissed as an evacuation-failure-only result.

Zero additional ballast is not absence of heap pressure: Caffeine still retains approximately 128 MiB of payload plus other structures, writes create retained/floating versions, common churn continues, and G1 adapts young/old collection behavior. These observations motivate a heap-headroom or collector intervention, without discarding failures from the main pressure outcome. Oracle's [G1 tuning guide](https://docs.oracle.com/en/java/javase/21/gctuning/garbage-first-garbage-collector-tuning.html) describes evacuation-failure diagnostics and relevant capacity/marking considerations; it does not identify the unique cause in our forks.

## 4. The occupancy criterion is not a reliable proof of nonstationarity

The selected 120-second 0.5% Caffeine qualification fork compares:

| Measurement half | Observations | Collection kinds | Post-collection used heap |
| --- | ---: | --- | --- |
| First | 4 | Concurrent-start young, remark, cleanup, prepare-mixed | 269, 269, 270, 274 MiB |
| Second | 2 | Mixed, mixed | 229, 194 MiB |

The medians are 52.64% and 41.31% of heap, so the declared rule genuinely failed. However, these are small samples of different phases of a G1 cycle. This can happen in a cyclic steady regime as well as during warmup. The test neither establishes steady state nor proves every subsequent fork is physically nonstationary. `transient=true` remains a conservative qualification label, not a demonstrated time trend in every fork.

Current prose should say **failed occupancy-based qualification**, rather than asserting that longer warmup conclusively failed to reach steady state. A future qualification should compare like collection phases and cover multiple complete cycles, while keeping finite-window response outcomes valid in their own scope. Do not spend days extending a single warmup call solely to force two medians to match.

The separate compiler probe still supports a possible phase-exit profiling problem. Repeated short complete invocations before the long phase are a testable intervention; they are not already proven to fix the nine primary compiler warnings.

## 5. The model's pause boundary matters

New analysis unions raw GC intervals with logged safepoint envelopes and replays the **unchanged M2 costs/algorithm**. It verifies raw-log/stall hashes, reconciles safepoint totals with retained summaries, and checks interval-superset prediction monotonicity. No target is trimmed or fitted.

| Input intervals | Primary median absolute response-p99.9 error | Fresh median absolute error |
| --- | ---: | ---: |
| Frozen GC-only M2 | 139.19 µs | 137.48 µs |
| GC plus safepoint core proxy, excluding reported reach time | 104.40 µs | 105.50 µs |
| GC plus full reported safepoint envelope | 97.25 µs | 96.99 µs |

For Chronicle alone, median relative error changes from 65.1% to 42.6% primary and 56.9% to 38.1% fresh with the full-envelope proxy. The constant pilot baseline is 28.1% and 40.6%, respectively. Thus the simple baseline is still better in the primary Chronicle comparison; the fresh proxy improvement over it is small and posthoc.

These are **not fresh validation results for a new model**: both datasets were already seen before proposing this sensitivity. Safepoint reach time is not necessarily time during which this particular worker was stopped. Excluding it still leaves approximate log-derived boundaries. The full envelope can compensate for other missing costs; a lower error does not prove it is the correct worker-unavailability interval. GC and safepoint totals overlap and must never be added without interval union. OpenJDK's [safepoint implementation](https://github.com/openjdk/jdk21u/blob/master/src/hotspot/share/runtime/safepoint.cpp) distinguishes thread synchronization from the operation itself; this source is context, not a claim of byte-for-byte correspondence with the host build.

The unresolved fresh Caffeine 0.5%/seed44812 fork is a useful counterexample: observed p99.9 is **152.191 µs**, while frozen M2 and both safepoint variants predict **16.043 µs**. Better pause boundaries alone do not solve the near-budget regime.

Across all 42 holdout forks, every retained gap episode of at least 1 ms overlaps a GC interval. GC-associated gaps have median per-fork envelope time beyond GC of about 136 µs primary /147 µs fresh for Chronicle, and 162/156 µs for Caffeine. These envelopes include legitimate service, pacing and runtime work. They are not pure overhead, and their use as future prediction inputs would leak worker-timing information. Sparse recording says nothing definitive about shorter non-GC stalls.

See [analysis artifact](deep-review-analysis-20261118.json) and `scripts/tailcache12_predictor_review_analysis.py`. Reproduce to a new output path; the script refuses an existing file. Frozen M0/M1/M2 and published data are unchanged.

## 6. A small logging sensitivity is worth more than immediate additional midpoints

The measurement records `gc*`, safepoints and age-trace output. Java logging is synchronous by default. The [Java 21 command documentation](https://docs.oracle.com/en/java/javase/21/docs/specs/man/java.html#xlog-output-mode) documents `-Xlog:async` and its bounded-buffer/drop behavior. Oracle also notes that [GC-log I/O can stall](https://docs.oracle.com/en/java/javase/21/gctuning/garbage-first-garbage-collector-tuning.html#unusual-system-or-real-time-usage).

This is a plausible observer effect, **not an established explanation**. Same flags in both backends do not cancel costs when Chronicle performs many short collections and Caffeine fewer long ones. Proposed screen: same measured Java/runtime, 0.5% writes, both backends, synchronous versus asynchronous logging, one paired seed = **four JVMs, roughly 10–15 minutes** plus checks. For the four-fork screen keep the same first backend in both modes; it cannot estimate order effects. If expanded to a second seed, use the opposite first backend for both modes of that seed. This holds order constant within each seed’s mode comparison and balances order across seeds within each mode. Treat four as a worth screen and eight as a separate confirmation.

Primary diagnostics: GC-linked gap excess and response exceedance at 100 µs, plus GC/safepoint interval accounting. Response p99.9, per-backend service and GC behavior remain secondary comparisons. Reject incomplete/dropped logs for model reconstruction, retain the latency outcome and diagnostic reason; never replace a failed slot silently. Keep buffer/native-memory settings logged. If raw completeness or timing consistency cannot be established, stop this arm. A null effect is useful and ends observer expansion. Do not tune a correction constant to the 42 already-seen targets.

## 7. Highest-value next research test: control the update hot set

The leading trace mechanism is not isolated. A more focused intervention than a general Zipf sweep is:

- 4 KiB values, 32,768 residents, 5% writes, 50k arrivals/s, zero ballast and the same churn/heap/collector.
- Keep read keys, operation flags, arrival schedule, fresh-write allocation demand and continuous indexing fixed within each seed.
- Change only the eligible update-key set: **2,048 versus 32,768 keys**. Generate on the fly in both arms; do not add a trace array.
- Hold first-backend order constant across update sets within a seed, use the opposite order for the second seed, and shuffle constrained temporal blocks.
- Two backends × two update sets × two paired seeds = **eight JVMs**, roughly **20–25 minutes**, after functional checks. A four-JVM single-seed worth screen can precede the second seed; freeze the rule and keep both stages distinct.
- Predeclare the hypothesis: concentrated updates shorten overwrite intervals and reduce Caffeine survival/GC exposure enough to narrow or reverse its response disadvantage; Chronicle may change less because read materialization demand remains fixed. At 2,500 updates/s, nominal per-key intervals are 0.8192 versus 13.1072 seconds. This is a prediction to test, not a required outcome.
- Record actual updated-key coverage/overwrite history, G1 phases/age evidence, allocation, full tails and Caffeine policy activity. The intervention still changes write locality and policy traffic with lifetime; do not claim isolated object survival without stronger tracking.

This directly tests why the old short-pattern and long-pattern rankings differ, with substantially fewer bundled changes. If concentrating updates does not give the predicted GC/response direction, retain the failed mechanism prediction and stop. Do not search more hot-set sizes until one wins.

## 8. Other options, ranked by purpose

| Follow-up | What it can establish | Initial budget | Priority |
| --- | --- | ---: | --- |
| Explicit schedule validation + fixed-seed repeats at 0.5% | Separates repeatability/order from seed variation | 8 JVMs; about20–25 min | High if tighter boundary language is needed |
| Phase-priming diagnostic | Tests the phase-exit/JIT hypothesis with identical total warmup work | 4 JVMs; about10–15 min | High as bounded qualification, not endless gate repair |
| Controlled update hot set | Tests update-locality/lifetime explanation of trace sensitivity | 4-fork screen, ceiling8 | Highest new workload-mechanism value |
| 512 MiB versus larger-heap G1 | Tests headroom/evacuation sensitivity under matched library contracts | 8-fork screen | Good alternative after GC diagnosis |
| G1 versus Generational ZGC | Tests whether the response gap contracts with a different pause regime | 8-fork screen, ceiling16 | Good collector sensitivity; not a single-variable proof |
| Matched Caffeine/get/getUsing | Tests materialization versus caller ownership contract | 6-fork screen, ceiling12 | Useful practical API question; keep semantics explicit |
| One independent host | Tests whether selected endpoint/transition conclusions transport | 12 JVMs | High value for paper credibility after protocol repair |
| More payloads, write midpoints, skew or rare percentiles | Adds coverage | Potentially large | Defer unless a specific prediction justifies them |

For collector work, Java 21 documents [Generational ZGC](https://docs.oracle.com/en/java/javase/21/gctuning/available-collectors.html). Do not predict that a smaller GC pause must remove the crossover: concurrent CPU, allocation stalls, barriers and capacity behavior also change. Similarly, a bigger machine can improve readiness/throughput without correcting methodological flaws.

Existing conditional read/update histograms also deserve an offline application-SLO discussion. In the 17 November saturated 4 KiB cohort, update-only p99.99 already favors Chronicle at baseline and the advantage grows at208 MiB, but all three high-pressure pairs carry warnings. This is not a newly pressure-emergent combined-service p99/p99.9 crossing and not new confirmation. It illustrates why updates and reads should remain separate diagnostics rather than being promoted opportunistically to a new headline.

## Proposed sequence and stopping boundary

1. Disclose actual order, evacuation failures and the limited occupancy inference before author release. Add explicit schedule-balance tests to the **next** driver, retaining historical schedules intact.
2. Secure disk space and a quiet, source-frozen runtime. At review, root free space was about126 MiB, below the existing512 MiB launch minimum. Aim for a practical reserve of at least2 GiB before collection. Preserve all raw evidence; no benchmark is launched in this review.
3. Timebox observer/JIT qualification: choose a small logging screen first, or a phase-priming screen if late compilation is the immediate blocker. Change one factor at a time; no declaration of steady state from a single clean fork.
4. Run the controlled update-hot-set screen, expanding only once under a written worth rule. Keep a failed prediction as an outcome. All new studies use separate source/runtime identities and immutable output directories.
5. Choose **one** headroom/collector/API/independent-host extension if it materially strengthens the contribution. Do not run all combinations. An independent host and an external arrival observer are stronger generalization work than another fine-grained threshold search.

The completed scope remains complete with limits. These are proposals for a new bounded scope, not queued jobs or renewed automatic recovery. The paper remains an author-unapproved working draft; no publication acceptance probability or guaranteed venue follows from these findings.
