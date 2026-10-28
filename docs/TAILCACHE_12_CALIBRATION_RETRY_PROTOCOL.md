# Prospective calibration host-CPU retry protocol

Version: `tailcache12-calibration-hostcpu-retry-v1`, declared 28 October 2026 before any use on newly collected calibration data. This implements the bounded, gate-based retry requirement in Task 12's research plan, line 132. It applies only to exploratory pressure calibration. It does not change the primary campaign's rejection/retry protocol, which remains to be frozen after the pilot.

## Scope and prerequisite

Earlier calibration attempts 001–004 retain their original interpretation and remain rejected/incomplete. No passing fork is imported from those attempts. A new attempt must follow fresh source-matched functional validation, both complete compiler qualifications, and a fresh quiet-host preflight. Observer v5 must be healthy; its snapshot-sharing repair does not explain the earlier calibration CPU spike.

The planned calibration retains 64 logical slots: two counterbalanced passes of both backends, both payloads, four common ballast inputs and both recorders. Each candidate is a fresh JVM with the unchanged workload, heap, seed, warmup, measurement and numerical quality controls. The protocol adds no ballast adjustment or endpoint-based selection.

## Fixed retry rule

The next candidate calibration, conditional on passing prerequisites, uses `--host-cpu-retries 2 --host-cpu-retry-budget 8`:

- A slot gets its first candidate and at most two extra JVMs. The entire attempt permits at most eight extra JVMs, so the upper bound is 72 JVM attempts for 64 slots.
- Retry only when the sole rejection is Windows root CPU above 10% in the declared settling/measurement interval, with all workload, runtime, source/artifact, histogram, GC/churn, compiler and other host checks passing.
- Compiler, memory/paging, observer freshness/version, source/integrity and other failures stop collection. A failed aggregate occupancy/replica band is not a reason to search for another sample.
- The first fully quality-passing candidate fills its slot regardless of its latency or occupancy value. A valid candidate cannot be replaced. No candidate is chosen by comparing endpoint values; noisy valid results remain included.
- Exhausting either budget stops collection with incomplete coverage. Missing slots cannot support a complete calibration or a no-crossover claim.

Retries stay at the same logical slot before advancing through the originally counterbalanced order. Record actual timestamps and gaps. This can delay the next backend; calibration supplies occupancy bands and descriptive diagnostics, not paired primary latency inference. The primary campaign needs its own reviewed pairing and retry rules.

## Quiet interval and temporal checks

Before each extra JVM, permit one bounded preflight: 60 consecutive quiet seconds, with a 300-second timeout. Retain its complete `host.csv` and `quiet.json` inside the attempt under `retry-preflights/`. A failure stops the grid; resumption cannot silently launch another preflight to chase a pass.

Replay the host samples to reconstruct the quiet decision. Gaps over five seconds reset the quiet window. Require the same full source hash, native observer v5, power scheme and CPU counter as the declaration. The quiet interval must follow the preceding JVM's host interval and finish before the replacement JVM starts. At most 360 seconds may elapse between its last sample and the next block's first host sample, allowing the declared controller guard while preventing stale prerequisite reuse. Every replacement still receives its own unchanged per-block host/compiler and other quality screens.

## Immutable declaration and audit

Opt-in attempts use schema `tailcache12-calibration-v2-hostcpu-retry`. Before the first candidate, retain a hashed `retry-policy.json` containing the policy, all logical slots and exact properties, full source identity, measurement-source identity and native observer declaration. Candidate labels end in `-q1`, `-q2` or `-q3`. Default CLI behavior remains the original stop-at-failure policy.

Audit reconstructs the canonical slot order, validates declaration/source/artifact/preflight hashes and identities, and rejects altered controls, out-of-order candidates, retries after a valid result, missing prerequisites and exceeded budgets. It retains every candidate in `observations` and CSV. `recordedJvmAttempts` counts all candidates; `completedBlocks` counts quality-passing logical slots. Rejected candidates remain explicitly listed and do not become valid when a later candidate fills the slot. Occupancy bands use exactly the required independent selected slots, with the existing ±5-point replica, level separation and anchor screens.

Report invalid-attempt counts and timing by condition, and review any concentration at a backend/pressure level. An accepted calibration is conditional on the declared host screen. It does not establish why Windows became busy, prove that exclusions are treatment-independent, or supply primary crossover evidence. Do not transfer this policy automatically to the pilot or campaign.

## Verification and collection state

Forty Python tests pass, including a complete synthetic audit of 64 logical slots and 65 candidate records with one rejected CPU-only candidate retained; this is software verification, not measured calibration evidence. Tests also reject endpoint-based replacement, changed controls/order/policy, exhausted budgets, other quality failures, missing/changed quiet evidence and invalid timing. Real replay of calibration 004 remains rejected at 14/64. Existing Java verification remains 34 tests; Java measurement sources are unchanged.

Observer v5 still requires fresh matching qualification. No real calibration has used this protocol yet. Freeze all documentation/coordination before a fresh preflight and leave timed collection alone.
