# TailCache preprint working package

Prepared 11 November 2026. **Working material, not an author-approved or submitted preprint.**

Revised 15 November after a [deep source/data and methods review](DEEP_REVIEW_20261115.md). The frozen `paper-data.json` is unchanged. Use [review-verification-20261115.json](review-verification-20261115.json) for the current validation receipt; `verification.json` and `data-audit.json` preserve the initial 11 November checks.

- [Manuscript draft](MANUSCRIPT.md): methods and related work, initial results narrative and explicit remaining edits.
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

This host-only audit requires the retained source files; portable verification and figure regeneration do not. Its receipt is `source-audit-20261115.json`. A missing raw archive on another machine does not invalidate successful portable figure regeneration, but it limits independent raw-evidence verification. The full raw archives remain git-ignored. Their off-host backup/public artifact, a clean harness build/smoke reproduction, and licensing review remain Task 15 work. No raw-evidence deposit or formal preprint publication is performed by these commands.

## Paper boundary

The ordinary 4 KiB scheduled-response p99.9 direction change repeats between 0 and 208 MiB; 104 MiB is mixed. Extreme-response advantages already exist at baseline. Historical saturated service and API-reuse sensitivities remain separate. The original unconditional protocol stays unqualified. Three matching paired directions are descriptive replication, not a significance test. None of this establishes a universal threshold, causal GC attribution or a production SLA.
