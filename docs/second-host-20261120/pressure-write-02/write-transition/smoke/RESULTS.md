# Portable experiment results

4/4 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 1.137 | 1.036–1.239 | 0 |
| 1 | service | 99.9 | 2 | 1.08 | 1.049–1.111 | 0 |
| 1 | service | 99.99 | 2 | 1.734 | 1.19–2.278 | 0 |
| 1 | service | 99.999 | 2 | 1.734 | 1.19–2.278 | 0 |
| 1 | response | 99 | 2 | 0.8152 | 0.59–1.04 | 0 |
| 1 | response | 99.9 | 2 | 1.024 | 0.9556–1.092 | 0 |
| 1 | response | 99.99 | 2 | 0.6922 | 0.3778–1.007 | 0 |
| 1 | response | 99.999 | 2 | 0.6922 | 0.3778–1.007 | 0 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 1899.0 | 2150.0 | CAFFEINE | False |
| 1 | service | 99.9 | 6473.0 | 6979.0 | CAFFEINE | True |
| 1 | service | 99.99 | 9375.0 | 16203.0 | CAFFEINE | True |
| 1 | service | 99.999 | 9375.0 | 16203.0 | CAFFEINE | True |
| 1 | response | 99 | 2948.0 | 2198.0 | UNRESOLVED | False |
| 1 | response | 99.9 | 8007.0 | 8251.0 | UNRESOLVED | True |
| 1 | response | 99.99 | 35779.0 | 18399.0 | UNRESOLVED | True |
| 1 | response | 99.999 | 35779.0 | 18399.0 | UNRESOLVED | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
No adjacent fully observed ranking reversal is resolved in this run.
