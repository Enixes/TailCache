# Mechanism experiments — 18 November 2026

Every completed comparison is retained separately. Values below are scheduled-response latency, not saturated service. Development choices, paired treatment screens, repeats and fresh confirmation have different evidence roles. Warnings and collector failures are retained.

## Frozen decisions

- **headroom-worth**: `{"expand":true,"tests":[{"writeBps":50,"gcRatio":0.7846403886528371,"winnerReversal":false},{"writeBps":500,"gcRatio":0.6126181892437236,"winnerReversal":false}],"rule":"Any ranking reversal or both Caffeine cells GC exposure reduce>=20%"}`
- **hotset-worth**: `{"expand":true,"tests":[{"seed":54821,"gcRatio":0.16930093844545613,"winnerReversal":true},{"seed":54822,"gcRatio":0.15192726879204604,"winnerReversal":true}],"rule":"Both seeds Caffeine GC overlap reduce>=20% or any seed ranking reversal"}`
- **logging-choice**: `{"logging":"async","asyncLogsComplete":true,"metrics":{"CAFFEINE":{"sync":172291.75,"async":145128.0},"CHRONICLE_IN_MEMORY":{"sync":147739.5,"async":118780.75}},"rule":"At least10% median excess reduction for one backend, no>10% increase for other; no log drops"}`
- **priming-choice**: `{"primeCalls":0,"compilerWarningCounts":{"0":1,"4":0},"rule":"At least two fewer>80ms warnings out of four backend/seed observations"}`

## Every paired data point

| Cohort | Seed / repeat | Writes % | Payload B | Update keys | Heap MiB | Logging / priming | p99.9 Caffeine µs | Chronicle µs | Ch/C p99.9 | p99.99 | p99.999 | Conclusion |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| headroom-confirm | 54842 / 1 | 0.5 | 4096 | 32768 | 1024 | async / 0 | 162.559 | 21.567 | 0.1327 | 0.0899 | 0.0983 | Chronicle lower; warnings |
| headroom-confirm | 54842 / 1 | 5 | 4096 | 32768 | 1024 | async / 0 | 14860.287 | 23.647 | 0.0016 | 0.0687 | 0.0812 | Chronicle lower |
| headroom-confirm | 54842 / 1 | 0.5 | 4096 | 32768 | 512 | async / 0 | 65.983 | 131.455 | 1.9923 | 0.1608 | 0.1474 | Caffeine lower; GC failure |
| headroom-confirm | 54842 / 1 | 5 | 4096 | 32768 | 512 | async / 0 | 9109.503 | 222.847 | 0.0245 | 0.1142 | 0.1268 | Chronicle lower; warnings |
| headroom-screen | 54841 / 1 | 0.5 | 4096 | 32768 | 1024 | async / 0 | 1075.199 | 23.839 | 0.0222 | 0.1090 | 0.1113 | Chronicle lower; warnings |
| headroom-screen | 54841 / 1 | 5 | 4096 | 32768 | 1024 | async / 0 | 12566.527 | 25.039 | 0.0020 | 0.0731 | 0.0816 | Chronicle lower; warnings |
| headroom-screen | 54841 / 1 | 0.5 | 4096 | 32768 | 512 | async / 0 | 1976.319 | 132.351 | 0.0670 | 0.1523 | 0.1411 | Chronicle lower; warnings; GC failure |
| headroom-screen | 54841 / 1 | 5 | 4096 | 32768 | 512 | async / 0 | 8798.207 | 75.135 | 0.0085 | 0.1025 | 0.1159 | Chronicle lower; warnings |
| hotset-repeat | 54821 / 2 | 5 | 4096 | 2048 | 512 | async / 0 | 26.463 | 244.095 | 9.2240 | 0.3896 | 0.3849 | Caffeine lower; warnings |
| hotset-repeat | 54822 / 2 | 5 | 4096 | 2048 | 512 | async / 0 | 24.751 | 172.031 | 6.9505 | 0.3710 | 0.3740 | Caffeine lower; warnings |
| hotset-repeat | 54821 / 2 | 5 | 4096 | 32768 | 512 | async / 0 | 9076.735 | 161.791 | 0.0178 | 0.1127 | 0.1242 | Chronicle lower |
| hotset-repeat | 54822 / 2 | 5 | 4096 | 32768 | 512 | async / 0 | 8904.703 | 133.503 | 0.0150 | 0.1102 | 0.1276 | Chronicle lower; warnings |
| hotset-screen | 54821 / 1 | 5 | 4096 | 2048 | 512 | async / 0 | 28.063 | 74.815 | 2.6660 | 0.3466 | 0.3710 | Caffeine lower; warnings |
| hotset-screen | 54822 / 1 | 5 | 4096 | 2048 | 512 | async / 0 | 25.535 | 134.527 | 5.2683 | 0.3784 | 0.3598 | Caffeine lower; warnings |
| hotset-screen | 54821 / 1 | 5 | 4096 | 32768 | 512 | async / 0 | 9699.327 | 226.559 | 0.0234 | 0.1079 | 0.1207 | Chronicle lower; warnings |
| hotset-screen | 54822 / 1 | 5 | 4096 | 32768 | 512 | async / 0 | 9183.231 | 125.375 | 0.0137 | 0.1068 | 0.1151 | Chronicle lower; warnings |
| logging | 54801 / 1 | 0.5 | 4096 | 32768 | 512 | async / 0 | 269.055 | 141.439 | 0.5257 | 0.1582 | 0.1502 | Chronicle lower; warnings; GC failure |
| logging | 54802 / 1 | 0.5 | 4096 | 32768 | 512 | async / 0 | 2854.911 | 158.463 | 0.0555 | 0.1414 | 0.1362 | Chronicle lower; warnings; GC failure |
| logging | 54801 / 1 | 0.5 | 4096 | 32768 | 512 | sync / 0 | 1040.895 | 480.767 | 0.4619 | 0.3524 | 0.3437 | Chronicle lower; warnings; GC failure |
| logging | 54802 / 1 | 0.5 | 4096 | 32768 | 512 | sync / 0 | 1496.063 | 173.567 | 0.1160 | 0.1520 | 0.1523 | Chronicle lower; warnings; GC failure |
| payload | 54851 / 1 | 0 | 256 | 32768 | 512 | async / 0 | 22.127 | 17.567 | 0.7939 | 0.1615 | 0.2282 | Chronicle lower |
| payload | 54851 / 1 | 5 | 256 | 32768 | 512 | async / 0 | 23.599 | 17.295 | 0.7329 | 0.1832 | 0.2302 | Chronicle lower; warnings |
| payload | 54851 / 1 | 0 | 4096 | 32768 | 512 | async / 0 | 18.879 | 93.183 | 4.9358 | 0.8219 | 0.6358 | Caffeine lower |
| payload | 54851 / 1 | 5 | 4096 | 32768 | 512 | async / 0 | 8912.895 | 93.887 | 0.0105 | 0.1054 | 0.1210 | Chronicle lower; warnings |
| priming | 54811 / 1 | 0.5 | 4096 | 32768 | 512 | async / 0 | 1401.855 | 135.423 | 0.0966 | 0.1530 | 0.1409 | Chronicle lower; warnings; GC failure |
| priming | 54812 / 1 | 0.5 | 4096 | 32768 | 512 | async / 0 | 836.607 | 166.655 | 0.1992 | 0.1986 | 0.1693 | Chronicle lower; warnings; GC failure |
| priming | 54811 / 1 | 0.5 | 4096 | 32768 | 512 | async / 4 | 40.991 | 50.335 | 1.2280 | 0.1956 | 0.2272 | Caffeine lower; warnings; GC failure |
| priming | 54812 / 1 | 0.5 | 4096 | 32768 | 512 | async / 4 | 1057.791 | 88.831 | 0.0840 | 0.1636 | 0.1494 | Chronicle lower; warnings; GC failure |
| transition | 54831 / 1 | 0.5 | 4096 | 32768 | 512 | async / 0 | 1806.335 | 62.239 | 0.0345 | 0.1433 | 0.1390 | Chronicle lower; warnings; GC failure |
| transition | 54831 / 2 | 0.5 | 4096 | 32768 | 512 | async / 0 | 1136.639 | 64.799 | 0.0570 | 0.1634 | 0.1498 | Chronicle lower; warnings; GC failure |
| transition | 54832 / 1 | 0.5 | 4096 | 32768 | 512 | async / 0 | 1138.687 | 65.663 | 0.0577 | 0.1385 | 0.1260 | Chronicle lower; warnings; GC failure |
| transition | 54832 / 2 | 0.5 | 4096 | 32768 | 512 | async / 0 | 1624.063 | 58.719 | 0.0362 | 0.1483 | 0.1314 | Chronicle lower; warnings; GC failure |

## Conditional response model / baseline comparison

All rows retain warnings and near-budget outcomes. Logging/priming are development; other cohorts are separately identified transport tests. The simple lower-total-GC rule is scored even when a fixed-cost model misses. 256B is outside numerical calibration.

| Cohort | Model | p99.9 correct / pairs | Abstentions | Median absolute error µs | Median relative error % |
| --- | --- | ---: | ---: | ---: | ---: |
| headroom-confirm | M0 | 2/4 | 2 | 147.007 | 100.00 |
| headroom-confirm | M1 | 3/4 | 0 | 130.734 | 52.83 |
| headroom-confirm | M2 | 3/4 | 0 | 115.445 | 40.16 |
| headroom-confirm | M3core | 3/4 | 0 | 95.673 | 32.97 |
| headroom-confirm | M3total | 3/4 | 0 | 88.433 | 32.39 |
| headroom-confirm | constant | 3/4 | 0 | 339.488 | 220.40 |
| headroom-confirm | alwaysCaffeine | 1/4 | 0 | — | — |
| headroom-confirm | alwaysChronicle | 3/4 | 0 | — | — |
| headroom-confirm | lowerTotalGc | 4/4 | 0 | — | — |
| headroom-screen | M0 | 4/4 | 0 | 260.874 | 83.85 |
| headroom-screen | M1 | 4/4 | 0 | 244.601 | 32.07 |
| headroom-screen | M2 | 4/4 | 0 | 181.077 | 31.16 |
| headroom-screen | M3core | 4/4 | 0 | 151.937 | 31.16 |
| headroom-screen | M3total | 4/4 | 0 | 113.569 | 28.85 |
| headroom-screen | constant | 4/4 | 0 | 232.752 | 88.13 |
| headroom-screen | alwaysCaffeine | 0/4 | 0 | — | — |
| headroom-screen | alwaysChronicle | 4/4 | 0 | — | — |
| headroom-screen | lowerTotalGc | 4/4 | 0 | — | — |
| hotset-repeat | M0 | 2/4 | 2 | 166.911 | 100.00 |
| hotset-repeat | M1 | 4/4 | 0 | 150.319 | 63.64 |
| hotset-repeat | M2 | 4/4 | 0 | 117.298 | 49.00 |
| hotset-repeat | M3core | 4/4 | 0 | 93.185 | 42.29 |
| hotset-repeat | M3total | 4/4 | 0 | 90.497 | 41.26 |
| hotset-repeat | constant | 2/4 | 0 | 401.744 | 67.54 |
| hotset-repeat | alwaysCaffeine | 2/4 | 0 | — | — |
| hotset-repeat | alwaysChronicle | 2/4 | 0 | — | — |
| hotset-repeat | lowerTotalGc | 4/4 | 0 | — | — |
| hotset-screen | M0 | 2/4 | 2 | 129.951 | 100.00 |
| hotset-screen | M1 | 4/4 | 0 | 113.359 | 60.49 |
| hotset-screen | M2 | 4/4 | 0 | 111.082 | 50.30 |
| hotset-screen | M3core | 4/4 | 0 | 89.741 | 43.19 |
| hotset-screen | M3total | 4/4 | 0 | 88.253 | 43.19 |
| hotset-screen | constant | 2/4 | 0 | 392.176 | 88.70 |
| hotset-screen | alwaysCaffeine | 2/4 | 0 | — | — |
| hotset-screen | alwaysChronicle | 2/4 | 0 | — | — |
| hotset-screen | lowerTotalGc | 4/4 | 0 | — | — |
| logging | M0 | 3/4 | 1 | 245.713 | 73.13 |
| logging | M1 | 3/4 | 0 | 229.439 | 65.54 |
| logging | M2 | 3/4 | 0 | 197.662 | 54.84 |
| logging | M3core | 4/4 | 0 | 162.113 | 42.25 |
| logging | M3total | 4/4 | 0 | 135.905 | 38.17 |
| logging | constant | 4/4 | 0 | 329.280 | 40.99 |
| logging | alwaysCaffeine | 0/4 | 0 | — | — |
| logging | alwaysChronicle | 4/4 | 0 | — | — |
| logging | lowerTotalGc | 3/4 | 0 | — | — |
| payload | M0 | 1/2 | 1 | 93.535 | 100.00 |
| payload | M1 | 2/2 | 0 | 76.942 | 48.84 |
| payload | M2 | 2/2 | 0 | 76.740 | 48.67 |
| payload | M3core | 2/2 | 0 | 76.740 | 48.67 |
| payload | M3total | 2/2 | 0 | 76.740 | 48.67 |
| payload | constant | 1/2 | 0 | 375.520 | 70.32 |
| payload | alwaysCaffeine | 1/2 | 0 | — | — |
| payload | alwaysChronicle | 1/2 | 0 | — | — |
| payload | lowerTotalGc | 2/2 | 0 | — | — |
| priming | M0 | 3/4 | 1 | 151.039 | 100.00 |
| priming | M1 | 4/4 | 0 | 134.446 | 64.06 |
| priming | M2 | 4/4 | 0 | 124.894 | 63.88 |
| priming | M3core | 4/4 | 0 | 93.201 | 59.23 |
| priming | M3total | 4/4 | 0 | 86.913 | 57.43 |
| priming | constant | 3/4 | 0 | 100.208 | 39.92 |
| priming | alwaysCaffeine | 1/4 | 0 | — | — |
| priming | alwaysChronicle | 3/4 | 0 | — | — |
| priming | lowerTotalGc | 3/4 | 0 | — | — |
| transition | M0 | 4/4 | 0 | 221.379 | 67.63 |
| transition | M1 | 4/4 | 0 | 205.105 | 52.80 |
| transition | M2 | 4/4 | 0 | 151.317 | 47.60 |
| transition | M3core | 4/4 | 0 | 135.446 | 46.19 |
| transition | M3total | 4/4 | 0 | 108.309 | 43.56 |
| transition | constant | 4/4 | 0 | 246.032 | 85.50 |
| transition | alwaysCaffeine | 0/4 | 0 | — | — |
| transition | alwaysChronicle | 4/4 | 0 | — | — |
| transition | lowerTotalGc | 4/4 | 0 | — | — |

## Limits

- One host; G1; paced ordinary get; no pooled quantiles.
- Logging and priming select settings and are development cohorts.
- Repeat hotset seeds are repeatability, not fresh validation.
- Models condition on observed pauses; new costs were never fitted.
- 256B has no old-cost numerical calibration.
- Warnings/evacuation failures remain intrinsic evidence; completion does not imply steady-state qualification.

Portable data: [mechanism-data-20261118.json](mechanism-data-20261118.json). Arithmetic verification: [portable-verification.json](portable-verification.json). Frozen protocol: [plan](../TAILCACHE_MECHANISM_PLAN.md). Research interpretation must keep negative and mixed effects.
