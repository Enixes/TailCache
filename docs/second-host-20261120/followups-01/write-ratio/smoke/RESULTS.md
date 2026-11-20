# Portable experiment results

4/4 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 1.152 | 1.134–1.169 | 0 |
| 1 | service | 99.9 | 2 | 1.047 | 1.026–1.069 | 0 |
| 1 | service | 99.99 | 2 | 1.474 | 0.8114–2.136 | 0 |
| 1 | service | 99.999 | 2 | 1.474 | 0.8114–2.136 | 0 |
| 1 | response | 99 | 2 | 0.8458 | 0.5274–1.164 | 0 |
| 1 | response | 99.9 | 2 | 0.853 | 0.5766–1.129 | 0 |
| 1 | response | 99.99 | 2 | 0.753 | 0.6632–0.8429 | 0 |
| 1 | response | 99.999 | 2 | 0.753 | 0.6632–0.8429 | 0 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 2074.5 | 2390.0 | CAFFEINE | False |
| 1 | service | 99.9 | 6579.0 | 6915.0 | CAFFEINE | True |
| 1 | service | 99.99 | 10459.0 | 14811.0 | UNRESOLVED | True |
| 1 | service | 99.999 | 10459.0 | 14811.0 | UNRESOLVED | True |
| 1 | response | 99 | 3300.0 | 2431.0 | UNRESOLVED | False |
| 1 | response | 99.9 | 11503.0 | 8521.0 | UNRESOLVED | True |
| 1 | response | 99.99 | 21119.0 | 15031.0 | CHRONICLE_IN_MEMORY | True |
| 1 | response | 99.999 | 21119.0 | 15031.0 | CHRONICLE_IN_MEMORY | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
No adjacent fully observed ranking reversal is resolved in this run.
