# Larger-payload worth pilot — prospective plan, 17 November 2026

This bounded extension addresses the user's request to test whether larger values could reveal a service crossover, while proving usefulness before investing in a larger matrix. Existing 4 KiB high-pressure observations show substantial GC wall time without a forward service-p99.9 reversal. The completed policy and JMH checks also show that small-payload service rankings depend on configuration/harness. A positive Chronicle result is not a condition for an informative experiment.

## Four-workload feasibility/discovery screen

Test **8 KiB, 32,768 residents, zero and 208 MiB common application ballast, both original backends: four workload JVMs**, one pair per pressure. Keep the existing ordinary 95/5 long-trace service runner, fixed 512 MiB G1 heap, seed 24301 and offered 32 MiB/s churn. Alternate backend order between the two cells. Use 12 seconds warmup, two seconds conditioning and **ten seconds measurement**. This is a cheap feasibility/direction screen, not confirmatory evidence or a replacement primary endpoint.

The Caffeine payload alone is 256 MiB; the high point has 464 MiB of raw cache-plus-ballast payload before metadata. Record actual post-GC occupancy, allocation, lost churn, service/read/update/gap tails, RSS, compilation and host state. All values/residents and source/runtime/raw fingerprints must pass their existing integrity checks. An OOM or incomplete outcome is a feasibility boundary, never a Chronicle latency win. Both backends get identical logical demand, not equal total heap occupancy or process RSS.

Use the already qualified policy/trace runtime byte-for-byte, with a new source/archive cohort and zero new functional-qualification JVMs. Validate the retained qualification/compiler/source/class/dependency bindings before capture. Three 12/2/4-second controls precede workloads: timer floor, injected 20 ms stall and fresh-supply floor at 8 KiB. Preserve every control/outcome warning. No floor subtraction or retrospective window changes. The exclusive native lock prevents overlap with the preceding sequence.

## Frozen worth/selection rule and maximum expansion

Independently audit the complete pilot before selecting anything. The endpoint is combined saturated-service **p99.9** throughout; the rarer tails remain diagnostic and cannot trigger an expansion by themselves. Let R0 and R208 be Chronicle/Caffeine paired ratios from complete, value-correct pilot pairs.

1. If both pairs are complete, R0 >= 1, R208 <= 1.10 and R208/R0 <= 0.90, select a **pressure confirmation**: 8 KiB at 0/208 MiB, two fresh paired repetitions per endpoint (eight workload JVMs).
2. Otherwise, if both pairs are complete and R0 <= 0.90, select a **payload confirmation**: 4/8 KiB at zero ballast, two fresh paired repetitions per payload (eight workload JVMs). An advantage already at baseline is not pressure-emergent.
3. Otherwise stop after the four-workload screen, retaining near ties, contrary results and failures. Do not add higher pressures, another payload, or favorable replacement forks.

These are budget-allocation rules rather than significance tests. Record JIT/host/demand warnings with the selected evidence; a candidate remains provisional. A selected confirmation uses a separate frozen design/source-linked evidence directory and **60/4/30-second phases** for both endpoints. It repeats matched timer/injected-stall/supply controls (8 KiB supply; also 4 KiB supply for a payload comparison). No second selection or recursive expansion follows mixed confirmation results. All-phase counters, full values, raw histograms and GC/event alignment require independent reconciliation before reporting conclusions.

Maximum: **four pilot plus eight conditional confirmation workload JVMs**, with three pilot and at most four confirmation controls. Forks, phase regimes and discoveries/confirmations remain separate. Any final direction is descriptive; no exact or universal threshold is inferred.

At the fixed resident count, 16 KiB values require 512 MiB of retained payload alone and 32 KiB require 1 GiB. They cannot fit Caffeine's 512 MiB heap with required metadata/application state. Do not spend benchmark JVMs rediscovering that arithmetic; changing heap or resident count is a different design and is outside this screen.
