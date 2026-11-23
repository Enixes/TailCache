# Portable experiment results

4/4 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 0.9933 | 0.9624–1.024 | 2 |
| 1 | service | 99.9 | 2 | 0.9406 | 0.927–0.9541 | 2 |
| 1 | service | 99.99 | 2 | 0.9447 | 0.9314–0.958 | 2 |
| 1 | service | 99.999 | 2 | 0.695 | 0.1589–1.231 | 2 |
| 1 | response | 99 | 0 | — | — | 0 |
| 1 | response | 99.9 | 0 | — | — | 0 |
| 1 | response | 99.99 | 0 | — | — | 0 |
| 1 | response | 99.999 | 0 | — | — | 0 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 6479.0 | 6429.0 | UNRESOLVED | False |
| 1 | service | 99.9 | 7545.0 | 7095.0 | CHRONICLE_IN_MEMORY | False |
| 1 | service | 99.99 | 11059.0 | 10447.0 | CHRONICLE_IN_MEMORY | False |
| 1 | service | 99.999 | 2061055.0 | 600575.0 | UNRESOLVED | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
No adjacent fully observed ranking reversal is resolved in this run.
