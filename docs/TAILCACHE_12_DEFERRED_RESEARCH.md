# Task 12: deferred research follow-up

> **Current update — 15 November:** the bounded follow-up and deep manuscript review are complete. The [current state](TAILCACHE_CURRENT_STATE.md) and [reviewed claim map](preprint/CLAIMS.md) supersede prospective wording below for present decisions. Recorder generalisation, other loads/machines and equal-total-memory interventions remain future research; none is a hidden prerequisite for writing the scoped findings. Original qualification failures stay explicit.

Recorded 9 November 2026, Asia/Kolkata. The user asked to note these items for later. **Deferred; no new collection is scheduled or launched by this note.**

> **Update 11 November:** the bounded 0/104/208 MiB follow-up described prospectively below has now completed, including two additional seeds: 30 workload JVMs and nine controls. The endpoint response direction change repeats; 104 MiB is mixed; the adaptive addition was skipped. See [the midpoint review](TAILCACHE_MIDPOINT_RESULTS.md) and [paper preparation package](preprint/README.md). The broader measurement/generalisation questions below remain deferred; no rerun is required before drafting the scoped paper. The original 9 November planning text is retained as dated history.

Subsequent planning: the user requested midpoint planning and a preprint before the 1 December application deadline. See [the bounded experiment and preprint plan](TAILCACHE_PREPRINT_PLAN.md); the 18-JVM batch is now proposed next work, still unlaunched. The broader follow-ups below remain available without requiring a full rerun.

## Completion and scope

The conditional Task 12 execution/analysis deliverable and the focused exploratory tail analysis are complete. The original unconditional joint-observer protocol remains unqualified. This distinction does not imply a formally approved replacement of the original scope, or that the original campaign was never collected.

The [final researcher review](TAILCACHE_12_FINAL_OUTCOME_REVIEW.md) records all 402 planned invocations attempted, including 192 campaign slots and 64 robustness slots on two additional seeds. One campaign fork was hard rejected and retained as excluded; the completion supplement changed the stopping policy after interruption. Source-matched qualification, known-pause controls, timer/supply floors, calibration and pilot were also collected. They must not be described as wholly missing work.

The [focused claims](TAILCACHE_FROZEN_CLAIMS.md) describe a separate exploratory follow-up, including post hoc p99.99/p99.999 and full-tail analysis. The current evidence establishes useful workload-specific effects; it does not establish a universal pressure threshold or a confirmatory causal explanation.

## Deferred items, in proposed order

| Item | Plain meaning and reason | Existing evidence to reuse | What would finish the follow-up |
| --- | --- | --- | --- |
| 1. Measurement interference and coherence | Check how much the act of timing changes the workload. Sparse timing and timing every operation can change throughput, allocation and GC exposure, and sometimes the backend ranking. | Both recorder datasets, fixed-sampling controls, pause checks and floors already exist. Known pauses were observable and source-matched qualification passed within its declared scope. | A small, separately declared study quantifies recorder effects and selects or limits the interpretation of the measurement method. Do not require identical numbers from different observers or subtract floors from tails. |
| 2. Source-matched qualification for the chosen follow-up | Verify that the exact code/runtime used for new evidence has settled after warmup, captures pauses and has sufficiently small timing/value-supply overhead. Qualification is specific to a source and protocol. | Existing source hashes, JIT diagnostics, pause controls and timer/supply floors. Some historical campaign cells still have JIT warnings despite passing low-pressure qualification. | Reuse matching controls where valid; repeat only the controls required by a changed source/protocol or an unresolved defect. Declare thresholds before collection and preserve warning-bearing cells. |
| 3. Reproducible pressure and a frozen confirmation plan | Choose comparable application memory pressure and write down the hypothesis, endpoints, run order, duration and failure rules before seeing new results. | Independent calibration and occupancy/GC records already exist. Equal application ballast is the fairness rule; equal total heap occupancy is not. | Document the pressure points and acceptance rules for a bounded new study. Keep service versus scheduled response, ordinary get versus buffer reuse, and runtime/build cohorts separate. Declare extreme percentiles prospectively if they become confirmation endpoints. |
| 4. Independent confirmation and extreme-tail support | Test whether the selected finding repeats, and whether rare-tail conclusions rest on enough independent stall episodes. Millions of operations delayed by a few pauses do not provide millions of independent pause observations. | The original 64 robustness invocations and the focused paired forks are available with their limitations. They do not repair rejected primary cells. | Collect only the additional forks/seeds or duration justified by the chosen claim; report fork variation, unresolved results and rare-event support. A larger machine or another host is an optional generalisation study, not a requirement for completing the offline analysis. |
| 5. Final acceptance and causal claim review | Reconcile the new evidence with its declared rules and state exactly what it establishes. A tail difference alone does not prove which GC pause, scheduler event or allocation caused it. | Existing raw archives, audits, exclusions, source identities, conditional acceptance and frozen exploratory claims. | Review accepted/rejected coverage and uncertainty under the new protocol. Keep historical conditional results and post-interruption amendments explicit. Any causal claim needs matching event-level evidence; otherwise retain a descriptive claim. |

These are stronger research follow-ups, not a commitment to rerun the entire matrix. A new protocol cannot retroactively make the original unconditional protocol pass.

## Separate optional small confirmation batch

**Completed 10 November:** 4 KiB ordinary scheduled response at **0, 104 and 208 MiB** application ballast, three primary paired forks per point: **18 JVMs**, plus 12 additional-seed JVMs. The following paragraphs preserve the original prospective purpose and controls.

Purpose: test whether the observed p99.9 direction change between 0 and 208 MiB repeats, and add the missing midpoint. At p99.99/p99.999 Chronicle already wins at baseline in the retained 30-second response data; those are baseline advantages, not newly observed forward crossovers.

Before launch, freeze one source/runtime and common workload settings, counterbalanced order, new evidence directory, warning/rejection rules and resumable slot handling. Preserve completed slots on interruption. Analyse this batch separately from the exploratory dataset; do not pool rejected forks or replace them silently.

This small batch would not by itself resolve recorder interference, establish a universal crossover, provide independent extreme-tail pause episodes, or satisfy the original unconditional protocol. Its value should be assessed after reviewing the completed full-tail explanation.

## Evidence and presentation already complete

- Focused percentile conclusions through p99.999, per-fork tail curves and exceedance probabilities at 100 microseconds, 1 millisecond and 10 milliseconds.
- Frozen exploratory claims, definitions, uncertainty and retained warning/exclusion information.
- Interactive results explorer deployed with authentication protection.
- No benchmark was started to create this deferred-work note. Existing completion flags and immutable evidence remain unchanged.
