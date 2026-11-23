# Tightened pressure and write-transition campaign

Source commit: 021cfa2b31d6d18ba283a8228ed889ec8fbe5e97
All ratios are Chronicle/Caffeine. Below 1 favors Chronicle.

## saturated-write-pressure

96/96 first-pass JVMs, 48 usable pairs, 36 warning-free pairs and 37 pairs in the clean sensitivity view.
First-pass warning instances: 11 × Churn demand dropped; endogenous outcome retained, 1 × Measured compiler activity exceeds frozen ceiling; not app pause time, 2 × Outside-process CPU upper bound exceeded frozen ceiling.
1 retry-eligible pairs, 1 selected, 1 recovered without warnings.
[Full results](saturated-write-pressure/research/RESULTS.md)

| Payload B | Ballast MiB | Writes % | First-pass p99.9 ratios | Clean sensitivity p99.9 ratios |
|---:|---:|---:|---|---|
| 256 | 0 | 1 | 0.3875, 0.4869, 0.3754, 0.4039 | 0.3875, 0.4869, 0.3754, 0.4039 |
| 256 | 0 | 5 | 0.4789, 0.4357, 0.3779, 0.3997 | 0.4789, 0.4357, 0.3779, 0.3997 |
| 256 | 0 | 10 | 0.5094, 0.4099, 0.4796, 0.414 | 0.5094, 0.4099, 0.4796, 0.414 |
| 256 | 288 | 1 | 0.3922, 0.4269, 0.3891, 0.3872 | 0.3922, 0.4269, 0.3891, 0.3872 |
| 256 | 288 | 5 | 0.4367, 0.4242, 0.4997, 0.448 | 0.4367, 0.4242, 0.4997, 0.4212 |
| 256 | 288 | 10 | 0.4493, 0.5174, 0.4997, 0.4893 | 0.4493, 0.5174, 0.4997, 0.4893 |
| 4096 | 0 | 1 | 1.141, 1.261, 1.209, 1.214 | 1.141, 1.261, 1.209, 1.214 |
| 4096 | 0 | 5 | 1.06, 1.113, 1.058, 1.101 | 1.06, 1.113, 1.058, 1.101 |
| 4096 | 0 | 10 | 1.078, 1.158, 1.044, 1.121 | 1.078, 1.158, 1.044, 1.121 |
| 4096 | 288 | 1 | 1.165, 1.177, 1.13, 1.161 | 1.161 |
| 4096 | 288 | 5 | 1.101, 1.044, 1.083, 1.06 | — |
| 4096 | 288 | 10 | 1.105, 1.137, 1.112, 1.13 | — |

## write-transition

48/48 first-pass JVMs, 24 usable pairs, 19 warning-free pairs and 19 pairs in the clean sensitivity view.
First-pass warning instances: 5 × Measured compiler activity exceeds frozen ceiling; not app pause time.
0 retry-eligible pairs, 0 selected, 0 recovered without warnings.
[Full results](write-transition/research/RESULTS.md)

| Payload B | Ballast MiB | Writes % | First-pass p99.9 ratios | Clean sensitivity p99.9 ratios |
|---:|---:|---:|---|---|
| 4096 | 0 | 0.5 | 1.146, 1.156, 1.166, 1.063 | 1.146, 1.156, 1.166 |
| 4096 | 0 | 0.75 | 1.151, 1.068, 1.054, 0.9464 | 1.054, 0.9464 |
| 4096 | 0 | 1 | 0.909, 0.1, 0.9547, 1.03 | 0.909, 0.1, 1.03 |
| 4096 | 0 | 1.25 | 25.99, 1.105, 1.136, 1.292 | 25.99, 1.105, 1.136, 1.292 |
| 4096 | 0 | 1.5 | 0.3356, 0.26, 0.2838, 0.002136 | 0.3356, 0.26, 0.2838, 0.002136 |
| 4096 | 0 | 2 | 0.05416, 0.01457, 0.08182, 0.01349 | 0.05416, 0.01457, 0.01349 |

Conditional midpoint selection: no setting qualified.
