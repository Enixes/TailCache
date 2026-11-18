# Mechanism study: update locality reverses the response ranking

The bounded 18 November scope is collected and audited: **64 research JVMs, 32 paired comparisons**, plus three functional JVMs and six separate controls. The three functional JVMs are shared setup, not a sum of copied per-cohort receipt fields; the [final review](REVIEW.md) discloses the frozen reuse-metadata error. Both conditional expansions satisfied their written worth rules. No research fork was replaced. This is a working, agent-reviewed research artifact; author approval, a public raw-evidence deposit and independent host replication remain outstanding.

The strongest new result is a **response reversal at identical 5% writes and fresh-write allocation demand**. With 2,048 eligible update keys, Caffeine response p99.9 is 24.751–28.063 µs versus Chronicle 74.815–244.095 µs. With 32,768 eligible keys, Caffeine is 8.905–9.699 ms versus Chronicle 125.375–226.559 µs. Every direction repeats in both seeds with reversed backend order. None of the four concentrated-update pairs is entirely warning-free; one distributed-update pair is. This is warning-inclusive replication, not a clean-host confirmation. Caffeine GC exposure falls 82–85% when updates concentrate. Reads, write flags, resident count and intended arrival rate stay matched. Update locality, value survival and cache-policy traffic remain bundled; the experiment does not isolate object promotion.

Other outcomes constrain the claim:

- At 0.5% writes, four separate 90-second pairs favor Chronicle (response p99.9 ratio 0.0345–0.0577). A fresh, warning-free 30-second 512 MiB pair instead favors Caffeine (ratio 1.992). The cohorts also differ in seeds and collection time, so this does not isolate an effect of measurement duration. No universal write threshold follows.
- At 5% writes, increasing the heap from 512 to 1,024 MiB lowers Caffeine total GC exposure yet **increases** its p99.9 in both seeds: 8.798→12.567 ms and 9.110→14.860 ms. Fewer, longer pauses explain why a pause sum alone cannot determine a numerical quantile. All four backend comparisons still favor Chronicle.
- The single-seed payload screen repeats the 4 KiB 0%→5% write-rate reversal. At 256 B, Chronicle is already lower at both endpoints, by a much smaller absolute amount. This does not establish a payload crossover boundary.
- Async logging meets the development selection rule (about 16%/20% lower median GC-linked gap excess); phase priming misses its rule (one fewer compiler warning, where two were required). Later cohorts use async and zero priming. These choices are development, not independent confirmations.
- Across the 44 calibrated transport forks, the full-safepoint M3 variant lowers descriptive median absolute response-p99.9 error from M2's 115.6 to 83.6 µs. These mixed-condition medians are not pooled latency quantiles or population estimates. Both variants remain approximate: M1/M2/M3 call 21/22 calibrated transport pair directions, while lower-total-GC calls 22/22. The constant pilot quantile remains better for Chronicle alone in aggregate. No precise ex ante selector is established.

**Qualification remains explicit.** Forty-two of 64 forks have warnings (49 instances: 31 zswpin, one zswpout, nine compiler, seven outside-CPU, one thermal-throttle). Fourteen Caffeine forks have measured evacuation failures; none have measured full GC. Failures/warnings are retained, not external exclusions or reasons for successful-only reruns. The historical occupancy rule still failed, but compared different G1-cycle phases; it does not prove that every fork was physically nonstationary. One host, an internal arrival observer, few seeds and bundled library semantics limit generalization. The original pressure-emergent saturated-service p99/p99.9 crossing remains unsupported; the original unconditional NO_GO is unchanged.

Read [the all-point table and model scores](RESULTS.md), [sequential code/research reviews](COHORT_REVIEWS.md), [final review](REVIEW.md), [figures](FIGURES.md) and [frozen plan](../TAILCACHE_MECHANISM_PLAN.md). Download [portable data](mechanism-data-20261118.json), [point conclusions](point-conclusions.csv), [stall-rate bounds](stall-rates.csv) and [winner scores](winner-scores.json). Full quantized distributions, all four model percentiles through p99.999, warnings, GC/safepoint inputs, actual schedules and old model source/parameters are portable.

```sh
python3 scripts/tailcache12_mechanism_report.py verify
python3 scripts/tailcache12_mechanism_reproduce.py --out /tmp/mechanism-model-replay.json
python3 scripts/tailcache12_mechanism_report.py report
python3 -m unittest discover -s scripts -p 'test_tailcache12_mechanism*.py'
python3 scripts/tailcache12_mechanism_figures.py
```

Figure regeneration uses matplotlib 3.10.7. DOM integration uses jsdom 27.2.0; real-browser/layout coverage is reported separately. The package verifies 1,580 research quantiles, 64 exact read/update unions, 960 threshold bounds, 790 ratios and 3,456 model-summary fields. Raw audits separately decode 350 research/control HDR files, reconcile 1,715 nonempty endpoints and 2,405 raw-file hashes, and verify archived source/runtime and independent logical replay. Exact model replay uses the same frozen solvers; it is not an independent implementation.

Do not relaunch the completed sequence into its old directories. Reporting sources were installed only after its native scope ended; a future performance experiment needs a distinct source-matched cohort. Earlier packages and rejected evidence are unchanged. Three inactive historical compressed checkpoints were relocated with verified hashes and original-path links to the larger local filesystem; this is space recovery, not an off-host backup.

The [deep re-review](REREVIEW_20261118.md) fixes fail-open dataset coverage/packaging checks and pins executable model sources. Its new receipts retain the initial verifier/review records; no measured data, quantile or frozen package hash changes.
