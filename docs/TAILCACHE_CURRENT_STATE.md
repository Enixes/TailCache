# TailCache current research and manuscript state

**Updated 17 November 2026.** [All documentation](DOCUMENTATION_INDEX.md) separates active entry points from immutable dated records. The worth-first extension is collected and audited; no benchmark remains to run in this bounded scope.

| Question / metric | Current conclusion | Limit |
| --- | --- | --- |
| RQ1: ordinary-service p99/p99.9 | No robust forward pressure crossover established. Small-value baseline wins depend on policy/harness; 4/8 KiB do not improve toward Chronicle in the tested cells. | Tested configurations only; original unconditional Task 12 stays NO_GO. |
| RQ2: payload effect | Same-pressure service cells change ordering with payload. Matched 256 B/4 KiB paced response favors Chronicle already at baseline in the long-trace regime. | No shared stable crossover threshold or measured movement of one. |
| Earlier scheduled-response p99.9 | Short-trace 4 KiB reversal at 0 versus 208 MiB repeats; 104 MiB mixed. | Equal-array logical-pattern control reverses baseline ordering. The bracket is scope-specific. |
| Extreme tails / GC | Tail curves and stall rates expose effects a single percentile misses. GC wall-time fraction can greatly exceed affected-operation fraction. | Rare-event support and one-pair discovery cells limit threshold inference. |
| Memory / reuse | Earlier Chronicle heap relief coexists with higher sampled RSS. getUsing remains a separate contract. | Neither total-memory savings nor a matched three-arm reuse comparison established. |

## Completed extension and artifact

- [17 November results](service-followup/RESULTS_20261117.md), [all 58 point groups](service-followup/followup-data-20261117.md), [all channel/percentile conclusions](service-followup/point-conclusions-20261117.csv), [new claim map](service-followup/CLAIMS_20261117.md).
- 184 research JVMs across eight cohorts, plus 30 controls. All raw-integrity checks pass; 138 research forks have no recorded warning, 46 remain warning-bearing. No pooling across observers, seeds, policies or stages.
- [Portable verification](service-followup/portable-verification-20261117.json): 704 distributions, 3,520 quantiles, count/union/threshold/ratio checks. [Seven new figures](service-followup/FIGURES_20261117.md); clean-directory reproduction matches 14 outputs. [Fresh JAR-only source compile/API check](service-followup/clean-source-check-20261117.json) passes.
- [Final technical review](service-followup/FINAL_REVIEW_20261117.md), agent-assisted, not independent human peer review. The original frozen preprint dataset and historical evidence remain unchanged.

## Manuscript and explorer

- [Revised working manuscript](preprint/MANUSCRIPT.md), [original 14 claims](preprint/CLAIMS.md), [original seven figures](preprint/FIGURES.md), [new supplementary figures](service-followup/FIGURES_20261117.md).
- [Offline explorer](TAILCACHE_RESULTS_EXPLORER.html#service-followup), [protected hosted explorer](https://tailcache-results.vercel.app/#service-followup), [deployment receipt](interactive/deployment.json).
- Branch `codex/tailcache-preprint`, [draft PR #10](https://github.com/Enixes/TailCache/pull/10), stacked on [research PR #9](https://github.com/Enixes/TailCache/pull/9).

## Remaining before publication

Independent domain/contribution feedback, author revision, final figure selection/typesetting/citation audit, selected raw-evidence off-host backup/public release and licensing, author names/affiliations/contributions/disclosure, and an author-approved deposit. No formal submission or deposit has occurred. A successful build/data audit is not independent performance replication. Browser/deployment checks and operational completion are recorded in the dated final review and status, not inferred from a launched command.

Application deadline supplied: **1 December**; earlier planned citable-release target **26 November**, subject to author approval and repository processing. These are planning dates, not acceptance claims.

## Preserved earlier evidence

[Original acceptance](TAILCACHE_12_FINAL_ACCEPTANCE.json): 402 attempted invocations, 191 conditionally usable campaign forks and one hard rejection; unconditional NO_GO remains. [Focused exploration](TAILCACHE_FOCUSED_RESULTS.md): 132 workload JVMs; [10 November midpoint](TAILCACHE_MIDPOINT_RESULTS.md): 30 additional workload JVMs. [15 November review](preprint/DEEP_REVIEW_20261115.md) and [16 November re-review](preprint/RE_REVIEW_20261116.md) apply to those earlier scopes. Raw archives remain git-ignored on the collection host. Dated plans and collection states retain their original wording; they do not override this current entry point.
