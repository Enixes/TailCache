# Portable experiment results

4/4 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 1.348 | 1.34–1.357 | 0 |
| 1 | service | 99.9 | 2 | 1.432 | 0.6879–2.176 | 0 |
| 1 | service | 99.99 | 2 | 1.272 | 0.9358–1.608 | 0 |
| 1 | service | 99.999 | 2 | 1.272 | 0.9358–1.608 | 0 |
| 1 | response | 99 | 2 | 1.327 | 1.281–1.372 | 0 |
| 1 | response | 99.9 | 2 | 0.9704 | 0.9323–1.008 | 0 |
| 1 | response | 99.99 | 2 | 1.19 | 0.7707–1.61 | 0 |
| 1 | response | 99.999 | 2 | 1.19 | 0.7707–1.61 | 0 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 1658.0 | 2235.0 | CAFFEINE | False |
| 1 | service | 99.9 | 5556.0 | 6453.0 | UNRESOLVED | True |
| 1 | service | 99.99 | 11163.0 | 14643.0 | UNRESOLVED | True |
| 1 | service | 99.999 | 11163.0 | 14643.0 | UNRESOLVED | True |
| 1 | response | 99 | 1772.5 | 2353.0 | CAFFEINE | False |
| 1 | response | 99.9 | 8095.0 | 7853.0 | UNRESOLVED | True |
| 1 | response | 99.99 | 12531.0 | 14903.0 | UNRESOLVED | True |
| 1 | response | 99.999 | 12531.0 | 14903.0 | UNRESOLVED | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
No adjacent fully observed ranking reversal is resolved in this run.
