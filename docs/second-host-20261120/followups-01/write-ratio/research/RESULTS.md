# Portable experiment results

20/20 successful slots; 0 failed; 0 missing.

Chronicle/Caffeine ratios below 1 favor Chronicle. Fork quantiles are never pooled.
Warning-free and all-usable results are separate. Tail support flags are in percentiles.csv.

| Cell | Channel | Percentile | Pairs | Median ratio | Range | Clean pairs |
|---|---|---:|---:|---:|---|---:|
| 1 | service | 99 | 2 | 2.52 | 1.264–3.775 | 1 |
| 1 | service | 99.9 | 2 | 2.91 | 1.588–4.233 | 1 |
| 1 | service | 99.99 | 2 | 4.122 | 1.189–7.055 | 1 |
| 1 | service | 99.999 | 2 | 216.5 | 204.4–228.6 | 1 |
| 1 | response | 99 | 2 | 2.479 | 1.273–3.685 | 1 |
| 1 | response | 99.9 | 2 | 3.051 | 1.681–4.421 | 1 |
| 1 | response | 99.99 | 2 | 1.949 | 1.924–1.973 | 1 |
| 1 | response | 99.999 | 2 | 0.6442 | 0.6403–0.6482 | 1 |
| 2 | service | 99 | 2 | 1.413 | 1.402–1.425 | 1 |
| 2 | service | 99.9 | 2 | 1.171 | 1.159–1.183 | 1 |
| 2 | service | 99.99 | 2 | 1.102 | 1.075–1.129 | 1 |
| 2 | service | 99.999 | 2 | 33.89 | 1.693–66.08 | 1 |
| 2 | response | 99 | 2 | 1.448 | 1.425–1.471 | 1 |
| 2 | response | 99.9 | 2 | 10.59 | 1.046–20.14 | 1 |
| 2 | response | 99.99 | 2 | 1.851 | 0.1352–3.567 | 1 |
| 2 | response | 99.999 | 2 | 1.407 | 0.116–2.698 | 1 |
| 3 | service | 99 | 2 | 0.9498 | 0.7981–1.101 | 1 |
| 3 | service | 99.9 | 2 | 1.12 | 1.054–1.186 | 1 |
| 3 | service | 99.99 | 2 | 0.9942 | 0.9507–1.038 | 1 |
| 3 | service | 99.999 | 2 | 57.81 | 56.1–59.52 | 1 |
| 3 | response | 99 | 2 | 1.111 | 1.109–1.113 | 1 |
| 3 | response | 99.9 | 2 | 0.9562 | 0.8932–1.019 | 1 |
| 3 | response | 99.99 | 2 | 0.1136 | 0.1082–0.1189 | 1 |
| 3 | response | 99.999 | 2 | 0.1089 | 0.1068–0.1111 | 1 |
| 4 | service | 99 | 2 | 1.148 | 1.147–1.149 | 2 |
| 4 | service | 99.9 | 2 | 1.154 | 1.133–1.175 | 2 |
| 4 | service | 99.99 | 2 | 1.255 | 0.9153–1.594 | 2 |
| 4 | service | 99.999 | 2 | 56.08 | 39.54–72.62 | 2 |
| 4 | response | 99 | 2 | 1.148 | 1.147–1.149 | 2 |
| 4 | response | 99.9 | 2 | 0.004184 | 0.002316–0.006051 | 2 |
| 4 | response | 99.99 | 2 | 0.05913 | 0.02449–0.09377 | 2 |
| 4 | response | 99.999 | 2 | 0.0647 | 0.02819–0.1012 | 2 |
| 5 | service | 99 | 2 | 1.128 | 1.122–1.134 | 1 |
| 5 | service | 99.9 | 2 | 1.212 | 1.041–1.384 | 1 |
| 5 | service | 99.99 | 2 | 1.084 | 1.044–1.124 | 1 |
| 5 | service | 99.999 | 2 | 67.33 | 60.88–73.78 | 1 |
| 5 | response | 99 | 2 | 1.113 | 1.1–1.126 | 1 |
| 5 | response | 99.9 | 2 | 0.002837 | 0.002634–0.00304 | 1 |
| 5 | response | 99.99 | 2 | 0.09618 | 0.095–0.09737 | 1 |
| 5 | response | 99.999 | 2 | 0.1124 | 0.1105–0.1144 | 1 |

## Point conclusions

| Cell | Channel | Percentile | Caffeine median ns | Chronicle median ns | All planned pairs favor | Thin tail support |
|---|---|---:|---:|---:|---|---|
| 1 | service | 99 | 1002.0 | 2499.5 | CAFFEINE | False |
| 1 | service | 99.9 | 1152.5 | 3302.0 | CAFFEINE | False |
| 1 | service | 99.99 | 2069.5 | 8397.0 | CAFFEINE | False |
| 1 | service | 99.999 | 2695.0 | 582143.0 | CAFFEINE | True |
| 1 | response | 99 | 1038.0 | 2550.5 | CAFFEINE | False |
| 1 | response | 99.9 | 1347.0 | 3992.0 | CAFFEINE | False |
| 1 | response | 99.99 | 278655.0 | 542719.0 | CAFFEINE | False |
| 1 | response | 99.999 | 1112575.0 | 716799.0 | CHRONICLE_IN_MEMORY | True |
| 2 | service | 99 | 1067.0 | 1508.0 | CAFFEINE | False |
| 2 | service | 99.9 | 5543.0 | 6493.0 | CAFFEINE | False |
| 2 | service | 99.99 | 7251.0 | 8013.0 | CAFFEINE | False |
| 2 | service | 99.999 | 8385.0 | 316019.0 | CAFFEINE | True |
| 2 | response | 99 | 1114.5 | 1613.5 | CAFFEINE | False |
| 2 | response | 99.9 | 6387.0 | 67631.0 | CAFFEINE | False |
| 2 | response | 99.99 | 3755007.0 | 6907519.0 | UNRESOLVED | False |
| 2 | response | 99.999 | 5814271.0 | 8279039.0 | UNRESOLVED | True |
| 3 | service | 99 | 4771.0 | 4615.0 | UNRESOLVED | False |
| 3 | service | 99.9 | 6083.0 | 6803.0 | CAFFEINE | False |
| 3 | service | 99.99 | 7661.0 | 7597.0 | UNRESOLVED | False |
| 3 | service | 99.999 | 8787.0 | 507519.0 | CAFFEINE | True |
| 3 | response | 99 | 5379.0 | 5977.0 | CAFFEINE | False |
| 3 | response | 99.9 | 7509.0 | 7141.0 | UNRESOLVED | False |
| 3 | response | 99.99 | 4669439.0 | 528511.0 | CHRONICLE_IN_MEMORY | False |
| 3 | response | 99.999 | 6529023.0 | 710911.0 | CHRONICLE_IN_MEMORY | True |
| 4 | service | 99 | 5387.0 | 6183.0 | CAFFEINE | False |
| 4 | service | 99.9 | 6295.0 | 7265.0 | CAFFEINE | False |
| 4 | service | 99.99 | 7731.0 | 9311.0 | UNRESOLVED | False |
| 4 | service | 99.999 | 10783.0 | 552191.0 | CAFFEINE | True |
| 4 | response | 99 | 5439.0 | 6243.0 | CAFFEINE | False |
| 4 | response | 99.9 | 2578431.0 | 8301.0 | CHRONICLE_IN_MEMORY | False |
| 4 | response | 99.99 | 13969407.0 | 543743.0 | CHRONICLE_IN_MEMORY | False |
| 4 | response | 99.999 | 15915007.0 | 708095.0 | CHRONICLE_IN_MEMORY | True |
| 5 | service | 99 | 5487.0 | 6189.0 | CAFFEINE | False |
| 5 | service | 99.9 | 6419.0 | 7783.0 | CAFFEINE | False |
| 5 | service | 99.99 | 8009.0 | 8713.0 | CAFFEINE | False |
| 5 | service | 99.999 | 9627.0 | 641535.0 | CAFFEINE | True |
| 5 | response | 99 | 5619.0 | 6253.0 | CAFFEINE | False |
| 5 | response | 99.9 | 3075071.0 | 8725.0 | CHRONICLE_IN_MEMORY | False |
| 5 | response | 99.99 | 5738495.0 | 551935.0 | CHRONICLE_IN_MEMORY | False |
| 5 | response | 99.999 | 6381567.0 | 717567.0 | CHRONICLE_IN_MEMORY | True |

## Matched-input contrasts

These are descriptive observed brackets, with warning-bearing evidence retained. A missing bracket is inconclusive.
No adjacent fully observed ranking reversal is resolved in this run.
