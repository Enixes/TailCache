# Frozen exploratory research claims — 8 November 2026

Historical snapshot: the subsequent [10 November midpoint comparison](TAILCACHE_MIDPOINT_RESULTS.md)
and [current experiment status](TAILCACHE_CURRENT_STATE.md) supersede the earlier
open midpoint question while preserving this dated evidence.

Scope: the retained 132 workload forks, ordinary get as primary, 512 MiB G1 heap, one worker, 32,768 resident entries and matched application ballast/allocation demand. These claims describe this tested workload and hardware. All warning-bearing forks remain visible. This version includes the requested post hoc p99.99, p99.999 and full-tail analyses; it does not rewrite the original endpoints.

## Claims that the data support

| Scope | Frozen claim | Limit |
| --- | --- | --- |
| 4 KiB ordinary saturated service, p99/p99.9/p99.99 | Caffeine is lower at all five tested pressure points. | No forward service crossover was observed for those endpoints within the tested high-pressure range. |
| 4 KiB ordinary saturated service, p99.999 | Chronicle is lower at all five tested points, including the lowest measured service ballast of 328 MiB. | An advantage throughout a measured range is not a newly bracketed pressure crossover. Builds remain separate. |
| 4 KiB ordinary scheduled response, p99.9 | Later-runtime 30 s measurements change from Caffeine lower at 0 MiB to Chronicle lower at 208 MiB, in all three pairs at both endpoints. | The bracket is 0–208 MiB; no precise threshold or intermediate 104 MiB observation exists. |
| 4 KiB ordinary scheduled response, p99.99/p99.999 | Chronicle is already lower at the 0 MiB baseline and remains lower at all measured 30 s pressure points. | Do not describe this baseline advantage as a new forward crossover. |
| 256 B ordinary saturated service | Earlier-runtime p99.9 changes from Chronicle lower at 448 MiB to Caffeine lower at 480 MiB; p99.99 favors Caffeine throughout; p99.999 changes from Caffeine lower at 448 to Chronicle lower at 480. | No percentile-independent service crossover exists. Later-runtime midpoints cannot narrow the earlier-runtime brackets. |
| getUsing sensitivity | Buffer reuse changes read allocation, ownership and the measured tail. | Keep its own paired controls and report it separately from ordinary get. |

## What the full tail adds

At some 4 KiB saturated points, Caffeine has lower probability of exceeding 100 µs or 1 ms, yet Chronicle has lower probability of exceeding 10 ms. At 368 MiB, Chronicle has lower probability at all three thresholds. Thus the distributions can cross within the latency tail; a single percentile is not sufficient to establish that one backend is faster throughout the distribution. Count-normalized operation probabilities are not pause-event rates.

The table below contains every primary comparison. Each cell reports the observed lower-probability backend only when all three pair bounds support that ordering. Equal observed rates and mixed pairs remain explicit. Histogram resolution bounds are not confidence intervals.

| Payload / ballast | Workload / contract / window / build | >100 µs | >1 ms | >10 ms |
| --- | --- | --- | --- | --- |
| 256 B / 448 MiB | Scheduled response / ordinary / 8 s / Earlier build | Caffeine lower | Mixed pairs | Equal observed rates |
| 256 B / 448 MiB | Saturated service / ordinary / 8 s / Earlier build | Caffeine lower | Caffeine lower | Equal observed rates |
| 256 B / 464 MiB | Saturated service / ordinary / 8 s / Later build | Caffeine lower | Caffeine lower | Equal observed rates |
| 256 B / 472 MiB | Saturated service / ordinary / 8 s / Later build | Caffeine lower | Caffeine lower | Equal observed rates |
| 256 B / 480 MiB | Scheduled response / ordinary / 8 s / Earlier build | Chronicle lower | Chronicle lower | Chronicle lower |
| 256 B / 480 MiB | Scheduled response / reuse / 8 s / Later build | Chronicle lower | Chronicle lower | Chronicle lower |
| 256 B / 480 MiB | Saturated service / ordinary / 8 s / Earlier build | Caffeine lower | Mixed pairs | Chronicle lower |
| 256 B / 480 MiB | Saturated service / reuse / 8 s / Later build | Chronicle lower | Chronicle lower | Chronicle lower |
| 4096 B / 0 MiB | Scheduled response / ordinary / 8 s / Earlier build | Caffeine lower | Mixed pairs | Equal observed rates |
| 4096 B / 0 MiB | Scheduled response / ordinary / 30 s / Later build | Caffeine lower | Chronicle lower | Equal observed rates |
| 4096 B / 208 MiB | Scheduled response / ordinary / 30 s / Later build | Chronicle lower | Chronicle lower | Equal observed rates |
| 4096 B / 248 MiB | Scheduled response / ordinary / 30 s / Later build | Caffeine lower | Chronicle lower | Equal observed rates |
| 4096 B / 288 MiB | Scheduled response / ordinary / 8 s / Earlier build | Chronicle lower | Chronicle lower | Equal observed rates |
| 4096 B / 288 MiB | Scheduled response / ordinary / 30 s / Later build | Chronicle lower | Chronicle lower | Equal observed rates |
| 4096 B / 328 MiB | Scheduled response / ordinary / 8 s / Earlier build | Chronicle lower | Chronicle lower | Mixed pairs |
| 4096 B / 328 MiB | Saturated service / ordinary / 8 s / Earlier build | Caffeine lower | Caffeine lower | Chronicle lower |
| 4096 B / 352 MiB | Scheduled response / ordinary / 8 s / Earlier build | Chronicle lower | Chronicle lower | Chronicle lower |
| 4096 B / 352 MiB | Scheduled response / reuse / 8 s / Later build | Chronicle lower | Chronicle lower | Chronicle lower |
| 4096 B / 352 MiB | Saturated service / ordinary / 8 s / Earlier build | Caffeine lower | Caffeine lower | Chronicle lower |
| 4096 B / 360 MiB | Saturated service / ordinary / 8 s / Earlier build | Caffeine lower | Chronicle lower | Chronicle lower |
| 4096 B / 364 MiB | Saturated service / ordinary / 8 s / Later build | Caffeine lower | Chronicle lower | Chronicle lower |
| 4096 B / 368 MiB | Saturated service / ordinary / 8 s / Later build | Chronicle lower | Chronicle lower | Chronicle lower |

## Uncertainty and claims not supported

- Three matching pairs describe consistency, not statistical significance. No pooled histogram, outlier deletion, floor subtraction or new acceptance-gate relaxation was used.
- All exact curve points are empirical survival probabilities at HDR upper-bin boundaries. At a requested threshold within an occupied bin, report definite–possible exceedance counts. Zero observed events is not proof of zero risk; show the operation count and 1/N resolution.
- Responses delayed by the same pause are correlated. At p99.999, 8 s and 30 s scheduled forks have only 4 and 15 nominal tail observations. These are not independent stall episodes.
- Off-heap retention and ordinary-get materialization costs provide a plausible mechanism, but aggregate histograms cannot attribute each stall to GC, compilation, the scheduler or storage.
- The collector measures scheduled response directly from intended arrival times; it does not generate external network traffic. Saturated and scheduled workloads are separate runs.

## Decision before another run

No confirmation batch is launched by this offline extension. The existing evidence already answers whether a useful effect exists. A bounded 0/104/208 MiB, three-pair, 4 KiB scheduled-response batch would materially add one new pressure point and test whether the p99.9 bracket repeats; it would not establish a universal threshold, causal attribution, independent extreme-tail episodes or robustness across hardware.

If that narrower question is worth the collection time, freeze a separate batch before launch: same source-matched workload and runtime throughout its 18 slots, same heap/entries/arrival/churn/warmup/measurement settings, fresh output directory, counterbalanced order, retained warnings, and resume completed slots without replacement. Report it as a separate confirmation dataset rather than pooling it with these exploratory forks. No additional run is needed to complete the requested offline tail explanation.
