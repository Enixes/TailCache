# TailCache preprint working package

The 22 November draft integrates the two-host update-locality replication and
the second-host pressure and write-rate studies. The [manuscript](MANUSCRIPT.md),
[claims](CLAIMS.md), and [figure data](locality-pairs.csv) form the current review
package. The [18 November manuscript](https://github.com/Enixes/TailCache/blob/5772fb212692244a29b6ab61d416340db600f0c8/docs/preprint/MANUSCRIPT.md)
preserves the expanded account of earlier experiments. The paper remains a
working draft for author review.

## Review PDF

[Download the review draft](../../output/pdf/tailcache-preprint-review.pdf).
The PDF and first figure are rendered from the Markdown manuscript and
`locality-pairs.csv` with Python 3.10+ and ReportLab 4.4.9.

```sh
python3 scripts/render_tailcache_preprint.py --update-svg
```

Before deposit, obtain a systems review of the contribution and measurement
boundaries, confirm author names, affiliations, contributions and disclosure,
then review the license and public access for the selected artifacts. The
review PDF still needs author approval and final release metadata.

## Follow-up: paced response at 10% writes

Test whether the scheduled-response p99.9 locality reversal survives at a
higher write fraction. Cross 5% and 10% nominal writes with 2,048 and 32,768
eligible update keys. Keep 4 KiB values, 32,768 residents, uniform reads,
50,000 intended arrivals/s, zero ballast, G1, a 512 MiB heap, and the same
offered churn. A matched design with three fresh seed pairs per cell would
use 24 research JVMs. Freeze the protocol, qualifications and retry cap before
any collection. Pair both backends within each seed and balance backend order.

At 10%, the offered workload doubles to about 5,000 fresh writes/s. The mean
per-key replacement interval falls from about 13.1 to 6.6 seconds in the
full-key arm. Report p99.9 response as the primary outcome alongside GC pause
time and length, operation allocation, achieved churn and tail exceptions.
Higher fresh allocation and shorter value lifetimes can pull in different
directions, so the response direction is an empirical question. This is a
follow-up and is outside the evidence needed for this draft.

## Earlier experiments and audits

Extended 17 November with [184 new research forks across eight cohorts](../service-followup/RESULTS_20261117.md), [58 point groups](../service-followup/followup-data-20261117.md), [seven supplementary figures](../service-followup/FIGURES_20261117.md), [new claims](../service-followup/CLAIMS_20261117.md) and a [final technical review](../service-followup/FINAL_REVIEW_20261117.md). The earlier package was revised 16 November after a [systems research re-review](RE_REVIEW_20261116.md) and the previous [deep source/data and methods review](DEEP_REVIEW_20261115.md). The frozen `paper-data.json` is unchanged. The new [raw reconciliation](raw-rereview-20261116.json), [original campaign rerun](original-rereview-20261116.json) and [trace inspection](trace-review-20261116.json) supplement [portable verification](review-verification-20261115.json); initial and earlier review receipts remain dated history.

The new [64-fork mechanism study](../mechanism/README.md), [all-point/model tables](../mechanism/RESULTS.md), [three figures](../mechanism/FIGURES.md) and [final review](../mechanism/REVIEW.md) add constrained-order update-set repeats, longer-window transition tests, heap headroom and matched payloads. The manuscript now discloses historical order imbalance, evacuation failures and the limited occupancy diagnostic. Original data packages remain unchanged.

The [current-state summary](../TAILCACHE_CURRENT_STATE.md) and [complete documentation index](../DOCUMENTATION_INDEX.md) guide readers through current and historical material. The [protected hosted HTML](https://tailcache-results.vercel.app/#mechanism-followup) includes this reviewed narrative, document downloads and the seven paper figures alongside the interactive evidence.

- [Manuscript draft](MANUSCRIPT.md) with methods, main results, limitations, and references.
- [Claim-to-evidence map](CLAIMS.md) and [machine-readable identities](claims.json).
- [Figures and full captions](FIGURES.md), vector PDF/SVG plus PNG in `figures/`.
- [Literature verification and novelty comparison](LITERATURE.md); [BibTeX](references.bib).
- [Researcher review and remaining work](REVIEW.md).
- [Original conditional campaign summary](ORIGINAL_CAMPAIGN.md), with all 16 comparison classifications.

## Offline figure reproduction from a clean checkout

Python 3.10+ is sufficient for verification. Figure rendering additionally requires Matplotlib. Use an isolated environment; installing dependencies is a one-time network step, not part of the offline analysis. A previously prepared environment needs no network access.

```sh
rtk proxy python3 -m venv /tmp/tailcache-paper-venv
rtk proxy /tmp/tailcache-paper-venv/bin/python -m pip install -r docs/preprint/requirements.txt
rtk proxy /tmp/tailcache-paper-venv/bin/python scripts/tailcache12_preprint.py verify
rtk proxy /tmp/tailcache-paper-venv/bin/python scripts/tailcache12_preprint.py render
rtk proxy /tmp/tailcache-paper-venv/bin/python -m unittest discover -s scripts -p test_tailcache12_preprint.py
```

Run from the repository root. `render` regenerates derived figures, CSVs, claim map and manifests under `docs/preprint/`; it does not access raw archives, Java, Vercel or benchmark processes. Rendering output hashes can vary with fonts, Matplotlib dependencies and PDF metadata; the numerical inputs and CSVs are the reproducibility contract. `MPLCONFIGDIR` defaults to `/tmp/tailcache-paper-mpl` unless explicitly set. Regenerating into a separate directory requires copying `paper-data.json` there and passing `--out <directory>`.

`paper-data.json` contains selected derived fields for all 132 historical focused forks and all 30 fresh forks, with the 18 fresh primary response histograms compressed losslessly. `fork-endpoints.csv` exports per-fork quantiles; `fresh-stall-rates.csv` exports all 270 fresh channel/threshold rows. These are derived observations, not independently collected new data, and are not a replacement for raw GC/host/JVM logs. The provenance map records the exact original input hashes and paths. `data-audit.json` documents the checks run during export; `render-manifest.json` binds generated figures to the input and renderer.

Only on the evidence host, initial export can be repeated with:

```sh
rtk proxy python3 scripts/tailcache12_preprint.py prepare
```

This checks matching audited midpoint hashes and refuses to replace a changed frozen `paper-data.json`. The revised checks are written to `data-audit-v2.json`; the initial `data-audit.json` remains a dated historical receipt. Evidence validation uses explicit exceptions and remains active under `python -O`.

On the evidence host, reconcile all exported observations/distributions and regenerate the original-campaign summary separately:

```sh
rtk proxy python3 scripts/tailcache12_preprint_source_audit.py
```

This host-only audit requires the retained source files; portable verification and figure regeneration do not. Its receipt is `source-audit-20261115.json`. A missing raw archive on another machine does not invalidate successful portable figure regeneration, but it limits independent raw-evidence verification. The full raw archives remain git-ignored. The later second-host replication has a separate versioned raw archive. Public artifact selection and licensing review remain release work. A JAR-only fresh-source build/API check and portable figure reproduction for the new extension now pass; these do not replace off-host raw backup. No raw-evidence deposit or formal preprint publication is performed by these commands.

## Paper boundary

In the earlier short-trace cohort, the ordinary 4 KiB scheduled-response p99.9 direction change repeats between 0 and 208 MiB; 104 MiB is mixed. Extreme-response advantages already exist at baseline. Historical saturated service and API-reuse sensitivities remain separate. The original unconditional protocol stays unqualified. Three matching paired directions are descriptive replication, not a significance test. None of this establishes a universal threshold, causal GC attribution or a production SLA.

## Reproduce the 17 November extension

The new portable package is separate from frozen `paper-data.json`. No Java process or raw archive is needed for its analysis:

```sh
rtk proxy python3 scripts/tailcache12_service_verify.py docs/service-followup/followup-data-20261117.json
rtk proxy /tmp/tailcache-paper-venv/bin/python scripts/tailcache12_service_figures.py
rtk proxy python3 -m unittest discover -s scripts -p test_tailcache12_service_verify.py
```

Use an isolated Matplotlib environment with [the pinned render requirements](../service-followup/render-requirements-20261117.txt); the `/tmp` environment is a local convenience, not a committed dependency. [Clean-directory reproduction](../service-followup/clean-analysis-reproduction-20261117.json) records matching SVG/PNG hashes. Full source/protocol/runtime/audit identities accompany each cohort. Collection states are frozen historical evidence; the separate dated acceptance/review determines analysis completion.

## Reproduce the 18 November predictor extension

The [current predictor report](../predictor/RESULTS.md), [research review](../predictor/REVIEW.md) and [portable commands](../predictor/README.md) add60 separately identified research forks. The draft now includes failed boundary forecasts, fresh 0.5% disagreement, GC-conditioned model errors and naive comparisons. Earlier data packages and claim maps keep their dated scope. The new working manuscript has not been author-approved or deposited.

## Reproduce the 18 November mechanism extension

Use the separate [portable commands](../mechanism/README.md). They verify all 64 forks/32 pairs, full tails, strict stall-rate bounds and frozen conditional models. New claims and their limits are audited in [the mechanism review](../mechanism/REVIEW.md); the older claim maps retain their dated scope. No new paper submission or author approval is implied.

The subsequent [deep mechanism re-review](../mechanism/REREVIEW_20261118.md) hardens incomplete-export checks, pins replay source identity, and distinguishes warning-inclusive replication from clean-host confirmation. Measurement data remain unchanged.
