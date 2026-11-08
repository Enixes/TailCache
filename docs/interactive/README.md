# TailCache interactive results

Open [the standalone explorer](../TAILCACHE_RESULTS_EXPLORER.html) directly in a browser. The file includes its dataset, source downloads, styles and scripts; it needs no server, package installation or network connection. The live session's restricted preview is at `http://127.0.0.1:8765/` while that local process remains running.

The default matrix covers 22 primary comparisons from all 132 workload JVMs. “Include all timing channels” expands it to 56 comparisons and 168 percentile conclusions. Inspect a row for the actual fork values, ratios, sample counts, heap observations, GC and warnings. Graphs separate runtime groups, measurement durations and read contracts; getUsing uses its own paired Caffeine controls. Zoom changes only the graph's observed range. A single point, mixed ordering or an advantage already present at baseline is not labelled a new crossover.

The three percentile columns remain visible together. The graph percentile switch changes the plotted endpoint and highlights that table column. Export produces the visible table, including all three percentile conclusions. The source dataset, HDR audit and researcher review also download directly from embedded copies. The source dataset copy matches its retained SHA-256.

Rebuild from the repository root:

```bash
rtk proxy python3 scripts/tailcache12_build_explorer.py
rtk proxy python3 -m unittest discover -s scripts -p 'test_tailcache12_explorer.py'
```

The builder reads the retained p99.99 study when available. A fresh checkout without ignored evidence archives recovers the identical, hash-verified input from the committed standalone HTML. The template is `scripts/tailcache12_explorer.html`; the generator is `scripts/tailcache12_build_explorer.py`. No benchmark runner is invoked.

Design decisions and the QA inventory are in [DESIGN.md](DESIGN.md). Browser checks were run through the in-app browser using a localhost server restricted to this single generated HTML file. Desktop, 390 px and 320 px layouts were reviewed. The browser's direct file-URL restriction does not affect opening the saved HTML manually in a normal browser.
