# Portable experiment results

8/8 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 1.131 | 1.118–1.143 | 2 |
| 1 | service | 99.9 | 2 | 1.105 | 1.084–1.126 | 2 |
| 1 | service | 99.99 | 2 | 1.169 | 1.149–1.189 | 2 |
| 1 | service | 99.999 | 2 | 39.39 | 38.46–40.32 | 2 |
| 1 | response | 99 | 0 | — | — | 0 |
| 1 | response | 99.9 | 0 | — | — | 0 |
| 1 | response | 99.99 | 0 | — | — | 0 |
| 1 | response | 99.999 | 0 | — | — | 0 |
| 2 | service | 99 | 2 | 1.23 | 1.185–1.274 | 2 |
| 2 | service | 99.9 | 2 | 1.209 | 1.165–1.252 | 2 |
| 2 | service | 99.99 | 2 | 1.168 | 1.109–1.228 | 2 |
| 2 | service | 99.999 | 2 | 44.9 | 44.45–45.36 | 2 |
| 2 | response | 99 | 0 | — | — | 0 |
| 2 | response | 99.9 | 0 | — | — | 0 |
| 2 | response | 99.99 | 0 | — | — | 0 |
| 2 | response | 99.999 | 0 | — | — | 0 |
| 2 | write-value-construction | 99 | 2 | 1.079 | 1.015–1.142 | 2 |
| 2 | write-value-construction | 99.9 | 2 | 1.097 | 1.05–1.143 | 2 |
| 2 | write-value-construction | 99.99 | 2 | 0.0282 | 0.02755–0.02886 | 2 |
| 2 | write-value-construction | 99.999 | 2 | 0.0886 | 0.0842–0.093 | 2 |
| 2 | write-cache-put | 99 | 2 | 1.523 | 1.476–1.57 | 2 |
| 2 | write-cache-put | 99.9 | 2 | 3.162 | 2.975–3.349 | 2 |
| 2 | write-cache-put | 99.99 | 2 | 1.404 | 1.356–1.452 | 2 |
| 2 | write-cache-put | 99.999 | 2 | 0.7628 | 0.5974–0.9283 | 2 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 6209.0 | 7019.0 | CAFFEINE | False |
| 1 | service | 99.9 | 6993.0 | 7725.0 | CAFFEINE | False |
| 1 | service | 99.99 | 9835.0 | 11495.0 | CAFFEINE | False |
| 1 | service | 99.999 | 15127.0 | 595711.0 | CAFFEINE | False |
| 2 | service | 99 | 5607.0 | 6895.0 | CAFFEINE | False |
| 2 | service | 99.9 | 6423.0 | 7761.0 | CAFFEINE | False |
| 2 | service | 99.99 | 9687.0 | 11307.0 | CAFFEINE | False |
| 2 | service | 99.999 | 13243.0 | 594687.0 | CAFFEINE | False |
| 2 | write-value-construction | 99 | 6379.0 | 6869.0 | CAFFEINE | False |
| 2 | write-value-construction | 99.9 | 9623.0 | 10543.0 | CAFFEINE | False |
| 2 | write-value-construction | 99.99 | 509951.0 | 14375.0 | CHRONICLE_IN_MEMORY | False |
| 2 | write-value-construction | 99.999 | 6924287.0 | 613631.0 | UNRESOLVED | True |
| 2 | write-cache-put | 99 | 971.0 | 1478.0 | CAFFEINE | False |
| 2 | write-cache-put | 99.9 | 1112.0 | 3507.0 | CAFFEINE | False |
| 2 | write-cache-put | 99.99 | 4195.0 | 5887.0 | CAFFEINE | False |
| 2 | write-cache-put | 99.999 | 17755.0 | 12747.0 | UNRESOLVED | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
No adjacent fully observed ranking reversal is resolved in this run.
