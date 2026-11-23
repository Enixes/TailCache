# TailCache experiment status

**Updated 23 November 2026.** The experiment compares Caffeine and ordinary
in-memory Chronicle Map under controlled Java 21 workloads. Start with the
[experiment questions](../README.md#experiment-questions-and-results), then use
[the evidence index](EXPERIMENT_EVIDENCE.md) or [interactive results](../output/html/tailcache-preprint-reader.html).

| Question | Current result | Scope |
| --- | --- | --- |
| RQ1. Does added application data cause a service p99 or p99.9 crossover? | No robust pressure-induced crossover was observed. | Ordinary access under the tested saturated workloads. The original unconditional Task 12 outcome remains NO_GO. |
| RQ2. Does payload size change the saturated-service ranking? | Chronicle led at 256 B and Caffeine led at 4 KiB in the 48-pair matrix. | One cache worker and the tested cache settings. |
| RQ3. Can the write-key set reverse response p99.9 at the same write rate? | At 4 KiB and 5% writes, Caffeine led with 2,048 eligible write keys and Chronicle led with 32,768 on both hosts. | 50,000 intended arrivals/s, uniform reads, and zero added application data. Write locality and overwrite intervals vary together. |

## Latest follow-up

The [23 November Pop!_OS results](nov23-popos-followup/) repeated the RQ3 direction at
100,000 arrivals/s and 2.5% writes, keeping write demand near 2,500/s. At 50,000
arrivals/s with 10% and 20% writes, Chronicle led both full-key pairs. The
concentrated-write pairs split at both write fractions. Both split-write timing
pilots failed the 5% ratio-shift gate, so their component measurements remain
qualification diagnostics.

[20 November results and archive](second-host-20261120/) ·
[23 November archive](nov23-popos-followup/archive/) ·
[Fork-level timing and G1 audit](preprint/timing-audit.json) ·
[Portable collection](PORTABLE_EXPERIMENT.md)

## Earlier experiment records

- [18 November mechanism runs](https://github.com/Enixes/TailCache/blob/d0841fe3af5df8a251ff740a52d0e813cad1dce5/docs/mechanism/RESULTS.md) preserve constrained-order
  repeats, longer windows, heap headroom, warnings, and contrary results.
  The [predictor runs](https://github.com/Enixes/TailCache/blob/d0841fe3af5df8a251ff740a52d0e813cad1dce5/docs/predictor/RESULTS.md) retain the failed boundary forecasts
  and mixed fresh 0.5% pairs.
- [17 November results](https://github.com/Enixes/TailCache/blob/d0841fe3af5df8a251ff740a52d0e813cad1dce5/docs/service-followup/RESULTS_20261117.md) cover 184 workload
  JVMs across eight cohorts, with 30 separate controls. The
  [offline verifier](https://github.com/Enixes/TailCache/blob/d0841fe3af5df8a251ff740a52d0e813cad1dce5/docs/service-followup/portable-verification-20261117.json)
  checks the exported distributions, quantiles, counts, and ratios.
- The [original acceptance record](TAILCACHE_12_FINAL_ACCEPTANCE.json),
  [focused exploration](TAILCACHE_FOCUSED_RESULTS.md), and
  [10 November midpoint](TAILCACHE_MIDPOINT_RESULTS.md) retain their protocol
  and timing assumptions. The midpoint's scheduled-response result was bracketed
  between 0 and 208 MiB for its short-trace workload. Earlier reuse diagnostics
  report a distinct caller-owned buffer API.

[Experiment plan](PLAN.md) · [Evidence index](EXPERIMENT_EVIDENCE.md)
