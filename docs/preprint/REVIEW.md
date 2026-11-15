# Preprint preparation review

## Current review — 15 November 2026

See [the deep-review findings and corrections](DEEP_REVIEW_20261115.md), [current executed checks](review-verification-20261115.json) and [source-to-export audit](source-audit-20261115.json). The 11 November assessment below is retained as history, not as the current test count.

The review found and fixed false success for missing histogram coverage, an empty-comparison winner, assertion-dependent validation, omitted offered-rate pairing, and insufficient count/rate/protocol validation. It also tightened service/drain semantics and the payload inference, added the original campaign summary, pinned HDR implementation semantics, completed discussion/conclusion prose and disabled survival-path simplification. The headline observations did not change. Independent human review, final author approval, raw-artifact release/backup and clean Java harness reproduction remain open.

## Initial review — 11 November 2026

11 November 2026. **Agent implementation and research-method review; not independent human peer review.**

## Outcome

The bounded paper-preparation unit is complete: claim map, seven static figures with full captions, selected derived evidence, offline renderer, initial manuscript prose and verified reference list. No benchmark was launched, no gate changed, no historical evidence overwritten and no manuscript submitted/published. This does not complete Tasks 14–17 or qualify the original unconditional protocol.

## Research review and corrections

| Concern | Resolution / remaining limit |
| --- | --- |
| Earlier notes implied that the planned midpoint was still unlaunched. | Added dated completion updates to the preprint plan, deferred list and historical focused/claim notes. Kept the prospective text identifiable as history. |
| “Service crossover unsupported” could hide the p99.999 result. | Claims distinguish no forward p99/p99.9/p99.99 service crossover from Chronicle's already-present high-pressure p99.999 service advantage. Neither supplies a precise forward service bracket. |
| A median at 104 MiB could conceal a contrary pair. | Show all primary paired ratios, clean coverage and both additional seeds separately. Further bisection remains skipped under the original adaptive rule. |
| Reuse data might be presented as a matched three-arm comparison. | Inspecting retained identities showed no contemporaneous ordinary-Chronicle arm in the reuse batches. Figure 7 uses only the actual Caffeine/getUsing paired response observations. It does not claim a matched ordinary-get-to-reuse causal improvement. |
| Heap relief might be called total memory savings. | Figure 4 places heap and sampled RSS side by side, with worker allocation/GC evidence. Equal-total-memory conclusions remain unsupported. |
| Extreme quantiles might be treated as independent pause evidence. | Captions and methods retain per-fork operation counts, approximately 15 nominal tail responses at p99.999, response correlation and the lack of event-level attribution. |
| Original failed qualification might disappear under fresh data. | Original conditional acceptance, one hard rejection and stopping-policy amendment remain explicit in methods/claims. New evidence does not repair old rejected cells. |
| Literature might overclaim novelty. | Verified primary records for eight cited sources, including the closest Caffeine/OHC practitioner comparison. Limited reading scope is documented; full citation chaining and human novelty assessment remain open. |

The original 30-JVM cliff diagnostic remains discovery evidence. Neither its single-fork service observations nor synthetic correction establish a universal G1 threshold or replace the later service/scheduled-response measurements. No claim that reuse is universally required or another language guarantees hard tail SLAs enters the paper.

## Verification

- Export includes all 132 historical focused forks and all 30 fresh forks, with explicit dataset, batch, runtime, seed, workload and contract identity. It preserves all five fresh compiler-warning forks.
- Recomputed all four requested quantiles from each of the 18 exported primary response distributions: 72 exact endpoint checks and matching counts. This is a selected derived-data check, not a rerun of the previous raw-evidence audit.
- Verified all primary response directions, clean-pair coverage, fresh extreme-response ordering, historical 4 KiB service ordering at five points, and the opposite historical 256 B endpoint directions.
- Six targeted tests reject duplicate/incomplete pairs, cross-cohort pairing, corrupt histogram counts, hidden midpoint changes and erased warnings; the frozen real-data check passes.
- Seven figures are available as PDF, SVG and PNG. Inspected the rendered figures; shortened long resource-axis labels. No fork pooling, curve smoothing, outlier removal or confidence-interval fabrication.
- Package contains per-fork endpoint CSV and all 270 fresh channel/threshold rows. Histogram-resolution intervals and zero observations are labelled correctly.
- Bibliography keys and local links are checked. The eight citations have corresponding BibTeX entries; metadata not verified is omitted rather than guessed.
- The original input hash map and render manifest allow source/data identity checks. Full raw archives remain retained and git-ignored; public archival availability is not claimed.

See [verification.json](verification.json) for executed receipt counts, original-input preservation and isolated offline regeneration results. See [data-audit.json](data-audit.json) for numerical guardrails and [render-manifest.json](render-manifest.json) for the generated figure hashes.

## Remaining before author-approved release

1. Complete/refine the 8–10-page manuscript, original-campaign outcome summary and final figure layout. This Markdown draft is not yet a typeset preprint.
2. Obtain substantive independent human feedback on contribution, method and threats if possible. Do not label this agent review as human peer review.
3. Complete clean harness build/smoke reproduction, selected raw-evidence release and off-host backup; agree code/data/manuscript licensing.
4. Audit every final number, caption and primary citation after prose/layout edits; review novelty beyond this bounded verification pass.
5. Confirm author names, affiliations, contributions, acknowledgements and tool-use disclosure with the authors; publish only the approved package.

No extra benchmark is required for these drafting tasks. A matched small-payload response study, different offered loads, equal-total-memory intervention, independent recorder study or second host would be a separately planned extension, not a hidden prerequisite for this scoped v1.
