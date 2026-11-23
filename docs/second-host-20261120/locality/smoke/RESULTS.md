# Portable experiment results

4/4 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 1.335 | 1.289–1.381 | 0 |
| 1 | service | 99.9 | 2 | 1.295 | 1.149–1.442 | 0 |
| 1 | service | 99.99 | 2 | 1.633 | 1.466–1.8 | 0 |
| 1 | service | 99.999 | 2 | 1.633 | 1.466–1.8 | 0 |
| 1 | response | 99 | 2 | 1.291 | 1.237–1.345 | 0 |
| 1 | response | 99.9 | 2 | 1.259 | 0.9445–1.574 | 0 |
| 1 | response | 99.99 | 2 | 1.484 | 1.178–1.79 | 0 |
| 1 | response | 99.999 | 2 | 1.484 | 1.178–1.79 | 0 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 1763.5 | 2360.0 | CAFFEINE | False |
| 1 | service | 99.9 | 5561.0 | 7055.0 | CAFFEINE | True |
| 1 | service | 99.99 | 11131.0 | 18187.0 | CAFFEINE | True |
| 1 | service | 99.999 | 11131.0 | 18187.0 | CAFFEINE | True |
| 1 | response | 99 | 1856.5 | 2403.0 | CAFFEINE | False |
| 1 | response | 99.9 | 6327.0 | 7419.0 | UNRESOLVED | True |
| 1 | response | 99.99 | 12547.0 | 18231.0 | CAFFEINE | True |
| 1 | response | 99.999 | 12547.0 | 18231.0 | CAFFEINE | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
No adjacent fully observed ranking reversal is resolved in this run.
