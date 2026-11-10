# Claim-to-evidence map

Prepared from frozen derived inputs; each evidence identity is `(dataset, batch, label)`. The complete identities, warning counts and source groups are in [claims.json](claims.json). No claims are upgraded to confirmatory or causal status.

| ID | Allowed statement | Evidence / figure | Limit |
| --- | --- | --- | --- |
| C01 | The fresh scheduled-response p99.9 ranking changes from Caffeine at 0 MiB to Chronicle at 208 MiB. | 12 forks; 0 warning-bearing. `fig01_response_replication` | Three paired forks per endpoint, all clean; workload-specific 0–208 MiB bracket, not an exact or universal threshold. |
| C02 | 104 MiB remains unresolved; further bisection was skipped under the frozen adaptive rule. | 10 forks; 2 warning-bearing. `fig01_response_replication` | Primary ratios are mixed with only one clean pair; the two clean additional-seed pairs disagree. No favourable-pair selection. |
| C03 | At response p99.99 and p99.999 Chronicle is lower in every fresh pair, including baseline. | 30 forks; 5 warning-bearing. `fig06_percentile_sensitivity` | Baseline advantage is not a pressure-emergent crossover. Approximately 15 nominal upper-tail responses per fork at p99.999; not independent stall episodes. |
| C04 | At all five historical 4 KiB saturated points, Caffeine is lower at service p99/p99.9/p99.99. | 30 forks; 0 warning-bearing. `fig02_estimands` | No observed forward service crossover at these endpoints. Do not join runtime groups into one threshold estimate. |
| C05 | Historical 4 KiB saturated service p99.999 favors Chronicle at every tested point, including 328 MiB. | 30 forks; 0 warning-bearing. `fig02_estimands` | Post hoc extreme endpoint. No newly bracketed pressure crossover; short windows and correlated pauses limit generalisation. |
| C06 | The historical 256 B service ranking is percentile-dependent: p99.9 reverses toward Caffeine, p99.999 toward Chronicle from 448 to 480 MiB. | 12 forks; 0 warning-bearing. `table: historical payload sensitivity` | p99.99 favors Caffeine at both points. Does not establish how the fresh 4 KiB scheduled-response crossover shifts with payload. |
| C07 | At 104 MiB, Caffeine response >100 µs probabilities straddle the 0.1% p99.9 tail boundary. | 3 forks; 1 warning-bearing. `fig05_stall_probabilities` | Histogram-resolution bounds are not confidence intervals. Explains quantile sensitivity, not the unique cause of each stall. |
| C08 | Ordinary 4 KiB Chronicle access allocates about 4,121.6 worker B/op versus 205.6 for Caffeine. | 18 forks; 2 warning-bearing. `fig04_resources` | Observed API/workload cost, not universal library overhead; aggregate GC/allocation does not establish event-level causality. |
| C09 | Chronicle lowers retained Java heap occupancy but has higher sampled RSS in the fresh primary cohort. | 18 forks; 2 warning-bearing. `fig04_resources` | RSS is not PSS or exact native allocation; heap sizes and common demand are equal, total process-memory budgets are not. |
| C10 | Additional seeds repeat the endpoint directions but disagree at 104 MiB. | 12 forks; 3 warning-bearing. `fig01_response_replication` | Limited descriptive robustness. Three of these forks have JIT warnings; no precise seed-level uncertainty. |
| C11 | Reuse sensitivities compare Caffeine with a different Chronicle borrowed-buffer contract. | 12 forks; 2 warning-bearing. `fig07_ownership_sensitivity` | No contemporaneous ordinary-Chronicle arm in these batches; do not claim a matched three-arm causal improvement or a payload-only effect. |
| C12 | The original unconditional protocol remains NO_GO; conditional completion is preserved. | 0 forks; 0 warning-bearing. `docs/TAILCACHE_12_FINAL_ACCEPTANCE.json` | 402 planned invocations attempted; 191 conditionally usable campaign forks, one hard rejection, no replacement. Historical stopping-policy amendment stays explicit. |
| C13 | No tested universal G1 occupancy threshold, production SLA, or payload-only response threshold shift is established. | 0 forks; 0 warning-bearing. `methods and threats to validity` | Single host/collector/heap/load; instrumented in-process scheduler; no independent externally arriving load, equal-total-memory intervention or matched 256 B response midpoint study. |

## Historical-note reconciliation

- The cliff diagnostic remains discovery evidence. Its synthetic expected-interval correction is distinct from directly measured intended-arrival response.
- A single diagnostic service win does not override the later repeated ordinary-service findings. “Exact ~97% cliff” and “reuse is mandatory” are not paper claims.
- Lower GC-managed heap and lower RSS are distinct. The fresh RSS observation must appear wherever a memory-saving claim is made.
- Original RQ1 concerns ordinary operation p99/p99.9. Scheduled response and post hoc extreme percentiles are explicitly identified follow-ups.
- RQ2 receives a limited payload-dependent service comparison, not a precise estimate of how the scheduled-response crossover moves with payload.
