# Portable experiment results

16/16 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 4 | 1.136 | 1.105–1.147 | 3 |
| 1 | service | 99.9 | 4 | 1.135 | 1.08–1.405 | 3 |
| 1 | service | 99.99 | 4 | 1.11 | 1.086–1.497 | 3 |
| 1 | service | 99.999 | 4 | 61.27 | 47.96–68.59 | 3 |
| 1 | response | 99 | 4 | 1.139 | 1.098–1.151 | 3 |
| 1 | response | 99.9 | 4 | 1.141 | 1.122–1.502 | 3 |
| 1 | response | 99.99 | 4 | 0.3676 | 0.3528–8.094 | 3 |
| 1 | response | 99.999 | 4 | 0.3337 | 0.3227–9.327 | 3 |
| 2 | service | 99 | 4 | 1.133 | 1.08–1.201 | 3 |
| 2 | service | 99.9 | 4 | 1.179 | 0.9218–1.374 | 3 |
| 2 | service | 99.99 | 4 | 1.304 | 0.8858–1.929 | 3 |
| 2 | service | 99.999 | 4 | 56.19 | 39.7–63.89 | 3 |
| 2 | response | 99 | 4 | 1.123 | 1.025–1.166 | 3 |
| 2 | response | 99.9 | 4 | 0.002906 | 0.002398–0.00321 | 3 |
| 2 | response | 99.99 | 4 | 0.08649 | 0.07901–1.693 | 3 |
| 2 | response | 99.999 | 4 | 0.1057 | 0.09727–1.727 | 3 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 5451.0 | 6229.0 | CAFFEINE | False |
| 1 | service | 99.9 | 6369.0 | 7917.0 | CAFFEINE | False |
| 1 | service | 99.99 | 7185.0 | 9133.0 | CAFFEINE | False |
| 1 | service | 99.999 | 8805.0 | 535551.0 | CAFFEINE | False |
| 1 | response | 99 | 5497.0 | 6293.0 | CAFFEINE | False |
| 1 | response | 99.9 | 6463.0 | 8321.0 | CAFFEINE | False |
| 1 | response | 99.99 | 1330687.0 | 479743.0 | UNRESOLVED | False |
| 1 | response | 99.999 | 1992191.0 | 655615.0 | UNRESOLVED | False |
| 2 | service | 99 | 5537.0 | 6235.0 | CAFFEINE | False |
| 2 | service | 99.9 | 6499.0 | 7629.0 | UNRESOLVED | False |
| 2 | service | 99.99 | 7427.0 | 9369.0 | UNRESOLVED | False |
| 2 | service | 99.999 | 9699.0 | 547327.0 | CAFFEINE | False |
| 2 | response | 99 | 5755.0 | 6317.0 | CAFFEINE | False |
| 2 | response | 99.9 | 3099647.0 | 9039.0 | CHRONICLE_IN_MEMORY | False |
| 2 | response | 99.99 | 5890047.0 | 501503.0 | UNRESOLVED | False |
| 2 | response | 99.999 | 6576127.0 | 682239.0 | UNRESOLVED | False |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
- {"axis": "updateHotset", "channel": "response", "fixedInputs": {"liveMiB": 0, "payloadBytes": 4096, "qps": 50000, "writeBps": 500}, "limit": "No bracket is not proof of no crossover; warning/rare-tail limitations apply", "observedRankingReversalBrackets": [{"fromBackend": "CAFFEINE", "fromValue": 2048, "toBackend": "CHRONICLE_IN_MEMORY", "toValue": 32768}], "quantile": 99.9, "testedPoints": [{"cell": 1, "cleanPairs": 3, "direction": "CAFFEINE", "tailSupportWarning": false, "value": 2048}, {"cell": 2, "cleanPairs": 3, "direction": "CHRONICLE_IN_MEMORY", "tailSupportWarning": false, "value": 32768}]}
