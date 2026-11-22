# Portable experiment results

4/4 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 1.701 | 1.494–1.907 | 0 |
| 1 | service | 99.9 | 2 | 1.518 | 1.331–1.705 | 0 |
| 1 | service | 99.99 | 2 | 1.243 | 1.022–1.465 | 0 |
| 1 | service | 99.999 | 2 | 1.243 | 1.022–1.465 | 0 |
| 1 | response | 99 | 2 | 1.689 | 1.497–1.881 | 0 |
| 1 | response | 99.9 | 2 | 1.512 | 1.332–1.691 | 0 |
| 1 | response | 99.99 | 2 | 1.242 | 1.023–1.461 | 0 |
| 1 | response | 99.999 | 2 | 1.242 | 1.023–1.461 | 0 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 1417.5 | 2410.0 | CAFFEINE | False |
| 1 | service | 99.9 | 3197.0 | 4890.0 | CAFFEINE | True |
| 1 | service | 99.99 | 7287.0 | 8659.0 | CAFFEINE | True |
| 1 | service | 99.999 | 7287.0 | 8659.0 | CAFFEINE | True |
| 1 | response | 99 | 1457.0 | 2461.0 | CAFFEINE | False |
| 1 | response | 99.9 | 3233.0 | 4925.0 | CAFFEINE | True |
| 1 | response | 99.99 | 7321.0 | 8697.0 | CAFFEINE | True |
| 1 | response | 99.999 | 7321.0 | 8697.0 | CAFFEINE | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
No adjacent fully observed ranking reversal is resolved in this run.
