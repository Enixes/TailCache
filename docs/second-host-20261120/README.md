# Second-host portable replication results (20 November 2026)

This directory packages the verified derived reports, percentile tables, point
conclusions, compact machine-readable results, and provenance manifest from all
TailCache portable campaigns run on the second Linux host on 20 November 2026.

## Host and runtime profile

- **OS:** Pop!_OS 24.04 LTS (`Linux-7.2.15-76070215-generic-x86_64-with-glibc2.39`)
- **Hardware:** AMD Ryzen 7 5800X (8 cores / 16 logical CPUs), 31.29 GiB RAM
- **JVM:** Eclipse Adoptium Temurin `21.0.13+9-LTS`, G1GC, frozen 512 MiB heap (`-Xms512m -Xmx512m`), 12-CPU JVM processor budget (`-XX:ActiveProcessorCount=12`), async GC logging, zero priming calls
- **Python:** 3.12.3
- **Provenance manifest:** [`MANIFEST.json`](MANIFEST.json)

All second-host cohorts are kept separate from the earlier first-host mechanism,
predictor, and service-extension cohorts. No distributions or quantiles are
pooled across hosts, seeds, or forks.

## Cohort inventory

Across four local result directories, the second host completed **252 primary
research JVMs (126 paired comparisons)** plus **2 bounded external-noise retry
JVMs (1 retry pair)**, alongside diagnostic smoke runs, a 4-JVM saturated
observer pilot, and per-suite timing controls.

| Campaign / suite | Source commit | Role | Scheduled / completed JVMs | Usable pairs | First-pass clean pairs | Clean sensitivity pairs | Primary reports |
|---|---|---|---:|---:|---:|---:|---|
| `smoke` | `8637d55` | Diagnostic smoke | 4 / 4 | 2 / 2 | 0 | — | [Summary](smoke/SUMMARY.md) · [Results](smoke/smoke/RESULTS.md) |
| `locality` | `8637d55` | 30 s update-locality replication | 8 / 8 | 4 / 4 | 3 | — | [Review](locality/CROSS_HOST_REVIEW.md) · [Results](locality/research/RESULTS.md) |
| `followups-01 / write-ratio` | `ae686f2` | 30 s write-rate sweep (0–5%) | 20 / 20 | 10 / 10 | 6 | — | [Review](followups-01/CAMPAIGN_REVIEW.md) · [Results](followups-01/write-ratio/research/RESULTS.md) |
| `followups-01 / locality-long` | `ae686f2` | 90 s 4-seed locality confirmation | 16 / 16 | 8 / 8 | 6 | — | [Interpretation](followups-01/INTERPRETATION.md) · [Results](followups-01/locality-long/research/RESULTS.md) |
| `followups-01 / rq-matrix` | `ae686f2` | 4-ballast × 2-payload × 2-mode matrix | 64 / 64 | 32 / 32 | 15 | — | [Review](followups-01/CAMPAIGN_REVIEW.md) · [Results](followups-01/rq-matrix/research/RESULTS.md) |
| `pressure-write-02 / preflight` | `021cfa2` | Diagnostic preflight (tightened observer) | 4 / 4 | 2 / 2 | 0 | — | [Summary](pressure-write-02/preflight/SUMMARY.md) · [Results](pressure-write-02/preflight/smoke/RESULTS.md) |
| `pressure-write-02 / saturated-pilot` | `021cfa2` | 4-JVM saturated observer validation | 4 / 4 | 2 / 2 | 2 | — | [Results](pressure-write-02/saturated-pilot/RESULTS.md) · [Observer log](pressure-write-02/observer-qualification.log) |
| `pressure-write-02 / saturated-write-pressure` | `021cfa2` | 256 B / 4 KiB × 0 / 288 MiB × 1 / 5 / 10% writes (saturated) | 96 / 96 (+2 retry) | 48 / 48 | 36 | 37 | [Review](pressure-write-02/CAMPAIGN_REVIEW.md) · [Results](pressure-write-02/saturated-write-pressure/research/RESULTS.md) |
| `pressure-write-02 / write-transition` | `021cfa2` | 4-seed 0.5–2% write transition (50k req/s) | 48 / 48 | 24 / 24 | 19 | 19 | [Review](pressure-write-02/CAMPAIGN_REVIEW.md) · [Results](pressure-write-02/write-transition/research/RESULTS.md) |

## Bounded scientific findings on the second host

Ratios below are `Chronicle / Caffeine` (values below 1 favor Chronicle).

1. **Update-locality scheduled-response reversal replicates on independent hardware.**
   At 4 KiB, 5% writes, zero ballast, and 50,000 intended arrivals/s, Caffeine led
   scheduled-response p99.9 with 2,048 eligible update keys while Chronicle led
   with 32,768 keys in both the 30-second replication (`locality`: 4/4 pairs, 3/4
   warning-free; ratios 1.186–1.417 vs 0.002165–0.002416) and the 90-second
   four-seed confirmation (`locality-long`: 8/8 pairs, 6/8 warning-free; ratios
   1.122–1.502 vs 0.002398–0.00321). At p99.99 and p99.999, `locality-long`
   favored Chronicle in 3/4 seeds in each arm; both contrary Chronicle forks were
   warning-free and exhibited unresolved completion gaps of 18.783 ms and
   19.730 ms not overlapping logged GC pauses or JVM safepoints.
   See [cross-host review](locality/CROSS_HOST_REVIEW.md) and
   [follow-up interpretation](followups-01/INTERPRETATION.md).

2. **Saturated-service ranking depends on payload, with no pressure-induced p99/p99.9 reversal.**
   In `rq-matrix` (0/96/208/288 MiB, 5% writes), 11 of 16 saturated pairs carried
   final-interval outside-CPU warnings caused by the observer sampling past worker
   exit. After fixing the native Linux post-measurement observer handoff and
   tightening the whole-host CPU bound to 2% (`021cfa2`), the 96-JVM
   `saturated-write-pressure` campaign (256 B and 4 KiB × 0 and 288 MiB × 1%, 5%,
   and 10% writes, four fresh seeds) achieved 36/48 first-pass warning-free pairs
   and 37/48 in the clean sensitivity view (1 eligible pair at cell 5 / seed
   61924 retried and recovered warning-free; original retained). Chronicle led
   saturated-service p99 and p99.9 in every 256 B pair, and Caffeine led in every
   4 KiB pair, at both 0 and 288 MiB across all three write fractions. The
   conditional midpoint trigger did not fire
   ([`midpoint-decision.json`](pressure-write-02/midpoint-decision.json)). At
   4 KiB and 288 MiB ballast, all pairs at 5% and 10% writes recorded endogenous
   churn-demand drops and remain warning-inclusive.

3. **Scheduled-response write-rate transition narrows to 1.25–1.5% on this host.**
   At 4 KiB, zero ballast, and 50,000 intended arrivals/s, the initial two-seed
   `write-ratio` sweep bracketed unanimous agreement at 0.5–2% (with 1% mixed).
   The four-seed `write-transition` sweep (0.5%, 0.75%, 1%, 1.25%, 1.5%, 2%;
   19/24 warning-free pairs, 0 retries eligible) gave unanimous Caffeine wins at
   1.25% (4/4 pairs, 4/4 clean) and unanimous Chronicle wins at 1.5% (4/4 pairs,
   4/4 clean), while 0.75% and 1% were mixed. This bracket is specific to the
   tested host, runtime, seeds, and workload and does not establish a universal
   or strictly monotonic threshold.

## Verification and packaging notes

- The archive audit covers 288 first-pass slots (252 research, 32 smoke, and
  4 observer pilot), 2 external-noise retry slots, and 60 timing controls.
- The [raw evidence archive](archive/README.md) contains the histograms, GC
  logs, and run protocols used to reconstruct the reports offline. The complete
  collection directories (~865 MB under git-ignored `results/`) also remain
  on the collection host.
- Each suite directory preserves verbatim `SUMMARY.md`, `suite-results.json`,
  `RESULTS.md`, `percentiles.csv`, and `point-conclusions.json`.
- Each primary phase also includes `results-compact.json`, which preserves all
  paired comparisons, summaries, point conclusions, contrasts, retry reviews,
  timing controls, per-fork latency/host/GC summary metrics, and raw file
  hashes while omitting the large per-event `gc.pauses` and `gc.occupancySamples`
  arrays (reducing total JSON size from ~81.6 MB to ~5.7 MB raw / ~9.4 MB
  pretty-printed) and rewriting absolute local checkout paths to `<repo>/`. Each
  compact file embeds `packaging.sourceResultsSha256`, matching the unmodified
  full `results.json` recorded in `suite-results.json` and `MANIFEST.json`.
- Manuscript and current-state documents (`docs/preprint/MANUSCRIPT.md`,
  `docs/TAILCACHE_CURRENT_STATE.md`) remain unchanged on this portability branch
  so integration with `codex/tailcache-preprint` stays coordinated per
  [docs/SESSION_HANDOFF.md](../SESSION_HANDOFF.md).
