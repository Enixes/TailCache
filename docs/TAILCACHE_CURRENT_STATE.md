# TailCache current research and manuscript state

**Updated 18 November 2026.** The new [mechanism study](mechanism/README.md) is collected and audited: **64 research JVMs /32 paired comparisons**, plus three functional JVMs and six separate controls. The protocol, source-matched qualification, per-cohort reviews, portable/model checks and all-point table are retained. Operational delivery is recorded separately in [mechanism status](TAILCACHE_MECHANISM_STATUS.json).

New [portable collection tooling](PORTABLE_EXPERIMENT.md) supports fresh host
replications without the old build folders or systemd. Its diagnostic validation is
separate from research observations; no new research campaign is implied by building
the bundle. The explicit processor-budget and host-monitoring protocol is versioned
separately from historical acceptance rules.

The strongest finding is a **response ranking reversal from update locality at matched fresh-write allocation demand**. At5% writes and 4 KiB values, concentrating updates on 2048 keys favors Caffeine in 4/4 pairs; distributing them over 32768 keys favors Chronicle in 4/4. Both seeds repeat with reversed backend order, and Caffeine GC exposure falls 82–85%. This bundles survival, locality and policy traffic; it does not prove an isolated promotion mechanism. Larger heap lowers Caffeine total GC exposure but worsens its response p99.9 at 5% writes in both seeds. The 90-second transition cohorts favor Chronicle, while a new warning-free 30-second pair favors Caffeine at 0.5%; different seeds/time prevent isolating a duration effect. No universal boundary follows.

Forty-two forks have warnings; collector failures and contrary results remain. Frozen models improve descriptive numerical error but call21/22 calibrated transport pair directions, compared with 22/22 for lower-total-GC. [Results/tables](mechanism/RESULTS.md), [figures](mechanism/FIGURES.md), [sequential reviews](mechanism/COHORT_REVIEWS.md), [final review](mechanism/REVIEW.md) and [portable reproduction](mechanism/README.md) are the current entry points. The [deep re-review](mechanism/REREVIEW_20261118.md) adds fail-closed artifact validation and clarifies warning coverage and duration confounding. No further same-host matrix is queued for this completed bounded scope.

The earlier [continuous-stream predictor study](predictor/RESULTS.md) remains separate:18 qualification,30 primary and 12 fresh research forks. It established0%/5% response endpoint directions but fresh0.5% disagreement. Both boundary forecasts failed; all original outcomes and conservative qualification remain. Historical occupancy halves sampled different G1-cycle phases, so failed qualification is not proof every fork was still warming. The actual order imbalance and measured evacuation failures are now disclosed in the manuscript.

[All documentation](DOCUMENTATION_INDEX.md) preserves earlier dated scopes. The 17 November results below remain unchanged. No additional benchmark is planned for the completed bounded predictor scope.

| Question / metric | Current conclusion | Limit |
| --- | --- | --- |
| RQ1: ordinary-service p99/p99.9 | No robust forward pressure crossover established. Small-value baseline wins depend on policy/harness; 4/8 KiB do not improve toward Chronicle in the tested cells. | Tested configurations only; original unconditional Task 12 stays NO_GO. |
| RQ2: payload effect | Same-pressure service cells change ordering with payload. New single-seed256 B response screen favors Chronicle already at 0%/5%;4 KiB reverses with writes. Earlier long-trace comparisons remain separate. | No shared stable crossover threshold or measured movement of one. |
| Update-locality response test | Winner reverses between2048/32768 eligible update keys at fixed 5% writes; both seeds/reversed-order repeats agree. | Two seeds, one host; locality/survival/policy bundled. |
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
- [Offline explorer](TAILCACHE_RESULTS_EXPLORER.html#mechanism-followup), [protected hosted explorer](https://tailcache-results.vercel.app/#mechanism-followup), [deployment receipt](interactive/deployment.json).
- Branch `codex/tailcache-preprint`, [draft PR #10](https://github.com/Enixes/TailCache/pull/10), stacked on [research PR #9](https://github.com/Enixes/TailCache/pull/9).

## Remaining before publication

Independent domain/contribution feedback, author revision, final figure selection/typesetting/citation audit, selected raw-evidence off-host backup/public release and licensing, author names/affiliations/contributions/disclosure, and an author-approved deposit. No formal submission or deposit has occurred. A successful build/data audit is not independent performance replication. Browser/deployment checks and operational completion are recorded in the dated final review and status, not inferred from a launched command.

Application deadline supplied: **1 December**; earlier planned citable-release target **26 November**, subject to author approval and repository processing. These are planning dates, not acceptance claims.

## Preserved earlier evidence

[Original acceptance](TAILCACHE_12_FINAL_ACCEPTANCE.json): 402 attempted invocations, 191 conditionally usable campaign forks and one hard rejection; unconditional NO_GO remains. [Focused exploration](TAILCACHE_FOCUSED_RESULTS.md): 132 workload JVMs; [10 November midpoint](TAILCACHE_MIDPOINT_RESULTS.md): 30 additional workload JVMs. [15 November review](preprint/DEEP_REVIEW_20261115.md) and [16 November re-review](preprint/RE_REVIEW_20261116.md) apply to those earlier scopes. Raw archives remain git-ignored on the collection host. Dated plans and collection states retain their original wording; they do not override this current entry point.
