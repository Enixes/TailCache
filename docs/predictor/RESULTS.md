# Continuous-stream write-rate and pause-model results — 18 November 2026

The fixed study is complete: **18 qualification +30 primary +12 fresh secondary research JVMs**. Four controls, three functional JVMs and one compiler-only diagnostic are separate. All raw/mechanism audits pass. Warnings and the failed steady-state qualification remain; completion is not unconditional acceptance. Earlier datasets and the original Task 12 NO_GO are unchanged.

## Research conclusions

**A response reversal exists; a stable write-rate boundary was not established.** At zero application ballast, all three primary pairs favor Caffeine at 0% writes and Chronicle at 0.5–5%. The two fresh secondary pairs repeat0%/5% endpoint directions but disagree at 0.5%. The original0.5–2% before-run bracket forecast failed in the primary study. The updated0.5% replication forecast also failed (5/6 pair directions overall). Keep the contrary fresh fork, including its compiler warning. Neither warning-bearing outcome is removed.

This is **scheduled response** under fixed arrival demand, not a saturated ordinary-service crossing and not an isolated causal effect of value placement. One host, OpenJDK 21.0.13.0.3+1, G1,512MiB heap,4KiB values,32768 residents,50k intended arrivals/s, zero extra ballast and common32MiB/s churn bound the inference. No additional payload-pressure matrix is implied.

**Conditional GC information explains winner directions more reliably than an ex ante write-ratio bracket.** M1 and M2 call15/15 primary and6/6 fresh p99.9 pairs correctly, including the contrary fresh 0.5% outcome. The lower-total-pause rule also scores15/15 and6/6. Thus winner accuracy does not demonstrate superiority of the residual-pause equation over this simple baseline. Constant backend calls and abstentions are retained in the package.

**Queue-drain modeling improves aggregate numerical error, but is not uniformly better.** M2 improves median/p90 absolute p99.9 error in both primary and fresh cohorts. Its fresh Chronicle median relative error is56.9%; the constant pilot-quantile comparator is better for Chronicle (40.6%). Primary Chronicle gives65.1% versus28.1%. The successful aggregate comparison hides this backend asymmetry unless reported separately. Conditional reconstruction reads measured GC; it does not predict future pauses or provide latency guarantees.

**The experiment remains finite-window/transient-qualified.** The120-second pilot still failed the declared half-window occupancy criterion at 0.5% writes (52.64%→41.31% heap). Warning-bearing research forks:3/18 pilot,10/30 primary (nine compiler, one outside-CPU),3/12 fresh. Both fresh 0.5% pairs include a Chronicle compiler warning; Caffeine GC overlap differs (32.526 versus28.675ms), near the ideal30ms p99.9 pause budget. That association is consistent with the model, not a unique causal attribution.

The one separately instrumented compiler probe observes phase-exit deoptimization and a conditioning recompile, but no large measurement-period compiler delta. It cannot erase nine original warnings. See [compiler interpretation](COMPILER_DIAGNOSTIC.md) and [narrow extracted evidence](compiler-diagnostic-summary.json). No extra replacement or collector/skew/payload sweep was launched after the fixed confirmation.

## Paired response p99.9 results

Each range spans individual fork quantiles, never a pooled quantile or confidence interval. Cohorts remain separate.

| Cohort | Writes % | Warmup s | Pairs | Caffeine µs range | Chronicle µs range | Ch/C ratios | Direction |
| --- | ---: | ---: | ---: | --- | --- | --- | --- |
| qualification | 0 | 12 | 1 | 20.495–20.495 | 174.591–174.591 | 8.5187 | Caffeine lower |
| qualification | 0 | 60 | 1 | 18.799–18.799 | 552.447–552.447 | 29.3870 | Caffeine lower |
| qualification | 0 | 120 | 1 | 18.367–18.367 | 115.455–115.455 | 6.2860 | Caffeine lower |
| qualification | 0.5 | 12 | 1 | 456.959–456.959 | 275.711–275.711 | 0.6034 | Chronicle lower |
| qualification | 0.5 | 60 | 1 | 1830.911–1830.911 | 195.199–195.199 | 0.1066 | Chronicle lower |
| qualification | 0.5 | 120 | 1 | 724.479–724.479 | 245.887–245.887 | 0.3394 | Chronicle lower |
| qualification | 5 | 12 | 1 | 9478.143–9478.143 | 239.999–239.999 | 0.0253 | Chronicle lower |
| qualification | 5 | 60 | 1 | 8822.783–8822.783 | 260.735–260.735 | 0.0296 | Chronicle lower |
| qualification | 5 | 120 | 1 | 9232.383–9232.383 | 138.623–138.623 | 0.0150 | Chronicle lower |
| validation | 0 | 120 | 3 | 18.895–23.343 | 137.087–182.143 | 7.4584, 6.4086, 7.8029 | Caffeine lower |
| validation | 0.5 | 120 | 3 | 1090.559–2006.015 | 153.727–276.991 | 0.1410, 0.1381, 0.2394 | Chronicle lower |
| validation | 1 | 120 | 3 | 3758.079–4108.287 | 157.183–290.303 | 0.0593, 0.0383, 0.0772 | Chronicle lower |
| validation | 2 | 120 | 3 | 5115.903–5918.719 | 192.767–236.927 | 0.0391, 0.0377, 0.0440 | Chronicle lower |
| validation | 5 | 120 | 3 | 9019.391–9125.887 | 167.423–391.935 | 0.0431, 0.0200, 0.0183 | Chronicle lower |
| confirmation | 0 | 120 | 2 | 18.575–18.783 | 168.575–189.695 | 9.0754, 10.0993 | Caffeine lower |
| confirmation | 0.5 | 120 | 2 | 152.191–828.415 | 183.423–303.615 | 0.2214, 1.9950 | Mixed |
| confirmation | 5 | 120 | 2 | 8814.591–8953.855 | 414.975–477.439 | 0.0533, 0.0471 | Chronicle lower |

## All-fork response p99.9 numerical error

No below-budget, small or warning-bearing outcome is excluded. Constant quantiles were specified after primary outcomes, before fresh confirmation; primary comparison is retrospective. M2 was frozen after pilot and before primary unblinding.

| Cohort / subset | Model | N | Median absolute µs | p90 absolute µs | Median relative % | p90 relative % |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| validation / all | M0 | 30 | 226.909 | 459.844 | 81.54 | 100.00 |
| validation / all | M1 | 30 | 210.316 | 443.890 | 50.47 | 90.81 |
| validation / all | M2 | 30 | 139.189 | 303.809 | 35.16 | 79.01 |
| validation / all | constant | 30 | 309.696 | 5194.240 | 51.10 | 92.06 |
| validation / CAFFEINE | M0 | 15 | 425.594 | 518.319 | 12.80 | 100.00 |
| validation / CAFFEINE | M1 | 15 | 409.640 | 502.365 | 12.38 | 37.56 |
| validation / CAFFEINE | M2 | 15 | 275.137 | 336.577 | 8.19 | 30.17 |
| validation / CAFFEINE | constant | 15 | 3041.792 | 8368.640 | 86.54 | 3286.84 |
| validation / CHRONICLE_IN_MEMORY | M0 | 15 | 192.767 | 230.869 | 100.00 | 100.00 |
| validation / CHRONICLE_IN_MEMORY | M1 | 15 | 176.174 | 214.276 | 89.44 | 91.39 |
| validation / CHRONICLE_IN_MEMORY | M2 | 15 | 134.657 | 142.657 | 65.13 | 88.21 |
| validation / CHRONICLE_IN_MEMORY | constant | 15 | 54.144 | 151.680 | 28.09 | 52.25 |
| confirmation / all | M0 | 12 | 207.052 | 370.635 | 86.96 | 100.00 |
| confirmation / all | M1 | 12 | 190.459 | 354.681 | 51.58 | 90.95 |
| confirmation / all | M2 | 12 | 137.482 | 230.081 | 31.34 | 80.21 |
| confirmation / all | constant | 12 | 307.584 | 8090.112 | 68.78 | 3757.10 |
| confirmation / CAFFEINE | M0 | 6 | 255.810 | 373.255 | 72.37 | 100.00 |
| confirmation / CAFFEINE | M1 | 6 | 239.857 | 357.301 | 14.59 | 89.52 |
| confirmation / CAFFEINE | M2 | 6 | 183.114 | 230.081 | 14.52 | 89.46 |
| confirmation / CAFFEINE | constant | 6 | 705.800 | 8229.376 | 233.97 | 3800.29 |
| confirmation / CHRONICLE_IN_MEMORY | M0 | 6 | 207.052 | 255.318 | 86.96 | 100.00 |
| confirmation / CHRONICLE_IN_MEMORY | M1 | 6 | 190.459 | 238.726 | 79.30 | 91.25 |
| confirmation / CHRONICLE_IN_MEMORY | M2 | 6 | 137.017 | 149.441 | 56.86 | 80.21 |
| confirmation / CHRONICLE_IN_MEMORY | constant | 6 | 108.032 | 338.816 | 40.63 | 70.97 |

## Every comparison group

Every row keeps its seed, phase duration and cohort. The CSV additionally supplies all channels and p50/p99/p99.9/p99.99/p99.999.

| Cohort | Writes % | Warmup s | Seed | Block | p99.9 Ch/C | p99.99 Ch/C | p99.999 Ch/C | Warning-free pair |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| qualification | 0 | 12 | 34801 | 1 | 8.51871 | 0.73182 | 0.65661 | True |
| qualification | 0 | 120 | 34801 | 1 | 6.28600 | 0.89011 | 0.67901 | True |
| qualification | 0 | 60 | 34801 | 1 | 29.38704 | 1.38981 | 1.26377 | False |
| qualification | 0.5 | 12 | 34801 | 1 | 0.60336 | 0.22227 | 0.24510 | False |
| qualification | 0.5 | 120 | 34801 | 1 | 0.33940 | 0.20235 | 0.18180 | True |
| qualification | 0.5 | 60 | 34801 | 1 | 0.10661 | 0.13743 | 0.12883 | True |
| qualification | 5 | 12 | 34801 | 1 | 0.02532 | 0.11098 | 0.13818 | True |
| qualification | 5 | 120 | 34801 | 1 | 0.01501 | 0.10859 | 0.12754 | True |
| qualification | 5 | 60 | 34801 | 1 | 0.02955 | 0.12221 | 0.13006 | False |
| validation | 0 | 120 | 34811 | 1 | 7.45843 | 0.71970 | 0.61980 | True |
| validation | 0 | 120 | 34812 | 2 | 6.40863 | 0.79609 | 0.59969 | False |
| validation | 0 | 120 | 34813 | 3 | 7.80290 | 0.83546 | 0.81225 | True |
| validation | 1 | 120 | 34811 | 1 | 0.05934 | 0.13002 | 0.13338 | True |
| validation | 1 | 120 | 34812 | 2 | 0.03826 | 0.11735 | 0.11843 | True |
| validation | 1 | 120 | 34813 | 3 | 0.07725 | 0.13594 | 0.16423 | False |
| validation | 2 | 120 | 34811 | 1 | 0.03906 | 0.13688 | 0.15891 | True |
| validation | 2 | 120 | 34812 | 2 | 0.03768 | 0.12800 | 0.13239 | False |
| validation | 2 | 120 | 34813 | 3 | 0.04402 | 0.12527 | 0.12572 | False |
| validation | 0.5 | 120 | 34811 | 1 | 0.14096 | 0.16923 | 0.14971 | True |
| validation | 0.5 | 120 | 34812 | 2 | 0.13808 | 0.19939 | 0.18589 | False |
| validation | 0.5 | 120 | 34813 | 3 | 0.23936 | 0.17843 | 0.15943 | False |
| validation | 5 | 120 | 34811 | 1 | 0.04310 | 0.13450 | 0.15634 | False |
| validation | 5 | 120 | 34812 | 2 | 0.02002 | 0.11286 | 0.11735 | False |
| validation | 5 | 120 | 34813 | 3 | 0.01835 | 0.11080 | 0.11954 | False |
| confirmation | 0 | 120 | 44811 | 1 | 9.07537 | 0.86022 | 0.63399 | True |
| confirmation | 0 | 120 | 44812 | 2 | 10.09929 | 0.94031 | 0.69447 | True |
| confirmation | 0.5 | 120 | 44811 | 1 | 0.22141 | 0.19192 | 0.17425 | False |
| confirmation | 0.5 | 120 | 44812 | 2 | 1.99496 | 0.16845 | 0.16894 | False |
| confirmation | 5 | 120 | 44811 | 1 | 0.05332 | 0.14689 | 0.23731 | True |
| confirmation | 5 | 120 | 44812 | 2 | 0.04708 | 0.20042 | 0.37784 | False |

## Reproduction and boundaries

The portable package contains60 research forks,284 nonempty distributions,1420 exact percentile reconstructions,710 paired ratios and710 point conclusions. Empty update channels at 0% are intentional. Independent portable checks conserve60 read/update unions,180 threshold rates,720 M0/M1/constant values and220 numerical summaries. The separate replay reproduces all 168 M2 values across42 holdout forks from portable GC/schedule inputs using the frozen solver, not an independent implementation. Raw audits independently decode320 research/control HDR files and reconcile source/runtime, stream continuity, writes, GC and sampled RSS. The diagnostic is not counted in those cohort audits.

See [protocol](../TAILCACHE_PREDICTOR_PLAN.md), [secondary protocol](../TAILCACHE_PREDICTOR_CONFIRMATION_PROTOCOL.md), [portable verification](portable-verification.json), [model replay](model-replay.json), [figures](FIGURES.md), [working manuscript](../preprint/MANUSCRIPT.md) and [final researcher review](REVIEW.md). Dataset: `predictor-data-20261118.json`. Frozen models and stream code are preserved in committed source and per-cohort archives. Retained model-worth fields describe the consumed single expansion decision; they do not authorize another12 forks.

This is an agent-reviewed working artifact, not independent peer review, an author-approved preprint, a public raw-evidence deposit or a clean-machine performance replication. Rare tails share stall episodes. No general exact threshold, object-lifetime isolation, total-memory saving or universal cache-selection rule is supported.
