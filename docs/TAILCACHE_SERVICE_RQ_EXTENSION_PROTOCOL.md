# Prospective service RQ extension — 17 November 2026

Declared after the completed/audited initial screen, before collecting this extension. The user's overnight instruction authorizes the additional bounded work. This is a new cohort and does not amend or replace the first cohort's frozen decisions. The screen's 20 forks and all four controls remain retained; its raw audit passed. Source archives and all 72 compiled runtime files are copied/hash-bound. The measured Java runtime must match the screen exactly; only controller/analysis code changes.

## Why extend

The screen shows clear Chronicle service-p99.9 advantages at 256/512 B, a near-tied 1–2 KiB band, and a Caffeine advantage at 4 KiB. The initial rule required adjacent payloads to clear a 10% margin, so it did not select confirmation across the gradual transition band. Its pressure rule selected 4 KiB but stopped because that cell already exceeded the first 80% occupancy target. Those decisions are preserved, not retrospectively rewritten. Fresh repetition of the full transition region and a fixed higher-pressure grid address these specific gaps.

## Unchanged measurement contract

Same 1,000,003-operation trace, ordinary immutable 95/5 workload, resident count, 512 MiB G1 heap, application-object/churn settings, timing boundaries, 12/2/30 s phases, 100 s process timeout, controls, host readiness, counter conservation and raw evidence rules as the initial protocol. Combined saturated-service p99.9 remains primary, p99 secondary; operation-specific service and higher tails are diagnostics. Common ballast stays equal within each backend pair; occupancy is an outcome. No timing-floor subtraction or observer-neutrality claim. All near ties, contrary forks, warnings and failures remain visible.

## Fixed bounded matrix

| Part | Cells / repetitions | Maximum workload JVMs |
| --- | --- | --- |
| Higher-pressure discovery | Payloads 2 and 4 KiB × common ballast 240/272/304/336 MiB × one fresh pair | 16 |
| Payload/pressure replication | Payloads 512 B, 1/2/4 KiB × common ballast 0/208 MiB × three fresh paired forks, seed 24301 | 48 |
| Held-out trace check | Same eight replication cells × one pair, seed 24302, analysed separately | 16 |
| Conditional pressure confirmation | At most one discovered pressure bracket × two endpoints × three fresh primary pairs plus one held-out-seed pair per endpoint | 16 |

Ceiling: **96 new workload JVMs**, plus four declared matched controls. The 20 original screen forks are separate discovery data. No further sweep or retries is implied by this ceiling. The Java functional validation is reused only because the compiled runtime is identical; no additional functional JVM is silently counted as workload evidence.

Discovery cells are deterministically shuffled (seed 24317). Replication cell order is shuffled separately in each block (24310 + block); held-out order uses 24320 + block. Alternate backend order within these schedules. The schedules themselves are in protocol.json before launch. Completed slots remain checksum-verified on resume. Failed/incomplete runs count toward the ceiling and are not latency winners.

The high grid is fixed application demand, not a claim of calibrated heap occupancy. Its maximum 336 MiB is below the initial policy cap for both payloads. No process is allowed to escape the accounting scope, no forced collection is inserted into measured phases, and host safety/readiness conditions stop new launches while retaining completed evidence.

## Conditional pressure confirmation

Use **only** the initial screen and this extension's higher-pressure discovery to choose a candidate; replication/held-out observations cannot alter that selection. Within each fixed payload (2 or 4 KiB), an eligible lower-ballast pair has Chronicle/Caffeine combined-service p99.9 ratio >=1.10 and a higher-ballast pair <=0.90. Choose the narrowest such observed interval, then smaller payload, then smaller lower ballast. Select at most one. Declare both endpoints and discovery ratios before new confirmations. If none exists, skip these 16 JVMs and retain a negative/mixed result for the tested range.

Confirmation uses three new pairs per endpoint at seed 24301, shuffled with seed 24330, and one separate seed-24302 pair per endpoint. Discovery forks are never pooled into these confirmation summaries. No monotonicity assumption, fitted exact threshold, favourable-pair selection, repeated bisection, or post hoc change of primary percentile. Endpoint consistency requires all primary paired directions to agree and their median to meet the predeclared practical margin; it is descriptive replication, not a calibrated significance test. Show clean-pair coverage and every holdout result separately.

## Completion and interpretation

Independently decode available raw HDRs, reconcile all distributions/counts, GC/allocation/RSS and paired ratios, and verify archived source/runtime and original paper identities. Export every measured cell with per-pair conclusions, operation-specific tails and uncertainty/quality notes. Review whether a result concerns pressure, payload, API/recorder behavior or feasibility. A broad payload transition band can be reported even if intervening cells are near-tied; failed cells cannot be silently interpolated across. The first screen's stricter adjacent-payload decision remains historical and unchanged.

The extension can establish repeated winning regions and finite observed brackets. It cannot isolate heap placement from all library differences, produce a universal threshold or turn an OOM into a tail-latency benefit. Any later recorder/maintenance sensitivity requires its own prospective protocol and separate cohort.
