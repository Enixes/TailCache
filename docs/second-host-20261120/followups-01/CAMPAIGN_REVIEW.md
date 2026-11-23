# TailCache second-host follow-up review

Source commit: `ae686f26823c7f7278a46e53c74090002ad5690c`.
Ratios below are Chronicle/Caffeine. Values below 1 favor Chronicle.
Ratios are matched by cell and seed. Host cohorts are reported separately.

## write-ratio

20/20 research JVMs completed. 10/10 usable pairs, 6 without recorded warnings.
Warning instances: 4 × Measured compiler activity exceeds frozen ceiling; not app pause time.
[Suite summary](write-ratio/SUMMARY.md) · [Full results](write-ratio/research/RESULTS.md)

| Payload B | Ballast MiB | Writes % | Update keys | Arrivals/s | Clean pairs | Service p99.9 ratios | Response p99.9 ratios | Response p99.999 ratios |
|---:|---:|---:|---:|---:|---:|---|---|---|
| 4096 | 0 | 0 | 32768 | 50000 | 1/2 | 4.233, 1.588 | 4.421, 1.681 | 0.6403, 0.6482 |
| 4096 | 0 | 0.5 | 32768 | 50000 | 1/2 | 1.159, 1.183 | 1.046, 20.14 | 0.116, 2.698 |
| 4096 | 0 | 1 | 32768 | 50000 | 1/2 | 1.054, 1.186 | 1.019, 0.8932 | 0.1111, 0.1068 |
| 4096 | 0 | 2 | 32768 | 50000 | 2/2 | 1.175, 1.133 | 0.002316, 0.006051 | 0.02819, 0.1012 |
| 4096 | 0 | 5 | 32768 | 50000 | 1/2 | 1.041, 1.384 | 0.002634, 0.00304 | 0.1105, 0.1144 |

## locality-long

16/16 research JVMs completed. 8/8 usable pairs, 6 without recorded warnings.
Warning instances: 2 × Measured compiler activity exceeds frozen ceiling; not app pause time.
[Suite summary](locality-long/SUMMARY.md) · [Full results](locality-long/research/RESULTS.md)

| Payload B | Ballast MiB | Writes % | Update keys | Arrivals/s | Clean pairs | Service p99.9 ratios | Response p99.9 ratios | Response p99.999 ratios |
|---:|---:|---:|---:|---:|---:|---|---|---|
| 4096 | 0 | 5 | 2048 | 50000 | 3/4 | 1.08, 1.405, 1.108, 1.161 | 1.122, 1.502, 1.149, 1.132 | 0.3227, 9.327, 0.3365, 0.331 |
| 4096 | 0 | 5 | 32768 | 50000 | 3/4 | 0.9218, 1.374, 1.258, 1.101 | 0.00274, 0.00321, 0.003072, 0.002398 | 1.727, 0.1086, 0.09727, 0.1028 |

## rq-matrix

64/64 research JVMs completed. 32/32 usable pairs, 15 without recorded warnings.
Warning instances: 4 × Churn demand dropped; endogenous outcome retained, 2 × Measured compiler activity exceeds frozen ceiling; not app pause time, 11 × Outside-process CPU upper bound exceeded frozen ceiling.
[Suite summary](rq-matrix/SUMMARY.md) · [Full results](rq-matrix/research/RESULTS.md)

| Payload B | Ballast MiB | Writes % | Update keys | Arrivals/s | Clean pairs | Service p99.9 ratios | Response p99.9 ratios | Response p99.999 ratios |
|---:|---:|---:|---:|---:|---:|---|---|---|
| 256 | 0 | 5 | 32768 | saturated | 0/2 | 0.3942, 0.3836 | — | — |
| 256 | 0 | 5 | 32768 | 50000 | 2/2 | 0.7082, 0.6713 | 0.7723, 0.6953 | 0.253, 0.2335 |
| 256 | 96 | 5 | 32768 | saturated | 0/2 | 0.3522, 0.397 | — | — |
| 256 | 96 | 5 | 32768 | 50000 | 2/2 | 0.7123, 0.6405 | 0.7093, 0.4299 | 0.3076, 0.3249 |
| 256 | 208 | 5 | 32768 | saturated | 0/2 | 0.3527, 0.5998 | — | — |
| 256 | 208 | 5 | 32768 | 50000 | 2/2 | 0.6529, 0.6552 | 0.6661, 0.6279 | 0.3126, 0.3534 |
| 256 | 288 | 5 | 32768 | saturated | 0/2 | 0.4231, 0.4428 | — | — |
| 256 | 288 | 5 | 32768 | 50000 | 2/2 | 0.6965, 0.669 | 0.7277, 0.5916 | 0.3713, 0.188 |
| 4096 | 0 | 5 | 32768 | saturated | 0/2 | 1.081, 1.124 | — | — |
| 4096 | 0 | 5 | 32768 | 50000 | 1/2 | 1.048, 0.9988 | 0.002582, 0.002236 | 0.1318, 0.09346 |
| 4096 | 96 | 5 | 32768 | saturated | 1/2 | 1.032, 1.086 | — | — |
| 4096 | 96 | 5 | 32768 | 50000 | 1/2 | 0.9036, 1.36 | 0.002532, 0.003022 | 0.1192, 0.1147 |
| 4096 | 208 | 5 | 32768 | saturated | 0/2 | 1.052, 1.084 | — | — |
| 4096 | 208 | 5 | 32768 | 50000 | 2/2 | 0.9929, 1.119 | 0.0006619, 0.0009765 | 0.0325, 0.03525 |
| 4096 | 288 | 5 | 32768 | saturated | 0/2 | 1.141, 1.113 | — | — |
| 4096 | 288 | 5 | 32768 | 50000 | 2/2 | 1.129, 1.144 | 0.01627, 0.01166 | 0.03606, 0.03653 |

