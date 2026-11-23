# Portable experiment results

8/8 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 1.199 | 1.157–1.242 | 1 |
| 1 | service | 99.9 | 2 | 1.273 | 1.148–1.397 | 1 |
| 1 | service | 99.99 | 2 | 1.211 | 0.9687–1.453 | 1 |
| 1 | service | 99.999 | 2 | 71.27 | 63.42–79.13 | 1 |
| 1 | response | 99 | 2 | 1.203 | 1.162–1.244 | 1 |
| 1 | response | 99.9 | 2 | 1.302 | 1.186–1.417 | 1 |
| 1 | response | 99.99 | 2 | 0.3939 | 0.3821–0.4057 | 1 |
| 1 | response | 99.999 | 2 | 0.36 | 0.3582–0.3617 | 1 |
| 2 | service | 99 | 2 | 1.214 | 1.17–1.258 | 2 |
| 2 | service | 99.9 | 2 | 1.07 | 0.9703–1.169 | 2 |
| 2 | service | 99.99 | 2 | 1.083 | 0.9267–1.239 | 2 |
| 2 | service | 99.999 | 2 | 60.01 | 42.25–77.77 | 2 |
| 2 | response | 99 | 2 | 1.208 | 1.165–1.251 | 2 |
| 2 | response | 99.9 | 2 | 0.00229 | 0.002165–0.002416 | 2 |
| 2 | response | 99.99 | 2 | 0.09206 | 0.08862–0.0955 | 2 |
| 2 | response | 99.999 | 2 | 0.1079 | 0.1026–0.1132 | 2 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 5447.0 | 6533.0 | CAFFEINE | False |
| 1 | service | 99.9 | 6339.0 | 8069.0 | CAFFEINE | False |
| 1 | service | 99.99 | 7815.0 | 9315.0 | UNRESOLVED | False |
| 1 | service | 99.999 | 8729.0 | 615679.0 | CAFFEINE | True |
| 1 | response | 99 | 5491.0 | 6605.0 | CAFFEINE | False |
| 1 | response | 99.9 | 6473.0 | 8433.0 | CAFFEINE | False |
| 1 | response | 99.99 | 1361919.0 | 535807.0 | CHRONICLE_IN_MEMORY | False |
| 1 | response | 99.999 | 1974783.0 | 710911.0 | CHRONICLE_IN_MEMORY | True |
| 2 | service | 99 | 5477.0 | 6649.0 | CAFFEINE | False |
| 2 | service | 99.9 | 6885.0 | 7311.0 | UNRESOLVED | False |
| 2 | service | 99.99 | 7765.0 | 8259.0 | UNRESOLVED | False |
| 2 | service | 99.999 | 11475.0 | 632831.0 | CAFFEINE | True |
| 2 | response | 99 | 5561.0 | 6717.0 | CAFFEINE | False |
| 2 | response | 99.9 | 3371007.0 | 7685.0 | CHRONICLE_IN_MEMORY | False |
| 2 | response | 99.99 | 5986303.0 | 550143.0 | CHRONICLE_IN_MEMORY | False |
| 2 | response | 99.999 | 6660095.0 | 716287.0 | CHRONICLE_IN_MEMORY | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
- {"axis": "updateHotset", "channel": "response", "fixedInputs": {"liveMiB": 0, "payloadBytes": 4096, "qps": 50000, "writeBps": 500}, "limit": "No bracket is not proof of no crossover; warning/rare-tail limitations apply", "observedRankingReversalBrackets": [{"fromBackend": "CAFFEINE", "fromValue": 2048, "toBackend": "CHRONICLE_IN_MEMORY", "toValue": 32768}], "quantile": 99.9, "testedPoints": [{"cell": 1, "cleanPairs": 1, "direction": "CAFFEINE", "tailSupportWarning": false, "value": 2048}, {"cell": 2, "cleanPairs": 2, "direction": "CHRONICLE_IN_MEMORY", "tailSupportWarning": false, "value": 32768}]}
