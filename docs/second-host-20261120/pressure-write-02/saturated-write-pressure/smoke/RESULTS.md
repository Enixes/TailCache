# Portable experiment results

4/4 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 1.245 | 1.196–1.294 | 0 |
| 1 | service | 99.9 | 2 | 0.8354 | 0.4252–1.246 | 0 |
| 1 | service | 99.99 | 2 | 0.9868 | 0.7798–1.194 | 0 |
| 1 | service | 99.999 | 2 | 0.9868 | 0.7798–1.194 | 0 |
| 1 | response | 99 | 2 | 1.215 | 1.168–1.262 | 0 |
| 1 | response | 99.9 | 2 | 0.6467 | 0.427–0.8664 | 0 |
| 1 | response | 99.99 | 2 | 0.9312 | 0.6693–1.193 | 0 |
| 1 | response | 99.999 | 2 | 0.9312 | 0.6693–1.193 | 0 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 1858.5 | 2315.0 | CAFFEINE | False |
| 1 | service | 99.9 | 5922.0 | 4138.0 | UNRESOLVED | True |
| 1 | service | 99.99 | 10003.0 | 9663.0 | UNRESOLVED | True |
| 1 | service | 99.999 | 10003.0 | 9663.0 | UNRESOLVED | True |
| 1 | response | 99 | 1935.0 | 2352.0 | CAFFEINE | False |
| 1 | response | 99.9 | 7359.0 | 4623.0 | CHRONICLE_IN_MEMORY | True |
| 1 | response | 99.99 | 10963.0 | 9703.0 | UNRESOLVED | True |
| 1 | response | 99.999 | 10963.0 | 9703.0 | UNRESOLVED | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
No adjacent fully observed ranking reversal is resolved in this run.
