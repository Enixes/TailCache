# Portable experiment results

8/8 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 1.13 | 1.047–1.213 | 2 |
| 1 | service | 99.9 | 2 | 1.104 | 1.039–1.17 | 2 |
| 1 | service | 99.99 | 2 | 1.129 | 1.041–1.218 | 2 |
| 1 | service | 99.999 | 2 | 41.06 | 40.67–41.45 | 2 |
| 1 | response | 99 | 0 | — | — | 0 |
| 1 | response | 99.9 | 0 | — | — | 0 |
| 1 | response | 99.99 | 0 | — | — | 0 |
| 1 | response | 99.999 | 0 | — | — | 0 |
| 2 | service | 99 | 2 | 1.169 | 1.103–1.236 | 2 |
| 2 | service | 99.9 | 2 | 1.12 | 1.056–1.185 | 2 |
| 2 | service | 99.99 | 2 | 1.101 | 1.076–1.126 | 2 |
| 2 | service | 99.999 | 2 | 40.94 | 40.41–41.48 | 2 |
| 2 | response | 99 | 0 | — | — | 0 |
| 2 | response | 99.9 | 0 | — | — | 0 |
| 2 | response | 99.99 | 0 | — | — | 0 |
| 2 | response | 99.999 | 0 | — | — | 0 |
| 2 | write-value-construction | 99 | 2 | 0.9854 | 0.9403–1.031 | 2 |
| 2 | write-value-construction | 99.9 | 2 | 1.016 | 0.9776–1.055 | 2 |
| 2 | write-value-construction | 99.99 | 2 | 0.6723 | 0.607–0.7376 | 2 |
| 2 | write-value-construction | 99.999 | 2 | 0.0975 | 0.08756–0.1074 | 2 |
| 2 | write-cache-put | 99 | 2 | 1.439 | 1.368–1.51 | 2 |
| 2 | write-cache-put | 99.9 | 2 | 2.858 | 2.741–2.974 | 2 |
| 2 | write-cache-put | 99.99 | 2 | 1.27 | 1.265–1.275 | 2 |
| 2 | write-cache-put | 99.999 | 2 | 0.9915 | 0.5725–1.41 | 2 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 6057.0 | 6825.0 | CAFFEINE | False |
| 1 | service | 99.9 | 6969.0 | 7681.0 | CAFFEINE | False |
| 1 | service | 99.99 | 10031.0 | 11291.0 | CAFFEINE | False |
| 1 | service | 99.999 | 14639.0 | 601087.0 | CAFFEINE | False |
| 2 | service | 99 | 5949.0 | 6933.0 | CAFFEINE | False |
| 2 | service | 99.9 | 6833.0 | 7631.0 | CAFFEINE | False |
| 2 | service | 99.99 | 10343.0 | 11383.0 | CAFFEINE | False |
| 2 | service | 99.999 | 14235.0 | 582655.0 | CAFFEINE | False |
| 2 | write-value-construction | 99 | 6889.0 | 6773.0 | UNRESOLVED | False |
| 2 | write-value-construction | 99.9 | 10343.0 | 10495.0 | UNRESOLVED | False |
| 2 | write-value-construction | 99.99 | 24255.0 | 16303.0 | UNRESOLVED | True |
| 2 | write-value-construction | 99.999 | 6758399.0 | 655871.0 | UNRESOLVED | True |
| 2 | write-cache-put | 99 | 1032.0 | 1483.0 | CAFFEINE | False |
| 2 | write-cache-put | 99.9 | 1228.0 | 3512.0 | CAFFEINE | False |
| 2 | write-cache-put | 99.99 | 4641.0 | 5893.0 | UNRESOLVED | True |
| 2 | write-cache-put | 99.999 | 15085.0 | 11899.0 | UNRESOLVED | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
No adjacent fully observed ranking reversal is resolved in this run.
