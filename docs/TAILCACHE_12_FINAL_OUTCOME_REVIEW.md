# Task12 final researcher review — 8 November 2026

Task12 execution and analysis are complete as an **observer-conditional study with explicit rejected/inconclusive conditions**. The original unconditional protocol is **NO_GO/unqualified**. This is not a confirmed universal crossover or a confirmed absence of crossover. All402 planned invocations were attempted, including192 campaign slots and64 independent robustness slots. One campaign fork failed the unchanged hard outside-CPU gate and is excluded from statistics, with no replacement. Every original primary condition has explicit rejection under the original joint-observer protocol and separate conditional-regime acceptance facts.

The retained dataset is `evidence-archives/native-final-conditional-completion-dataset-20261108-001/`. Read `dataset.json`, `coverage.csv`, `independent-review-002/audit.json`, `independent-review-002/comparison-summary.csv` and final `acceptance.json` together. The original exported dataset remains unchanged with its pre-review flag; final acceptance records review completion separately. Raw/source archive:229058001bytes,19782 verified members,SHA256`85df767f2b73d8b967655a9d09b08e57337379f5554f3d81f26788c604f62276`. Exported dataset SHA256`a8b88d3da40e8a1ef420c08c9a23559a617c6cb02a289aa5e96ec4878aeff73a`.

## What was executed

| Stage | Planned/attempted invocations | Outcome |
| --- | ---: | --- |
| Functional/integrity/retention controls |14/14|Mechanical and host checks pass|
| Known-GC-pause controls |2/2|Both backends expose the pause in service/completion-gap timing|
| Separate compiler diagnostics |8/8|Complete; one slow thermal metadata-read warning|
| Unprofiled source-matched qualification |16/16|Both passes/backend/payload/recorder pass; maximum compiler interval5ms, maximum total6ms|
| Independent timer/supply floors |10/10|All pass; no floor subtraction|
| Independent pressure calibration |64/64|Complete; one outside-CPU warning and one slow metadata-read warning, propagated to affected bands|
| Low/high pilot |32/32|Complete without warnings|
| Frozen campaign |192/192|191 conditionally usable; one hard CPU rejection, no replacement|
| Two separate robustness seeds |64/64|All pairs physically complete;29/32 pairs warning-free, no seed-specific confidence intervals|

An invocation is not always one JVM: the functional controls include multi-condition smoke checks. Campaign replication is exactly two counterbalanced outer passes with three fresh paired fork ordinals per backend/cell/recorder, not192 independent endpoint comparisons. Workload: one worker,32768 resident entries,256B/4096B values,uniform95/5 reads/updates,seed0x5EED,512MiB fixed G1 heap,32MiB/s common background allocation,30 one-second warmups,8 conditioning and8 analysis intervals. Retained application data is0/96/208/288MiB. Both backends receive the same logical trace and immutable fresh write values; Chronicle has no retained payload-shadow bank. Backend total heap occupancy is intentionally allowed to differ.

The selected measurement source is `7f0313004a2f6bcc3eb4b107e564113733947516139331096f22f4cc79b0a52a`; full source during collection is `838a0845167bce0d32f2e81b91a91c9b80c76d8cedd0cd49995a32cb73c31881`. Exact source archives, VM/JMH identity, custom fixed1/16 sampler/harness artifacts, workload trace hashes, native host records and native-control002 are retained. Code/docs promotion into the final checkout happened only after collection and full-source preservation verification. The supplement's actual controller is SHA-bound in its declaration/archive; the committed counterpart changes only plan locations from ops/ to docs/.

## Interruption and stopping-policy amendment

Original final005 remains terminal under its frozen stopping rule. Campaign slot143, `s24301-b2-sample-calibration-p4096-live96-f3-CHRONICLE_IN_MEMORY`, recorded outside-CPU upper35.0748% against25%. Its thermal, churn, recording and other checks pass, but it is rejected. The original stopped master/state/manifests and seven prerequisite references were not changed. A166063795-byte checkpoint preserves all289 invocations attempted at that point.

A separately declared completion supplement collected only original slots144–192 and the original64 robustness slots. It changed stopping policy for an otherwise valid independent CPU-rejected slot, not the25% acceptance ceiling. It preserved identical properties/order/source/trace, acquired the same exclusive native lock in a fresh scope, and required fresh available-memory/zero-swap preparation,120s quiet and per-fork cold readiness. No old study001–004 fork enters this dataset. No rejected fork was retried, selected away or pooled with accepted data. The interrupted within-pass condition is explicitly unresolved; time/scope segment membership is retained. This post-interruption amendment prevents a confirmatory interpretation of the original study.

## Measurement and numerical review

The independent stdlib auditor imports none of the collector rank/GC/bootstrap parsers. It reconciles386 histogram forks,3088 measured windows,1544 nearest-rank percentile endpoints,451960566 retained JMH samples,376 raw GC logs and26588 measured GC/occupancy events. It independently rebuilds allocation totals/rates and the30 available endpoint bootstrap intervals, including nominal32-comparison Bonferroni and descriptive95% bounds. The primary replay separately decoded5952 compressed HDR distributions and checked exact bins/counts; the archive audit independently verifies every retained byte/member against inventory. All402 invocation inventories/control hashes/source-unchanged facts reconcile.

The independent audit's first attempt incorrectly assumed supply floors had GC logs; floors intentionally do not. Its failure receipt is preserved. The corrected audit excludes timer/supply floors only from GC reconciliation and passes their histogram/allocation checks. No benchmark record or acceptance changed.

Both known-pause controls pass with unified-log/System.nanoTime alignment: Caffeine8.829ms GC overlaps a9.004646ms completion gap; Chronicle13.196ms overlaps13.366888ms. This proves pause observability, not that p99.9 must include a single rare pause. All floor comparisons pass: maximum median floor/workload ratio0.1982, against declared supply0.5 and timer1/3 ceilings. Floor values are descriptive, never subtracted from percentiles.

All final conditioning/measured windows have zero dropped churn bytes; realised rate/JVM allocation checks pass. The prospective minor-loss allowance therefore was not used in this dataset. No campaign evacuation failure was observed. Six-fork/per-pass variation remains visible; there is no outlier trimming or cross-fork histogram pooling. Three campaign JIT warnings remain explicit (13/18/39ms intervals); they block affected claims even though current low-pressure qualification passes.

The two timing regimes remain separate because recording changes throughput/allocation/GC exposure. Fixed sampling repairs adaptive-buffer bias; it does not establish recorder neutrality. Only two outer passes make the bootstrap uncertainty coarse; nominal corrected intervals do not establish guaranteed coverage or independent operation-level replication.

## Pressure and allocation

Measured bands reproduce increasing common application retention, not equal backend occupancy. At288MiB application retention with4KiB payloads, campaign median post-GC used heap is about89.7% Caffeine versus61.6% Chronicle in sparse timing, and90.5% versus63.6% in every-operation timing. At256B the corresponding medians are61.5% versus60.5%, and62.8% versus61.7%. Thus256B does not reach the same high Caffeine occupancy as4KiB; avoid treating all four labels as universal low/moderate/high/severe pressure.

Post-GC used heap and old-region capacity are occupancy proxies, not an exact live-object census. Calibration is independent and recorder/backend-specific, with replica/band limitations retained. Worker allocation medians are approximately13.6B/op(Caffeine256B) versus281.6B/op(Chronicle256B), and205.6B/op versus4121.6B/op at4KiB, in addition to controlled background allocation. They include observed worker instrumentation and are not process-wide profiler values. Chronicle saves retained heap while paying materialisation allocation; neither fact alone implies lower tails.

## RQ1/RQ2 findings and claim limits

Fifteen of sixteen recorder/payload/pressure comparisons retain all12 accepted scheduled forks. Eight comparisons are free of conditional quality limitations; fourteen of the32 planned endpoint directions are resolved by their nominal intervals. The other comparisons/endpoints remain rejected or unresolved. All16 original backend/payload/pressure conditions remain unaccepted under the unconditional joint-observer protocol.

| Payload/recorder | Qualified conditional evidence | Interpretation |
| --- | --- | --- |
|256B, sparse SampleTime|At96MiB, Caffeine has lower p99; p99.9 interval includes equality|High-pressure p99.9 point estimates favor Chronicle but carry quality limits; no accepted pressure-induced crossover|
|256B, every operation|At0/96/208MiB, Chronicle/Caffeine p99.9 ratios are0.479/0.495/0.539; p99 favors Caffeine at96/208MiB|Chronicle's p99.9 advantage is already present at the lowest pressure; it is not evidence of a newly emerging pressure crossover|
|4KiB, sparse SampleTime|At0MiB, Chronicle/Caffeine ratios are1.125(p99),1.354(p99.9)|Caffeine is lower; other sparse cells have explicit quality/missing-data limits|
|4KiB, every operation|At0/96/208MiB, Chronicle is about11–12% higher atp99 and30–35% higher atp99.9|No qualified Chronicle win at these tested points; high-pressure warnings prevent a whole-range no-crossover claim|

Across all accepted campaign forks,4KiB Caffeine p99.9 spans roughly8.13–8.47µs versus Chronicle10.22–11.89µs. These ranges are descriptive, not a substitute for the condition-specific intervals. At256B the recording regimes show substantially different p99.9 patterns. The two robustness seeds repeat the qualitative4KiB ordering and256B every-operation advantage;256B sparse p99.9 ratios span0.742–1.375. Each seed has one fork/backend/cell, three robustness pairs have warnings, and robustness does not repair rejected primary conditions.

RQ1 remains inconclusive as an unconditional pressure-induced crossover. RQ2 shows a payload-dependent conditional tradeoff: larger payloads substantially increase Chronicle's access/materialisation cost in the tested workload despite lower retained heap. The dataset supports this limited observation, not a general claim that Chronicle never crosses over, that all caches behave similarly, or that a particular heap/collector/concurrency/workload has a universal threshold.

## Timeline in Asia/Kolkata

| Attempt | Protocol creation → terminal/export | Preserved outcome |
| --- | --- | --- |
|Final001|7 Nov17:55 →20:13|133 invocations; pilot startup-thermal rejection|
|Final002|7 Nov21:24 →22:08|37 invocations;8192 conditioning bytes dropped|
|Final003|7 Nov22:22 →23:02|34 invocations;16ms qualification compiler interval|
|Final004|7 Nov23:14 →23:47|29 invocations;77.9ms thermal metadata bracket|
|Final005|7 Nov23:52 →8 Nov06:00|289 invocations; hard CPU rejection at campaign143|
|Completion supplement|8 Nov06:10 →08:42|Only113 remaining scheduled invocations; full402 execution/export|

Amendments were declared/reviewed/tested before their fresh collection; earlier cohorts remain rejected. The supplement stopping amendment is separately identified as post-interruption. None of these historical cohorts fills missing final slots. Host/settings were not changed to manufacture a favorable ranking.

## Acceptance decision

Accept the complete source-matched conditional dataset and explicit rejected/inconclusive condition accounting as the completed Task12 execution/analysis deliverable under the user's authorised reasonable protocol relaxations. Do not accept the original unconditional protocol or promote this to confirmatory RQ1/RQ2 evidence. Keep original stopping-rule failure, all rejected forks, uncertainty, provenance, amendments and archive checksums. No further fork is needed to complete this declared execution; any future stronger causal/coherence study is a new protocol.

Persisted cold/open/page-fault behaviour, two-JVM sharing, object reuse/getUsing, eviction, other collectors/heaps/concurrency and broader host generalisation remain outside this study. No claim is made for them. The final committed207-test check passed. The immutable acceptance manifest and verified recovery-timer shutdown are recorded in separate operational receipts.
