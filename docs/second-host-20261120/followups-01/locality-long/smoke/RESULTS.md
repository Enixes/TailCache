# Portable experiment results

4/4 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 1.152 | 1.08–1.224 | 0 |
| 1 | service | 99.9 | 2 | 0.817 | 0.6897–0.9443 | 0 |
| 1 | service | 99.99 | 2 | 0.9412 | 0.8543–1.028 | 0 |
| 1 | service | 99.999 | 2 | 0.9412 | 0.8543–1.028 | 0 |
| 1 | response | 99 | 2 | 1.106 | 1.047–1.165 | 0 |
| 1 | response | 99.9 | 2 | 1.059 | 0.8828–1.236 | 0 |
| 1 | response | 99.99 | 2 | 0.9405 | 0.8549–1.026 | 0 |
| 1 | response | 99.999 | 2 | 0.9405 | 0.8549–1.026 | 0 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 1898.5 | 2180.0 | CAFFEINE | False |
| 1 | service | 99.9 | 6675.0 | 5317.0 | CHRONICLE_IN_MEMORY | True |
| 1 | service | 99.99 | 9963.0 | 9279.0 | UNRESOLVED | True |
| 1 | service | 99.999 | 9963.0 | 9279.0 | UNRESOLVED | True |
| 1 | response | 99 | 2006.5 | 2214.0 | CAFFEINE | False |
| 1 | response | 99.9 | 6709.0 | 6919.0 | UNRESOLVED | True |
| 1 | response | 99.99 | 10011.0 | 9319.0 | UNRESOLVED | True |
| 1 | response | 99.999 | 10011.0 | 9319.0 | UNRESOLVED | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
No adjacent fully observed ranking reversal is resolved in this run.
