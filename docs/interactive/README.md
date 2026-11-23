# TailCache interactive results

**Updated 17 November 2026.** The first section now covers the [completed eight-cohort extension](../service-followup/RESULTS_20261117.md): 184 research JVMs, 58 point groups, p99 through p99.999, per-pair ratios, full-tail/stall-rate views, warnings and seven new figures. Earlier sections below retain their own frozen datasets and definitions. [QA boundary](SERVICE_QA_20261117.md): DOM integration passes; the CUA browser host is unavailable, so this version has no new real-browser layout/interaction signoff.

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

Stage the protected static page, separate same-origin follow-up JSON, scientific figure assets and configuration:

```bash
rtk proxy python3 scripts/tailcache12_build_explorer.py --site-out build/tailcache-results-site
```

Deploy that staged directory, using the configured Vercel account/project. The page includes its research data downloads; the deployment requires no Java build, server, environment variables or raw archive upload. The deployment receipt records the actual target, source hashes and deployed URL after verification.

### Live protected deployment

[Open TailCache results](https://tailcache-results.vercel.app/). Sign in with a Vercel account that has access to Enixes’ projects / tailcache-results. Authentication protects **all deployments**, including production aliases and the unique generated deployment URL. No temporary sharing link was created.

The [deployment receipt](deployment.json) is authoritative for the current source commit, hashes, aliases, SSO configuration and checks. Earlier authenticated live browser checks remain in its preserved history; they do not establish visual signoff for new content. Do not create bypass/share links or make the data asset public.

## Full tail and stall probabilities

“Beyond a single percentile” follows the crossover graph’s payload, measurement, contract and duration. Select one observed pressure point/build and all three curve pairs or one pair. The six step curves use every recorded bin, with logarithmic latency/probability axes and guides at 100 µs, 1 ms and 10 ms. Curve focus and hover expose per-fork counts. Zero-event tails are shown in the table, not plotted as log(0).

Switch “Show conclusions for” to “Stall probabilities” to inspect all three threshold conclusions at every filtered point. Expanded rows and the full-tail section show definite–possible counts and denominators. CSV includes both views regardless of the selected display mode. Download full binned tails, their independent audit and the frozen research claims from Methods. The page uses native gzip decoding for the selected distributions, without a CDN or new network requests; current browsers with DecompressionStream are required to draw the full curves. Stall tables remain available if decoding is unsupported.

The retained offline derivative is `evidence-archives/focused-rq-tails-20261108-001/`. No new workload runs are launched. The later 10 November 0/104/208 MiB confirmation batch and 17 November extension are now complete and presented separately.

The full-tail update is deployed and authenticated hosted checks passed: all-fork/single-pair curves, the complete stall matrix and exact frozen-claims download. Clean signed-out requests to both production aliases and the new unique deployment URL still redirect to Vercel SSO. The previous deployment receipt remains in deployment.json history.

## Follow-up regeneration

The main builder preserves and regenerates all three appended components. To refresh only the 17 November section, run `rtk proxy python3 scripts/tailcache12_service_explorer.py --site-out /tmp/tailcache-service-site-20261117`. Offline HTML embeds the complete new package and PNGs; hosted staging uses the same data hash with a separate protected `service-data.json` and figure files. Full-curve fetch verifies SHA-256 before decode. `scripts/tailcache12_service_dom_qa.cjs` documents the optional jsdom integration test; it is software testing, not browser visual review.

## Mechanism extension —18 November2026

The top mechanism section adds all 64 research forks/32 paired comparisons, separate cohort roles, channel/percentile selectors throughp99.999, all-point conclusions, conditional-model values, exact quantized tails and strict 100 µs/1 ms/10 ms bounds. It defaults to the reversed-order update-set repeat. The hosted full dataset is lazy-loaded with a SHA256 check; the standalone HTML embeds it. Empty update channels at 0% remain empty. Definitions explain update sets, headroom, priming, safepoint envelopes and collector failures. Existing historical sections/data remain preserved. New scientific figures and current manuscript downloads accompany the reviewed dataset. Authentication stays enabled for all deployments; no bypass/share links are created. See the current deployment and QA receipts for exact coverage.
