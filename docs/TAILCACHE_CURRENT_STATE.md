# TailCache current research and manuscript state

**Updated 18 November 2026.** The [continuous-stream predictor study](predictor/RESULTS.md) is fully collected/audited:18 qualification,30 primary and12 fresh secondary research forks. Four controls, three functional JVMs and one compiler diagnostic are counted separately. Source/runtime, raw histograms, GC/RSS, stream continuity and portable/model checks pass; failed steady-state qualification and warnings remain. [Operational status](TAILCACHE_PREDICTOR_STATUS.json) records delivery/recovery completion separately.

The new scheduled-response p99.9 result reverses from Caffeine at 0% writes to Chronicle at 5% in both holdouts. All primary 0.5% pairs favor Chronicle, but fresh 0.5% is mixed. Original and updated boundary forecasts therefore fail; no exact transition is established. M1/M2 conditional winner accuracy ties the simple total-GC rule. M2 improves aggregate numerical error, yet a constant pilot quantile is better for Chronicle alone. [Results/tables](predictor/RESULTS.md), [figures](predictor/FIGURES.md), [review](predictor/REVIEW.md) and [portable reproduction](predictor/README.md) are the current entry points.

[All documentation](DOCUMENTATION_INDEX.md) preserves earlier dated scopes. The17 November results below remain unchanged. No additional benchmark is planned for the completed bounded predictor scope.

| Question / metric | Current conclusion | Limit |
| --- | --- | --- |
| RQ1: ordinary-service p99/p99.9 | No robust forward pressure crossover established. Small-value baseline wins depend on policy/harness; 4/8 KiB do not improve toward Chronicle in the tested cells. | Tested configurations only; original unconditional Task 12 stays NO_GO. |
| RQ2: payload effect | Same-pressure service cells change ordering with payload. Matched 256 B/4 KiB paced response favors Chronicle already at baseline in the long-trace regime. | No shared stable crossover threshold or measured movement of one. |
| Earlier scheduled-response p99.9 | Short-trace 4 KiB reversal at 0 versus 208 MiB repeats; 104 MiB mixed. | Equal-array logical-pattern control reverses baseline ordering. The bracket is scope-specific. |
| Extreme tails / GC | Tail curves and stall rates expose effects a single percentile misses. GC wall-time fraction can greatly exceed affected-operation fraction. | Rare-event support and one-pair discovery cells limit threshold inference. |
| Memory / reuse | Earlier Chronicle heap relief coexists with higher sampled RSS. getUsing remains a separate contract. | Neither total-memory savings nor a matched three-arm reuse comparison established. |

## Preserved17 November extension and artifact

- [17 November results](service-followup/RESULTS_20261117.md), [all 58 point groups](service-followup/followup-data-20261117.md), [all channel/percentile conclusions](service-followup/point-conclusions-20261117.csv), [new claim map](service-followup/CLAIMS_20261117.md).
- 184 research JVMs across eight cohorts, plus 30 controls. All raw-integrity checks pass; 138 research forks have no recorded warning, 46 remain warning-bearing. No pooling across observers, seeds, policies or stages.
- [Portable verification](service-followup/portable-verification-20261117.json): 704 distributions, 3,520 quantiles, count/union/threshold/ratio checks. [Seven new figures](service-followup/FIGURES_20261117.md); clean-directory reproduction matches 14 outputs. [Fresh JAR-only source compile/API check](service-followup/clean-source-check-20261117.json) passes.
- [Final technical review](service-followup/FINAL_REVIEW_20261117.md), agent-assisted, not independent human peer review. The original frozen preprint dataset and historical evidence remain unchanged.

## Manuscript and explorer

- [Revised working manuscript](preprint/MANUSCRIPT.md), [original 14 claims](preprint/CLAIMS.md), [original seven figures](preprint/FIGURES.md), [new supplementary figures](service-followup/FIGURES_20261117.md).
- [Offline explorer](TAILCACHE_RESULTS_EXPLORER.html#predictor-followup), [protected hosted explorer](https://tailcache-results.vercel.app/#predictor-followup), [deployment receipt](interactive/deployment.json).
- Branch `codex/tailcache-preprint`, [draft PR #10](https://github.com/Enixes/TailCache/pull/10), stacked on [research PR #9](https://github.com/Enixes/TailCache/pull/9).

## Remaining before publication

Independent domain/contribution feedback, author revision, final figure selection/typesetting/citation audit, selected raw-evidence off-host backup/public release and licensing, author names/affiliations/contributions/disclosure, and an author-approved deposit. No formal submission or deposit has occurred. A successful build/data audit is not independent performance replication. Browser/deployment checks and operational completion are recorded in the dated final review and status, not inferred from a launched command.

Application deadline supplied: **1 December**; earlier planned citable-release target **26 November**, subject to author approval and repository processing. These are planning dates, not acceptance claims.

## Preserved earlier evidence

[Original acceptance](TAILCACHE_12_FINAL_ACCEPTANCE.json): 402 attempted invocations, 191 conditionally usable campaign forks and one hard rejection; unconditional NO_GO remains. [Focused exploration](TAILCACHE_FOCUSED_RESULTS.md): 132 workload JVMs; [10 November midpoint](TAILCACHE_MIDPOINT_RESULTS.md): 30 additional workload JVMs. [15 November review](preprint/DEEP_REVIEW_20261115.md) and [16 November re-review](preprint/RE_REVIEW_20261116.md) apply to those earlier scopes. Raw archives remain git-ignored on the collection host. Dated plans and collection states retain their original wording; they do not override this current entry point.
