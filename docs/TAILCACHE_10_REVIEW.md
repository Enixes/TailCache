# TailCache 10 — secondary-work decision and researcher review

## Decision on 2026-10-04

**NO GO for secondary experiments.** `scripts/tailcache10_gate.py` read the recorded quality and schedule evidence in `docs/TAILCACHE_10_EVIDENCE.json` and wrote a machine-readable decision. RQ1 and RQ2 have no heap/live-set crossover sweep, the TailCache 08 persisted-warm candidate is rejected, and remaining research hours have not been verified. The TickTick 10 due date is October 14 (10 calendar days from the decision date); the repository target is October 20 (16 calendar days). Calendar days are not interchangeable with available research hours. The current work should repair the primary protocol and repeat it on a quiet host, not launch a secondary experiment.

The later full-duration `08-candidate-20261004-a` also failed its variance and host-quality gates. The evidence input now points to that candidate's `quality.json`; its new result reinforces the same **NO GO** decision and supersedes the short validation as the latest attempted 08 run. See `docs/TAILCACHE_08_CANDIDATE_REVIEW.md` for the raw-data assessment.

If the gate later passes, the selected order is (1) persisted two-JVM sharing, (2) Chronicle `getUsing`/object reuse, (3) cold/open/page-fault behavior. Eviction-policy simulation is cut first. The current 07 reopen/first-touch diagnostic remains separate from warm operation measurements and is not promoted into the primary data.

## Audit of the gate

The script requires explicit `sound`, `invalid`, or `missing` states for RQ1, RQ2, and persisted-warm quality; it also checks task/project dates and a recorded remaining-hour reserve. Missing hours fail closed rather than assuming that a future calendar deadline implies spare time. Its present negative decision follows the 07 and 08 researcher reviews. A synthetic positive input with all three quality states `sound` and eight remaining hours selected the first priority, two-JVM sharing, verifying that the order is encoded rather than only described in prose.

The input evidence states are researcher judgments backed by the cited local reviews; the script does not independently inspect a JFR recording or infer heap-pressure crossover from JMH JSON. Before changing any state to `sound`, rerun the primary study and link its artifact-specific review, including the persisted page-state gate. The five-hour threshold is a conservative scheduling reserve drawn from the scope guard's secondary-work rule; it is a decision policy, not a measured effort estimate for two-JVM sharing.

## Claim limit

This is a scope decision, not a result about two-JVM sharing, `getUsing`, cold starts, or eviction. TailCache 09 capacity sensitivity can stand as its own diagnostic design, but its short timing data and the invalid 08 baseline cannot establish or explain the primary crossover.
