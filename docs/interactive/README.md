# TailCache interactive results

Open [the standalone explorer](../TAILCACHE_RESULTS_EXPLORER.html) directly in a browser. The file includes its dataset, source downloads, styles and scripts; it needs no server, package installation or network connection. The live session's restricted preview is at `http://127.0.0.1:8765/` while that local process remains running.

The default matrix covers 22 primary comparisons from all 132 workload JVMs. “Include all timing channels” expands it to 56 comparisons and 224 percentile conclusions. Inspect a row for the actual fork values, ratios, sample counts, heap observations, GC and warnings. Graphs separate runtime groups, measurement durations and read contracts; getUsing uses its own paired Caffeine controls. Zoom changes only the graph's observed range. A single point, mixed ordering or an advantage already present at baseline is not labelled a new crossover.

The four percentile columns remain visible together. The graph percentile switch changes the plotted endpoint and highlights that table column. Export produces the visible table, including all four percentile conclusions. The source dataset, HDR audit and researcher review also download directly from embedded copies. The source dataset copy matches its retained SHA-256.

Rebuild from the repository root:

```bash
rtk proxy python3 scripts/tailcache12_build_explorer.py
rtk proxy python3 -m unittest discover -s scripts -p 'test_tailcache12_explorer.py'
```

The builder reads the retained p99.999 study when available. A fresh checkout without ignored evidence archives recovers the identical, hash-verified input from the committed standalone HTML. The template is `scripts/tailcache12_explorer.html`; the generator is `scripts/tailcache12_build_explorer.py`. No benchmark runner is invoked.

Design decisions and the QA inventory are in [DESIGN.md](DESIGN.md). Browser checks were run through the in-app browser using a localhost server restricted to this single generated HTML file. Desktop, 390 px and 320 px layouts were reviewed. The browser's direct file-URL restriction does not affect opening the saved HTML manually in a normal browser.

## p99.999 and terminology

The fourth endpoint is derived from the same raw HDR distributions, independently decoded with pinned HDR 2.2.2 and checked against weighted bin ranks. No benchmark runs are needed. The graph shows nominal upper-tail support for its selected view; expanded rows show support and counts strictly above the selected bin for every percentile. At p99.999, scheduled 8 s and 30 s forks have just 4 and 15 nominal upper-tail observations. Original endpoints and warnings remain visible.

“Understand the terms” explains ballast, heap/off-heap, churn, GC, saturated and scheduled workloads, service/response/waiting/gap times, percentiles, payload, throughput, forks, runtime groups, ownership contracts and crossovers. The example separates 20 ms of waiting from 5 µs of service.

## Static Vercel deployment

Stage the standalone page and static configuration only:

```bash
rtk proxy python3 scripts/tailcache12_build_explorer.py --site-out build/tailcache-results-site
```

Deploy that two-file directory, using the configured Vercel account/project. The page includes its research data downloads; the deployment requires no Java build, server, environment variables or raw archive upload. The deployment receipt records the actual target, source hashes and deployed URL after verification.

### Live protected deployment

[Open TailCache results](https://tailcache-results.vercel.app/). Sign in with a Vercel account that has access to Enixes’ projects / tailcache-results. Authentication protects **all deployments**, including production aliases and the unique generated deployment URL. No temporary sharing link was created.

The deployed source is commit `9a7e581`; its exact index.html SHA-1 matches the deployment source file UID. All three signed-out URL checks redirect to Vercel SSO without returning the embedded results. The browser also reaches the Vercel login page. The authenticated page was previously tested locally; this session has no signed-in Vercel browser, so it did not repeat those interactions behind the hosted login. See [deployment.json](deployment.json) for target, hashes and checks.
