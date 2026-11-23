# TailCache interactive results

Open [the standalone explorer](../TAILCACHE_RESULTS_EXPLORER.html) directly in a browser. The file includes its dataset, source downloads, styles and scripts; it needs no server, package installation or network connection.

The default matrix covers 22 primary comparisons from all 132 workload JVMs. “Include all timing channels” expands it to 56 comparisons and 224 percentile conclusions. Inspect a row for the actual fork values, ratios, sample counts, heap observations, GC and warnings. Graphs separate runtime groups, measurement durations and read contracts; getUsing uses its own paired Caffeine controls. Zoom changes only the graph's observed range. A single point, mixed ordering or an advantage already present at baseline is not labelled a new crossover.

The four percentile columns remain visible together. The graph percentile switch changes the plotted endpoint and highlights that table column. Export produces the visible table, including all four percentile conclusions. The source dataset, HDR audit and researcher review also download directly from embedded copies. The source dataset copy matches its retained SHA-256.

Rebuild from the repository root:

```bash
python3 scripts/tailcache12_build_explorer.py
python3 -m unittest discover -s scripts -p 'test_tailcache12_explorer.py'
```

The builder reads the retained p99.999 study when available. A fresh checkout without ignored evidence archives recovers the identical, hash-verified input from the committed standalone HTML. The template is `scripts/tailcache12_explorer.html`; the generator is `scripts/tailcache12_build_explorer.py`. No benchmark runner is invoked.

Design decisions and the QA inventory are in [DESIGN.md](DESIGN.md). Browser checks were run through the in-app browser using a localhost server restricted to this single generated HTML file. Desktop, 390 px and 320 px layouts were reviewed. The browser's direct file-URL restriction does not affect opening the saved HTML manually in a normal browser.

## p99.999 and terminology

The fourth endpoint is derived from the same raw HDR distributions, independently decoded with pinned HDR 2.2.2 and checked against weighted bin ranks. No benchmark runs are needed. The graph shows nominal upper-tail support for its selected view; expanded rows show support and counts strictly above the selected bin for every percentile. At p99.999, scheduled 8 s and 30 s forks have just 4 and 15 nominal upper-tail observations. Original endpoints and warnings remain visible.

“Understand the terms” explains ballast, heap/off-heap, churn, GC, saturated and scheduled workloads, service/response/waiting/gap times, percentiles, payload, throughput, forks, runtime groups, ownership contracts and crossovers. The example separates 20 ms of waiting from 5 µs of service.

## Full tail and stall probabilities

“Beyond a single percentile” follows the crossover graph’s payload, measurement, contract and duration. Select one observed pressure point/build and all three curve pairs or one pair. The six step curves use every recorded bin, with logarithmic latency/probability axes and guides at 100 µs, 1 ms and 10 ms. Curve focus and hover expose per-fork counts. Zero-event tails are shown in the table, not plotted as log(0).

Switch “Show conclusions for” to “Stall probabilities” to inspect all three threshold conclusions at every filtered point. Expanded rows and the full-tail section show definite–possible counts and denominators. CSV includes both views regardless of the selected display mode. Download full binned tails, their independent audit and the frozen research claims from Methods. The page uses native gzip decoding for the selected distributions, without a CDN or new network requests; current browsers with DecompressionStream are required to draw the full curves. Stall tables remain available if decoding is unsupported.

The retained offline derivative is `evidence-archives/focused-rq-tails-20261108-001/`. No new workload runs are launched. The [0/104/208 MiB follow-up](../TAILCACHE_MIDPOINT_RESULTS.md) is a separate cohort.
