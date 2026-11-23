# Portable experiment results

4/4 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 1.68 | 1.5–1.86 | 0 |
| 1 | service | 99.9 | 2 | 1.826 | 0.9758–2.676 | 0 |
| 1 | service | 99.99 | 2 | 2.662 | 1.063–4.26 | 0 |
| 1 | service | 99.999 | 2 | 2.662 | 1.063–4.26 | 0 |
| 1 | response | 99 | 2 | 1.684 | 1.52–1.848 | 0 |
| 1 | response | 99.9 | 2 | 1.686 | 1.003–2.37 | 0 |
| 1 | response | 99.99 | 2 | 3.029 | 1.813–4.245 | 0 |
| 1 | response | 99.999 | 2 | 3.029 | 1.813–4.245 | 0 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 1403.0 | 2350.0 | CAFFEINE | False |
| 1 | service | 99.9 | 4454.0 | 7421.0 | UNRESOLVED | True |
| 1 | service | 99.99 | 8659.0 | 23783.0 | CAFFEINE | True |
| 1 | service | 99.999 | 8659.0 | 23783.0 | CAFFEINE | True |
| 1 | response | 99 | 1432.5 | 2407.0 | CAFFEINE | False |
| 1 | response | 99.9 | 4725.0 | 7549.0 | CAFFEINE | True |
| 1 | response | 99.99 | 8695.0 | 26899.0 | CAFFEINE | True |
| 1 | response | 99.999 | 8695.0 | 26899.0 | CAFFEINE | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
No adjacent fully observed ranking reversal is resolved in this run.
