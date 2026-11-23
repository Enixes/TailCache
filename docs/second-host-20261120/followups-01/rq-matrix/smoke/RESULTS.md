# Portable experiment results

4/4 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 1.137 | 1.005–1.27 | 0 |
| 1 | service | 99.9 | 2 | 1.161 | 0.7693–1.552 | 0 |
| 1 | service | 99.99 | 2 | 1.06 | 0.9993–1.12 | 0 |
| 1 | service | 99.999 | 2 | 1.06 | 0.9993–1.12 | 0 |
| 1 | response | 99 | 2 | 1.113 | 0.9991–1.226 | 0 |
| 1 | response | 99.9 | 2 | 0.8292 | 0.6876–0.9709 | 0 |
| 1 | response | 99.99 | 2 | 3.243 | 0.1363–6.35 | 0 |
| 1 | response | 99.999 | 2 | 3.243 | 0.1363–6.35 | 0 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 1979.0 | 2225.0 | CAFFEINE | False |
| 1 | service | 99.9 | 6619.0 | 6873.0 | UNRESOLVED | True |
| 1 | service | 99.99 | 11003.0 | 11595.0 | UNRESOLVED | True |
| 1 | service | 99.999 | 11003.0 | 11595.0 | UNRESOLVED | True |
| 1 | response | 99 | 2058.0 | 2270.0 | UNRESOLVED | False |
| 1 | response | 99.9 | 8959.0 | 7309.0 | CHRONICLE_IN_MEMORY | True |
| 1 | response | 99.99 | 47135.0 | 43999.0 | UNRESOLVED | True |
| 1 | response | 99.999 | 47135.0 | 43999.0 | UNRESOLVED | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
No adjacent fully observed ranking reversal is resolved in this run.
