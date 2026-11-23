# Prospective pause-model validation — 18 November 2026

User authorization: autonomous experiment/review cycles for eight hours, ordinary-usage recovery after interruptions. Preserve all earlier evidence and original NO_GO. This is a new exploratory predictor-validation unit; it does not reopen or relabel completed service cohorts. One current status, one plan, one portable dataset/report; keep raw audit receipts behind these entry points.

## Questions and frozen distinctions

1. **Before-run forecast:** at 4 KiB/zero application ballast/50,000 intended arrivals per second, ordinary Caffeine response p99.9 is lower at 0% writes; a ranking reversal toward Chronicle is predicted between 0.5% and 2% writes. Operational endpoints: Caffeine lower at 0 and 0.5%, Chronicle lower at 2 and 5%; 1% is not assigned a winner. A contrary/mixed result falsifies or limits this forecast; do not hunt until it succeeds.
2. **Conditional out-of-sample explanation:** given a new fork's GC intervals and phase schedule, can the *already frozen* model predict its response quantiles? These GC inputs become known during/after execution. This is not a before-run predictor of GC or a universally known write-ratio threshold.
3. Baseline operation/service, scheduled response and p99.99/p99.999 remain separate endpoints. Primary: response p99.9. Response p99.99 is secondary; p99, p99.999, service/gap/read/update, throughput, heap/RSS, G1 survival and demand losses are diagnostics. Capture full distributions/exceedance rates for every completed fork, without pooled percentiles or trimming.

## Offline model freeze (zero performance JVMs)

Archive Argon's posthoc review/model/CSV as development inputs with hashes. Reproduce all paired scores and compare with constant-Chronicle, constant-Caffeine and lower-total-GC-time rules; disclose nine abstentions and the single-class p99.99 subset. Preserve the original residual equation as model M0. Freeze M1, a finite-window residual-pause version plus an explicit fixed calibration baseline, before qualification. Parameters and scoring must not read future response histograms.

For window [a,b), T=b-a, a pause [s,e) contributes `max(0,min(b,e-x)-max(a,s))` to residual delay exceeding x. Merge overlapping pauses; preserve actual pause end if it extends past b. Solve the continuous residual budget `(1-q/100)T`; below budget, residual prediction is zero. This omits serial queue drain and non-GC stalls and is an approximation. M1 adds a fixed q-specific scheduler baseline (median of three retained timer-only arrival controls) and backend service offset (median historical baseline paced service p50). This additive baseline is a declared heuristic, not a convolution theorem or subtractable overhead. Record zero-budget cases and score **all** numerical outcomes, including below-budget/near-threshold cases. Report absolute/log-ratio/relative errors, each fork and cohort; do not select only >=0.5 ms errors.

Use only pre-existing 17 November paced/trace/geometry controls and paced 4 KiB baseline for calibration. No tuning to make a crossover. Conditional prediction files bind only frozen model, GC intervals, phase schedule and backend; immutable predictions precede the scoring stage. Compare M0/M1 with both constant-winner baselines and the total-pause rule; print coverage/abstentions and missing endpoints. No significance or precision claim from three pairs.

## Workload and source contract

New, separately compiled workload/runner preserve old classes. An operation-index deterministic hash stream produces uniform keys and independently selected writes at 0/50/100/200/500 basis points. Positions increase across warmup, conditioning and measurement; **no reset and no wrap**. Repeated keys are legitimate; no finite operation-sequence replay. Identical seed and phases yield identical paired keys, flags and fresh immutable write contents. Actual write counts are retained; Bernoulli selection is not falsely labelled an exact per-window percentage.

No retained trace/payload arrays: a large prerecorded trace would itself add heap pressure. Both backends pay identical generation/consumption work; fresh-supply floors quantify this new caller's demand without subtraction. Keep 32,768 residents, ordinary get, 4 KiB values, bounded-default Caffeine and original Chronicle capacity/tiering policy, 512 MiB G1 heap, one worker, common offered 32 MiB/s churn, analytics disabled and full final value/count checks. The stream adds CPU work relative to earlier traces: do not pool them or attribute changes solely to value survival.

## Qualification, worth and validation budget

Before any performance collection: JAR-only isolated compile; deterministic stream/pair/mix/phase-continuity, backend values, allocation and per-bin union checks; timer/injected-20-ms/fresh-supply controls. Retain all control warnings.

Qualification: one pair at each of **0%, 0.5%, 5% writes** with **12/4/30 s** phases (six JVMs), then a separately labelled pair at each with **60/4/30 s** (six). Choose 60-second warmup for validation only after checking late-window GC/occupancy/compiler stability; fixed warmup alone does not prove steady state. If late post-GC used-heap median shifts by >5 percentage points between measurement halves, or compilation exceeds80ms, permit the same six 120/4/30-second checks, then choose120. Warnings remain outcomes. If still evolving, label the experiment transient or stop/revise prospectively; do not silently claim steady state. Expected 131-second per-key overwrite time at0.5% is not a universal warmup requirement.

Worth: proceed when controls/accounting/source checks pass, paired logical streams match and the response/GC quantities can test the frozen predictions. A missing/contrary crossover does not make a valid negative result worthless. Stop on corrupted evidence, OOM/censoring or a reproducible unusable caller; no replacement forks. Qualification data do not count as validation. Additional JVMs: maximum18 qualification, four controls, separately counted functional checks.

Freeze the final model/protocol/source/runtime/schedule **after qualification and before validation**, recording any development changes and preserving earlier versions. Validation: **five write ratios × two backends × three paired repetitions =30 fresh JVMs**, 4-second conditioning/30-second offered measurement, chosen common warmup, 50k arrivals/s; 1.5 million responses per fork. Fixed shuffled cell order and alternating backend order, pair-specific predeclared seeds, all30 slots retained, no successful-only selection. No extra midpoint until this dataset is scored/reviewed.

## Quality, resilience and stop

Exclusive native lock/cgroup; inspect actual host processes first; require AC, >=1GiB available RAM, >=512MiB free disk and unchanged runtime/source, no new paging since readiness. Record CPU/thermal/power/storage/mount/boot/JDK metadata, all GC/safepoints, compilation, actual churn, RSS and sparse stalls. External/JIT warnings remain visible; corrupted counts/source identities are hard failures. Freeze source during each cohort. Checksum-verify retained completed slots on resume, never overwrite an unresolved slot or launch a duplicate.

After collection, independently decode every HDR, conserve all phases/channels, reconcile GC/RSS and stream metadata, score frozen model and forecast, and review as a systems researcher. Any subsequent mechanism experiment needs a new bounded prospective declaration and worth pilot within the remaining eight-hour budget; no obligation to obtain a Chronicle win. Preserve old paper-data.json and delivery history. Update manuscript/claims/explorer only after numerical review; no author-approved submission/deposit.

Recovery uses a dedicated predictor status, requires an actual usage-limit interruption and explicit ordinary-usage permission, suppresses active threads/drivers, makes no polling model calls, and stops on taskComplete=true. A launched job is not completion.
