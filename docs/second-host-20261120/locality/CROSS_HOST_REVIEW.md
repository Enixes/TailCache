# TailCache locality replication on a second host

Collected on 20 November 2026 IST on Pop!_OS 24.04 LTS, Ryzen 7 5800X
(16 logical CPUs), 32 GiB RAM, and Temurin 21.0.13+9. The source checkout
was `8637d5535b321f430a8fc7975301cb97906b8ab9`. The runner used the frozen
locality profile with G1, a 512 MiB heap, a 12-CPU JVM budget, 32,768 resident
4 KiB values, 5% writes, zero ballast, 50,000 arrivals/s, 120 s warmup with
zero priming, 4 s conditioning, and 30 s measurement. Both backends used
the same trace within each seed and reversed order across seeds.

## Scheduled-response results

All latencies below are in microseconds. Ratios use Chronicle divided by Caffeine.

| Eligible update keys | Seed | p99.9 Caffeine / Chronicle | p99.9 ratio | p99.99 Caffeine / Chronicle | p99.999 Caffeine / Chronicle | Warnings |
|---:|---:|---:|---:|---:|---:|---|
| 2,048 | 61801 | 6.531 / 9.255 | 1.417 | 1415.167 / 540.671 | 1988.607 / 719.359 | None |
| 2,048 | 61802 | 6.415 / 7.611 | 1.186 | 1308.671 / 530.943 | 1960.959 / 702.463 | Chronicle, 352 ms compilation activity |
| 32,768 | 61801 | 3094.527 / 7.475 | 0.002416 | 5709.823 / 545.279 | 6238.207 / 706.047 | None |
| 32,768 | 61802 | 3647.487 / 7.895 | 0.002165 | 6262.783 / 555.007 | 7081.983 / 726.527 | None |

Both seeds reproduce the first host's p99.9 reversal. Caffeine leads with
2,048 update keys and Chronicle leads with 32,768. First-host p99.9 ratios
were 2.666–9.224 for 2,048 and 0.01365–0.02336 for 32,768. This host has a
smaller Caffeine advantage in the concentrated arm and a larger Chronicle
advantage in the distributed arm. The JVM build, hardware, operating
environment and seeds changed together. These differences in magnitude cannot
be assigned to one of those changes.

At p99.99 and p99.999, Chronicle leads in all four new response pairs. That
also matches the first host's direction in both arms. Each research JVM
completed 1,500,000 requests. Roughly 15 requests lie beyond the p99.999
rank per JVM, so treat that result as a descriptive extreme-tail observation.

## GC, service and data quality

- Caffeine's measured GC pause overlap increases from 8.21–9.91 ms with
  concentrated updates to 59.57–65.13 ms with distributed updates. Chronicle
  stays at 12.79–13.15 ms. Caffeine's measured worker allocation per operation
  is identical between update sets for each seed. Chronicle's is also identical
  between its update sets. This supports an association with pause exposure
  under matched write demand. Locality, value survival and policy activity
  varied together.
- The separate service p99.9 metric favors Caffeine in both concentrated
  pairs and is mixed in the distributed arm. The new run only varies the update
  working set at zero ballast, so it adds no direct test of a pressure crossover.
- All eight research JVMs and all four pairs passed the retained evidence checks.
  Warning-free coverage was 1/2 concentrated pairs and 2/2 distributed pairs.
  There were no measured GC evacuation failures. The compiler warning in the
  second concentrated Chronicle JVM remains in the paired result.

An offline check revalidated the report hash, all eight slot seals and raw file
inventories, the compressed HDR and independent logical stream receipts, and
the derived histogram and GC statistics. The original first-host data was used
for comparison without pooling the two hosts.

- [Run summary](SUMMARY.md)
- [All measurement results](research/RESULTS.md)
- [Machine-readable paired results](research/results-compact.json)
- [Frozen host, JVM and provenance manifest](../MANIFEST.json)
- [Original mechanism results](../../mechanism/RESULTS.md)
