# Portable experiment results

4/4 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 1.824 | 1.57–2.079 | 0 |
| 1 | service | 99.9 | 2 | 2.05 | 1.778–2.323 | 0 |
| 1 | service | 99.99 | 2 | 2.614 | 1.832–3.396 | 0 |
| 1 | service | 99.999 | 2 | 2.614 | 1.832–3.396 | 0 |
| 1 | response | 99 | 2 | 1.748 | 1.511–1.985 | 0 |
| 1 | response | 99.9 | 2 | 1.942 | 1.533–2.351 | 0 |
| 1 | response | 99.99 | 2 | 0.1775 | 0.1572–0.1979 | 0 |
| 1 | response | 99.999 | 2 | 0.1775 | 0.1572–0.1979 | 0 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 1493.0 | 2701.0 | CAFFEINE | False |
| 1 | service | 99.9 | 4481.0 | 9007.0 | CAFFEINE | True |
| 1 | service | 99.99 | 7171.0 | 19103.0 | CAFFEINE | True |
| 1 | service | 99.999 | 7171.0 | 19103.0 | CAFFEINE | True |
| 1 | response | 99 | 1595.5 | 2768.0 | CAFFEINE | False |
| 1 | response | 99.9 | 5319.0 | 10055.0 | CAFFEINE | True |
| 1 | response | 99.99 | 104799.0 | 19139.0 | CHRONICLE_IN_MEMORY | True |
| 1 | response | 99.999 | 104799.0 | 19139.0 | CHRONICLE_IN_MEMORY | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
No adjacent fully observed ranking reversal is resolved in this run.
