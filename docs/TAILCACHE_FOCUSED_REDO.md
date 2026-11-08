# Focused crossover follow-up — plan before implementation, 8 November 2026

The user wants bounded batches that answer RQ1/RQ2 quickly, building on AGY's exploratory evidence rather than repeating a broad qualification campaign. Historical Task12 acceptance, source, raw evidence and AGY's uncommitted work remain unchanged. Disk cleanup reclaimed3.44GiB from npm/pip/Firefox caches; no research evidence or offline Java dependency was removed.

## Notes reviewed and methodological decisions

Latest AGY session: `813eaaaa-7714-484f-8709-5826310287c3`, “Codex Session Review and Documentation”, updated8 November2026. Read its `tailcache12_review.md`, repository `TAILCACHE_12_CLIFF_DIAGNOSTIC_AND_SYNTHESIS.md`, probe/runner, and retained30-JVM evidence. Treat the existing cliff runs as discovery evidence selecting a region of interest, not as a confirmatory research campaign.

| AGY point | Action in this follow-up |
| --- | --- |
| Earlier pressure missed the cliff, especially256B | Start near the observed4KiB transition,328/352MiB common application ballast; refine only if it changes the answer. Later calibrate256B on the SAME512MiB heap, so payload and heap size are not confounded. |
| Closed-loop service percentiles underrepresent rare stalls | Preserve service latency as the original RQ1 endpoint; add a genuinely scheduled-arrival channel measuring completion minus intended arrival, with a fixed request count and no skipped overdue arrivals. Keep the two estimands separate. |
| Existing “open-loop” proof used `recordValueWithExpectedInterval` | Label its numbers as synthetic coordinated-omission correction. The variable `nextIntendedStartNs` was unused: there was no paced arrival schedule. New response observations come from actual timestamps, without synthetic histogram expansion. |
| Ordinary get materialises values | Keep ordinary Chronicle get as the primary comparison. `getUsing` is a separately labelled explanatory sensitivity after the primary bracket, not a replacement for the original research question. |
| GC summary included setup/warmup | Log explicit phase start/end on the same monotonic clock as unified GC logs. Reconcile pause/full-GC/occupancy only against the measurement envelope and separately report scheduled-arrival drain time. |
| Frequent thread starts perturb measurement | Run the application-churn thread continuously through warmup/conditioning/measurement; snapshot cumulative counters at phase boundaries. Endogenous lost allocation demand under GC is an outcome, not automatic rejection. |
| Caffeine executor may explain256B baseline | Treat this as an untested hypothesis. Run a small direct-executor/unbounded sensitivity only if needed for the256B answer. Do not assert a cause in advance. |
| Whole-study aborts wasted time | Record fork outcomes and continue the finite schedule. Full GC/evacuation failure/OOM are pressure phenomena. No endpoint-based rerun or outlier trimming. |
| Single runs/weak replication | First batch uses3 counterbalanced independent pairs per point/channel. Report all paired values/ranges and consistency, without pretending3 pairs prove a precise universal threshold. Add replication only to a promising narrow bracket. |
| Evidence local and docs confusing | Write raw evidence directly to a NEW outside-build directory; retain source, runtime/classpath identities and a compact plan/progress/result record. Do not clean build/reports or overwrite earlier archives. |

HdrHistogram describes expected-interval correction as generated additional observations, not a workload generator: https://github.com/HdrHistogram/HdrHistogram . Oracle documents allocation/marking/evacuation conditions for G1 Full GC, not a universal97% threshold: https://docs.oracle.com/en/java/javase/21/gctuning/garbage-first-garbage-collector-tuning.html . The cliff location must be measured for this workload. Chronicle getUsing reuse is optional/fallback-dependent and must be checked, not called universally mandatory: https://github.com/OpenHFT/Chronicle-Map/blob/ea/docs/CM_Tutorial.adoc .

## First bounded batch

Primary inputs: Caffeine versus ordinary Chronicle in-memory get;32768 resident entries,4KiB payload,512MiB fixed G1 heap,uniform40001-operation95/5 trace,seed24301,common32MiB/s application allocation,ballast328 and352MiB. Use the actual shared backend configuration and log it; do not assume the notes' stated Caffeine65536 limit if the factory uses40960.

Two independently forked timing regimes: saturated closed-loop service; scheduled50,000 arrivals/s, measured response=end−intendedArrival and service=end−actualStart. Spin pacing is explicit and its timer-only floor is recorded. The schedule origin never moves after a pause, and all arrivals scheduled within the8s offered window must complete or be reported as unserved/censored after a bounded drain. Late requests are never skipped. At most24 workload JVMs:2 points×2 backends×2 regimes×3 counterbalanced passes. Freeze order before use, reverse backend/point order across passes, and keep within-pass logical inputs identical. Fresh arrays are immutable; verify every final resident value/version outside timing.

Initial preparation:3 lightweight disposable lifecycle trials,8s warmup,2s conditioning,8s measured work; no20000-batch maintenance ceremony. Record compiler deltas and warmup/measurement variability as evidence. No claim of full steady-state qualification from a short warmup. Raw service/gap/response histograms and counts, actual windows, allocation demand/realisation/drop counters, GC exposure, host/power/thermal data and process outcome are retained. Pause/floor/function controls are small and separate. No histogram clipping or percentile floor subtraction.

Collection budget:20 minutes for this first workload batch, with per-JVM timeouts and no duplicate slots. Preserve timeout/OOM/host warnings as outcomes and continue. Harness integrity or source mutation stops to fix the harness; a workload pressure outcome does not discard collected data. If the budget expires, report attempted/unattempted slots and decide using retained evidence rather than silently restarting.

## Decision after the batch

Report per-backend p99/p99.9 and pause exposure against measured Caffeine reference occupancy, paired ratios, sign consistency, all warnings and OOM phase. A crossover is bracketed only when the SAME endpoint/regime changes ordering across the two common-input points in repeatable pairs. An already-present advantage is not a new crossover. Separate service crossover, response crossover, and capacity survival. No crossover in this bracket is informative and not a failed experiment.

If a narrow ordinary-get bracket reproduces, freeze a small follow-up with additional paired repeats/one interior point rather than a full factorial matrix. Then evaluate256B with payload-specific ballast on the same heap and a separately labelled getUsing sensitivity where it explains allocation. If response changes ordering but service does not, answer those research questions separately instead of redefining service latency after seeing results. Any next batch gets its own frozen schedule and retained evidence; discovery and follow-up forks are never pooled as if prospectively confirmatory.

## Implementation/review and outcome

Implemented the focused runner, explicit arrival schedule, cumulative churn snapshots and finite resumable collector.49 Java tests pass, including three new schedule/churn tests;207 existing Python tests and four focused collector tests pass. The collector freezes24 slots and resumes retained results without replacing them. OOM phase, unserved arrivals, warmup/measurement compiler activity, endogenous churn loss and host warnings remain visible. Source/runtime changes stop only to protect integrity, never to erase completed slots.

Actual short controls passed in `evidence-archives/focused-control-20261108-001`: both scheduled controls completed exactly50000 requests. Injecting a20ms stall yields response p99.9=19.33ms while service p99.9 remains100ns; the request schedule therefore preserves queued arrivals rather than inserting synthetic histogram samples. The unperturbed scheduled timer floor has response p99.9=20.77µs, so small response differences near that scale must be interpreted cautiously; no floor subtraction is permitted. One-second controls lack the legacy10s host-settling coverage by construction and are timing validation only. Inspection of the actual pinned HDR2.2.2 bytecode shows nextAfter toward negative infinity followed by ceiling rank (not an older rounded-rank implementation); the collector and a boundary regression test use that rule. Compressed distributions receive separate post-collection decoding/bin verification.

Review: the shared logical workload retains no Chronicle payload bank; final contents/entry counts are checked outside timing. Phase timing is continuous, except small explicitly recorded boundaries; the churn worker persists throughout. The true arrival schedule never rebases after a stall and captures any post-offer drain. GC summaries use raw monotonic timestamps only through the actual measurement completion, retaining original full logs separately. Short preparation is intentionally exploratory and compiler warnings remain attached. Proceed with the bounded first batch; its raw outcomes, not blanket acceptance gates, determine useful next work.

## First batch results and next small batches

`focused-rq1-4k-20261108-001` completed24/24 JVMs in about10minutes, with exact source preservation and81 compressed histograms decoded against bins. All forks completed and verified values; one arrival/328MiB Caffeine fork has a compiler warning, retained. At352MiB, scheduled response p99.9 is19.79–20.40ms(Caffeine) versus1.075–1.222ms(ordinary Chronicle), three consistent pairs. Caffeine has30–34 measured Full GCs in the scheduled run, Chronicle zero. In the saturated run Caffeine has105–129 measured Full GCs and2.09–2.49s pause exposure, but service p99.9 remains8.47–8.53µs versus10.93–14.03µs Chronicle. Thus the repeated real-response advantage is clear; AGY's single-fork service crossover at352MiB did not reproduce in this short three-pair batch. Do not manufacture a crossover by mixing response and service.

Next declared batches, selected using this discovery and bounded independently:

1.4KiB scheduled arrivals at0/288MiB, three counterbalanced pairs each:12 JVMs,10minute cap. This supplies the lower-pressure side, which328MiB already exceeds for response.
2.4KiB saturated service at360MiB, three pairs:6 JVMs,5minute cap. This checks the last sliver before capacity failure; OOM phase is reported rather than silently discarded.
3.256B at448/480MiB with the SAME512MiB heap, three pairs/point/regime:24 JVMs,20minute cap. The512MiB heap,32768 entries and50k/s arrival rate stay fixed for RQ2; ballast changes to reach a genuinely high occupancy for smaller payloads. A capacity failure triggers at most one narrow midpoint refinement, not a new broad grid.

Each attempt is separately frozen and resumable, never reuses a completed slot, and retains endogenous outcomes/host warnings. The user explicitly prioritised an initial RQ answer over hardened gates on this host; no endpoint-dependent deletion or whole-study abort is introduced. Source/harness corruption is still distinguished from pressure phenomena. After these small batches, make plots and direct RQ answers before considering any additional work.

## Follow-up outcomes and final targeted refinements

The three follow-ups all completed:12 lower-response forks,6 service-edge forks,24 small-payload forks, in about15minutes. All small-payload and360MiB edge forks have no warnings; the lower-response batch retains one0MiB Caffeine compiler/outside-CPU warning. At4KiB/288MiB the three response p99.9 ratios are0.348/0.359/0.361, all Chronicle lower; at0MiB they are19.94/1.03/0.79, so an eight-second baseline does not reliably order this rare tail. At360MiB Caffeine spends4.28–4.60s/8s in measured GC with253–270 Full GCs, yet service p99.9 stays8.57–8.67µs versus10.54–11.06µs Chronicle. This is a service-versus-response distinction, not missing evidence to be discarded.

At256B on the SAME512MiB heap, ordinary Chronicle service p99.9 is consistently lower at448MiB (ratio0.628–0.635) but consistently HIGHER at480MiB (ratio1.186–1.497). This is a reverse crossover, consistent with increased materialisation allocation as both heaps approach saturation; it is not the originally hypothesised off-heap win emerging with pressure. Scheduled response still favors Chronicle at480MiB in all pairs, ratios0.064–0.519. Occupancy depends on achieved workload/regime: report measured values rather than treating equal ballast as equal occupancy.

Final small refinements, then synthesis rather than another full campaign:

-4KiB arrival0/288MiB,3 pairs,12s warmup/2s conditioning/30s measured:12 JVMs,12minute cap. Match observation duration across both points to reduce rare-GC phase variability.
-4KiB saturated364MiB,3 pairs:6 JVMs,5minute cap, to locate the capacity edge beyond the no-service-crossover360MiB result.
-256B saturated464MiB,3 pairs:6 JVMs,5minute cap, to bisect the observed reverse crossover448→480MiB.
-Secondary getUsing at256B/480MiB in both regimes,3 pairs:12 JVMs,8minute cap; and4KiB/352MiB arrivals,3 pairs:6 JVMs,5minute cap. These explain the allocation mechanism and use a borrowed-buffer read contract; they cannot replace the ordinary-get RQ1 result.

The ordinary `executeNext` method is unchanged. A separate `executeNextUsing` shares logical keys/versions and identical fresh immutable writes, checks actual buffer identity, and has a test proving mutated caller buffers do not alter stored values. Both modes allocate the same tiny caller-buffer footprint. The sensitivity's compiled runtime/source are separately bound; no samples are pooled across access contracts. The first66 ordinary forks remain immutable and their original compiled runtime is retained. Any setup/measurement/verification OOM remains phase-labelled evidence, never a fabricated latency comparison.
