# TailCache results explorer design and QA plan

## Skill application

Read the local Anthropic frontend-design skill at `/home/y/.claude/plugins/marketplaces/claude-plugins-official/plugins/frontend-design/skills/frontend-design/SKILL.md`. Impeccable is not installed locally; read the official [skill](https://github.com/pbakaus/impeccable/blob/main/plugin/skills/impeccable/SKILL.md), new-work, init, Operate and craft-floor guidance. Its context launcher is unavailable; project context comes directly from the explicit user brief and retained research records. Apply its Operate-mode precision, accessibility and rendered review to this requested document; no plugin was installed or persistent workflow approval inferred.

## Direction before implementation

Operate/Read: a scientist comparing endpoints, not a marketing landing page. Use a compact analysis workspace with a graph above a conclusion matrix and inline evidence disclosure. The signature interaction is changing the percentile and seeing the same forks change ordering, with a paired-ratio reference line at one. All conclusions stay available in the matrix at once.

Palette: paper `#f5f7fb`, surface `#ffffff`, ink `#182c43`, muted ink `#506179`, Chronicle `#0369a1`, Caffeine `#b91c1c`; borrow the backend colors from the existing research figures. Purple `#6d28d9` denotes paired ratios. Use a familiar sans family, tabular numerals for measurements, a restrained 14/16/20/30 px scale, generous section separation, compact table rows and visible keyboard focus. Avoid metric-card scaffolding and decorative motion. All plotting is local SVG; no external fonts, scripts or images.

```text
TailCache                                        Export visible table
Results explorer / short interpretation
Dataset filters / percentile switch
Graph focus and actual context
Latency vs ballast              Paired ratio vs ballast
Observed crossover statement / cohort boundaries
Conclusion matrix: p99 | p99.9 | p99.99 / inspect each point
Inline paired evidence and warnings
Methods, source hashes and scope
```

Review against the brief: avoid making the graph's selected point or the default primary endpoints conceal the rest of the dataset. Keep all three percentile conclusions visible, offer all timing channels, and identify duplicate pressure points by batch/window/contract. A mixed point is mixed; a baseline advantage is not called a crossover. Draw connections only within matching runtime, window, payload, regime and ownership contract. Reuse always uses its own paired Caffeine controls.

## QA inventory before implementation

- Coverage: 132 forks; 22 primary configuration comparisons; all three nonempty timing channels available; every comparison exposes p99/p99.9/p99.99 and three paired ratios. Verify exact group and pair coverage against retained JSON.
- Filtering: payload, channel scope, contract, duration, runtime and text search; reset; graph focus updates within the visible cohort. Test both directions and a combination with no results.
- Graphs: percentile changes, latency scale, runtime-separated connections, all fork points and pair ratios, reference line at one, tooltips by mouse/focus, click/keyboard point inspection, pressure zoom/reset. Check a real forward bracket, reverse bracket, baseline advantage and mixed result.
- Table: sortable pressure/payload, all percentile conclusions, warning counts, inline expansion/collapse, CSV export with visible rows. Verify own paired controls in getUsing views.
- Scientific limits: no points dropped for warnings, no pooled distributions, no percentile floor subtraction, no fabricated exact threshold or significance claim. Check tail counts and source links.
- Visual: desktop initial view and dense expanded state, mobile layout and table scrolling, keyboard focus, reduced motion, contrast and page overflow. Every filter has a visible label. User input cannot inject markup.
- Exploratory cases: impossible filter intersection and hostile-looking search text; duplicate ballast across durations/builds; one-point reuse plot has no crossover claim.

## Validation outcome

Seven evidence tests pass: complete fork/channel coverage; agreement of all primary ratios with the retained independent analysis; the baseline percentile reversal; correct Caffeine controls for reuse; mixed/tied pair handling; source immutability; and recovery of identical input without local evidence archives.

The browser review covered the actual forward 4 KiB response bracket, reverse 256 B service bracket, p99.99 baseline advantage, mixed midpoint, and a one-point reuse view. Filters, all-channel scope, search, reset, both sorting controls, percentile switches, log/linear latency, valid and invalid zoom, graph-to-table inspection, table-to-graph focus, keyboard tooltip/inspection and expansion/collapse were exercised. A hostile-looking search and an impossible duration/build intersection produce useful empty states and disable export.

The browser CSV download was checked against four filtered 30 s response points, including the baseline p99.9/p99.99 reversal. The full source dataset downloaded from the page matches the retained source hash. Embedded audit/review/data strings are individually hashed. No external scripts or styles are loaded. Browser console checks returned no errors or warnings.

Desktop and 390/320 px rendering were reviewed. Fixed-size SVG text was replaced by container-sized viewBoxes, small ratios retain nonzero precision, phone filters collapse, and the main table scrolls horizontally. Expanded evidence stays anchored within that table's visible viewport; its own metric table can scroll separately. Actual mobile scrolling moved the main table from692 to289 px. At320 px, page scroll width equalled client width; chart viewBoxes matched their251 px containers. Viewport overrides were reset after QA. The final tab remains open as the deliverable.

All checks use retained data only. Historical archives, original acceptance records and AGY work are unchanged. This is a viewing and interpretation layer, not new experimental evidence or a qualification campaign.

## p99.999 / definitions extension: plan and QA scope

Preserve the established visual system and all prior endpoints. Add a fourth percentile switch and conclusion column, updating counts, expansion span and CSV fields. Use a two-by-two percentile selector at phone widths. A collapsible glossary near the introduction explains each term before the reader needs it; the top Definitions link opens it. Include a concrete waiting/service/response example.

Validate the added endpoint against independently decoded raw HDRs, then verify the 4 KiB p99.99→p99.999 service reversal, 256 B 448–480 MiB forward bracket, response baseline advantage, 56-channel/224-conclusion coverage, finite-tail counts, CSV/source downloads, glossary opening/closing and phone layout. Check prior p99/p99.9 conclusions remain intact. Stage only index.html and static Vercel configuration; verify the deployed page against its local SHA-256 and exercise its percentile switch.

Extension verification passed: 226 Python tests; 504 directly decoded HDR histograms; 1,680 percentile checks; all 132 old records unchanged except appended endpoint/support; all 66 primary collector ratios agree. Browser checks confirmed both new service findings, unchanged p99.9 response bracket, 56/224 all-channel coverage, per-fork support, exact four-row/24-column CSV and exact source download hash. Desktop glossary/graphs and 320 px controls were visually reviewed without horizontal page overflow; no console errors or warnings were observed. A transient preview server interruption was recovered before checking the final downloads. Viewport override was reset. Vercel project creation remains pending explicit team confirmation because automatic approval review rejected the inferred target.
