# Portable experiment results

4/4 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 1.288 | 1.128–1.448 | 0 |
| 1 | service | 99.9 | 2 | 1.499 | 1.409–1.589 | 0 |
| 1 | service | 99.99 | 2 | 1.133 | 0.8751–1.392 | 0 |
| 1 | service | 99.999 | 2 | 1.133 | 0.8751–1.392 | 0 |
| 1 | response | 99 | 2 | 1.064 | 0.7035–1.425 | 0 |
| 1 | response | 99.9 | 2 | 1.124 | 0.8503–1.398 | 0 |
| 1 | response | 99.99 | 2 | 0.9357 | 0.8749–0.9966 | 0 |
| 1 | response | 99.999 | 2 | 0.9357 | 0.8749–0.9966 | 0 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 1798.5 | 2254.5 | CAFFEINE | False |
| 1 | service | 99.9 | 3924.0 | 5953.0 | CAFFEINE | True |
| 1 | service | 99.99 | 11535.0 | 12663.0 | UNRESOLVED | True |
| 1 | service | 99.999 | 11535.0 | 12663.0 | UNRESOLVED | True |
| 1 | response | 99 | 2526.0 | 2305.0 | UNRESOLVED | False |
| 1 | response | 99.9 | 6032.0 | 6003.0 | UNRESOLVED | True |
| 1 | response | 99.99 | 13559.0 | 12711.0 | CHRONICLE_IN_MEMORY | True |
| 1 | response | 99.999 | 13559.0 | 12711.0 | CHRONICLE_IN_MEMORY | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
No adjacent fully observed ranking reversal is resolved in this run.
