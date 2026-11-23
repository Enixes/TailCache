# 23 November Pop!_OS follow-up

The Ryzen 7 5800X ran the suites sequentially with Temurin 21.0.13+9, G1,
a fixed 512 MiB heap and a 12-CPU JVM budget. The locality experiment completed.
Both split-timing instruments failed qualification. Their research phases
stopped at the gate.

## Scheduled response under heavier loads

Both backends completed every scheduled arrival in all 32 research JVMs.
There were 16 usable pairs, including 13 warning-free pairs. Four forks
carried compilation-activity warnings. The frozen retry policy selected zero
pairs. All results below come from the two paired seeds 62201 and 62202.
Durations are scheduled-response p99.9, in microseconds.

| Arrivals/s | Writes | Eligible write keys | Seed 62201 Caffeine / Chronicle | Seed 62202 Caffeine / Chronicle | Lower p99.9 |
|---:|---:|---:|---:|---:|---|
| 50,000 | 5% | 2,048 | 8.30 / 9.92 | 6.80 / 9.91 | Caffeine 2/2 |
| 50,000 | 5% | 32,768 | 3,461 / 10.00 | 3,572 / 9.82 | Chronicle 2/2 |
| 100,000 | 2.5% | 2,048 | 6.54 / 120.70 | 7.11 / 85.18 | Caffeine 2/2 |
| 100,000 | 2.5% | 32,768 | 3,830 / 73.79 | 3,783 / 85.06 | Chronicle 2/2 |
| 50,000 | 10% | 2,048 | 6.78 / 10.02 | 414.98 / 7.40 | Split 1/1 |
| 50,000 | 10% | 32,768 | 4,665 / 9.04 | 4,735 / 11.10 | Chronicle 2/2 |
| 50,000 | 20% | 2,048 | 9.29 / 11.10 | 9.57 / 8.16 | Split 1/1 |
| 50,000 | 20% | 32,768 | 5,493 / 10.37 | 5,575 / 11.30 | Chronicle 2/2 |

The 50,000 and 100,000 arrival settings both achieved roughly 2,500 writes/s.
Doubling arrivals at matched write intensity preserved the locality reversal in
both seeds. Chronicle's response tail increased at the higher arrival rate and
still led by 44–52× with the larger write set. With that write set Chronicle
led at all four tested loads. At 10% and 20% writes the concentrated write set
gave mixed rankings. Both concentrated pairs at 10% were warning-free. At
20% only the Caffeine-winning concentrated pair was warning-free.

Chronicle led the observed p99.99 and p99.999 in every pair in this suite.
At 50,000 arrivals/s the p99.999 estimates have only about 15 expected
observations beyond the percentile per fork. Keep the prior contrary 90-second
forks in the extreme-tail interpretation. The primary outcome is the
scheduled-response p99.9. The change in arrival rate also changes the operation
mix and the pacing. These two-seed, one-host comparisons extend the observed
workload range while keeping the original saturated-service result separate.
[All locality points](locality-load/research/RESULTS.md)

## Split-write timing qualification

| Pilot | Complete / warning-free forks | Shift in Chronicle/Caffeine service p99.9 ratio by seed | Result |
|---|---:|---|---|
| [Time every write](all-write-pilot/write-timing-pilot/write-timing-qualification.json) | 8 / 8 | +11.2%, +7.5% | Rejected at the 5% limit |
| [Time one in eight writes](sampled-write-pilot/write-timing-pilot/write-timing-qualification.json) | 8 / 8 | +14.1%, −9.7% | Rejected at the 5% limit |

The sampled split histograms contained 166,947–364,869 writes per fork and
passed the sample-count and timer-floor checks. Caffeine's whole-operation
p99.9 also shifted by −10.5% in one seed, exceeding its separate 10% limit.
The results establish that neither instrument met the required equivalence on
this host. They cannot distinguish direct timing overhead from JIT/layout
effects or ordinary between-fork variation. The payload-specific comparison
of value construction and adapter `put()` costs remains unresolved.

The first sampled setup failed at Java self-test compilation before any
benchmark forks. The corrected setup used a fresh directory and completed
the pilot at source `b11505f`. The earlier setup log stays on the host.
The predeclared bounded sampled attempt is exhausted.

### What the 5% limit means

For each seed, the gate divided the Chronicle/Caffeine service p99.9 ratio
with split timing by the ratio with the original timer. The result had to
stay within 5% of one. An original ratio of 1.10 therefore allows a split-timing
ratio of 1.045 to 1.155. The protocol declared this engineering tolerance
before collection to preserve modest differences between the caches. The
protocol records no baseline repeatability calibration for exactly 5%.
Both pilots would also have exceeded a 10% ratio tolerance in at least one
seed. [Frozen pilot protocol](../PORTABLE_EXPERIMENT.md#split-write-timing-on-the-pop_os-host)

For a future split-write study, repeat the original timer twice per backend
using fresh paired seeds and counterbalanced order. This A/A control estimates
how far the ratio moves across identical JVM runs. If its variability exceeds
the smallest latency difference the study aims to explain, improve
repeatability before testing another timer. Use the intended effect size and
measured variability to set the design and declare its limits before new
collection. Both recorded pilot verdicts stand.

## Evidence and verification

The [collection manifest](MANIFEST.json) binds source commits, suite manifests,
and original reports. The [archive index](archive/MANIFEST.json) gives the
checksums for [locality](archive/locality-load.tar.xz),
[all-write pilot](archive/all-write-pilot.tar.xz), and
[sampled pilot](archive/sampled-write-pilot.tar.xz). The three archives contain
32 research forks, 16 split-pilot forks, 12 smoke forks, and 24 timing controls.

The HDR histograms, bins, GC logs, windows, and host samples are byte-for-byte
copies. Exported run manifests retain the scientific settings and omit local
machine identifiers and launcher metadata. Worker configurations and receipts
rewrite checkout paths. The re-sealed archive receipts bind the archived files.
Each phase also records the hashes of the original receipts. Full source
collections remain in the host's ignored result directories.

```sh
python3 scripts/tailcache_verify_archive.py --popos-followup
```

The verifier reconstructs the percentiles, point conclusions, and split-pilot
gate verdicts from the archives. The paper can use the locality extension and
the failed timing qualification as separate findings.
