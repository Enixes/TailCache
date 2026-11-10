# Derived result tables

Generated from `paper-data.json`. All ranges span individual forks; they are not confidence intervals. Ratios use paired quantiles, never pooled histograms.

## Fresh primary scheduled response p99.9

| Ballast (MiB) | Caffeine range (µs) | Chronicle range (µs) | Paired Ch/C ratios | Clean pairs / all pairs |
| --- | --- | --- | --- | --- |
| 0 | 23.823–33.183 | 281.855–325.119 | 11.473570, 8.493958, 13.647274 | 3/3 |
| 104 | 33.311–426.239 | 153.343–283.135 | 0.426941, 0.446545, 8.499745 | 1/3 |
| 208 | 921.087–1188.863 | 239.231–334.335 | 0.214728, 0.362979, 0.259474 | 3/3 |

## Historical 256 B saturated service — earlier runtime only

Batch `focused-rq2-256-20261108-001`, ordinary get, 512 MiB G1 heap, 8 s measured windows. All selected pairs are warning-free. This is not the fresh scheduled-response protocol.

| Ballast (MiB) | Endpoint | Three paired Ch/C ratios | Direction |
| --- | --- | --- | --- |
| 448 | p99 | 0.948798, 0.878496, 0.890267 | Chronicle lower |
| 448 | p99.9 | 0.635379, 0.633563, 0.627916 | Chronicle lower |
| 448 | p99.99 | 1.533782, 1.580802, 1.474783 | Caffeine lower |
| 448 | p99.999 | 43.166430, 42.746416, 43.053192 | Caffeine lower |
| 480 | p99 | 0.778723, 0.800156, 0.855539 | Chronicle lower |
| 480 | p99.9 | 1.373694, 1.186423, 1.496975 | Caffeine lower |
| 480 | p99.99 | 3.373889, 2.835974, 5.710785 | Caffeine lower |
| 480 | p99.999 | 0.799849, 0.859388, 0.899918 | Chronicle lower |

## Historical 4 KiB saturated service — runtime groups preserved

Ordinary get, 8 s measured windows. Each row is three pairs at one point; no cross-runtime interpolation. All selected forks are warning-free. Runtime fingerprints are the historical class-set fingerprints, not the fresh all-runtime-file digest.

| Ballast (MiB) | Historical runtime fingerprint | Endpoint | Three paired Ch/C ratios | Direction |
| --- | --- | --- | --- | --- |
| 328 | `57346dc1b2a8` | p99 | 1.116756, 1.121713, 1.099796 | Caffeine lower |
| 328 | `57346dc1b2a8` | p99.9 | 1.304634, 1.299368, 1.269335 | Caffeine lower |
| 328 | `57346dc1b2a8` | p99.99 | 1.431199, 1.499637, 1.407021 | Caffeine lower |
| 328 | `57346dc1b2a8` | p99.999 | 0.902146, 0.903846, 0.918782 | Chronicle lower |
| 352 | `57346dc1b2a8` | p99 | 1.416138, 1.102908, 1.095889 | Caffeine lower |
| 352 | `57346dc1b2a8` | p99.9 | 1.656357, 1.320863, 1.283868 | Caffeine lower |
| 352 | `57346dc1b2a8` | p99.99 | 2.672138, 2.537647, 2.391980 | Caffeine lower |
| 352 | `57346dc1b2a8` | p99.999 | 0.080630, 0.084519, 0.079545 | Chronicle lower |
| 360 | `57346dc1b2a8` | p99 | 1.090054, 1.092271, 1.083344 | Caffeine lower |
| 360 | `57346dc1b2a8` | p99.9 | 1.226073, 1.284814, 1.274939 | Caffeine lower |
| 360 | `57346dc1b2a8` | p99.99 | 2.472886, 2.508529, 2.563656 | Caffeine lower |
| 360 | `57346dc1b2a8` | p99.999 | 0.077098, 0.080731, 0.075334 | Chronicle lower |
| 364 | `cd0ca17ea71a` | p99 | 1.396119, 1.077980, 1.354718 | Caffeine lower |
| 364 | `cd0ca17ea71a` | p99.9 | 1.611234, 1.277296, 1.586273 | Caffeine lower |
| 364 | `cd0ca17ea71a` | p99.99 | 2.818375, 2.497664, 2.732502 | Caffeine lower |
| 364 | `cd0ca17ea71a` | p99.999 | 0.074840, 0.076345, 0.073849 | Chronicle lower |
| 368 | `cd0ca17ea71a` | p99 | 1.077660, 1.079842, 1.080866 | Caffeine lower |
| 368 | `cd0ca17ea71a` | p99.9 | 1.273175, 1.258477, 1.281850 | Caffeine lower |
| 368 | `cd0ca17ea71a` | p99.99 | 2.050738, 1.964707, 1.708041 | Caffeine lower |
| 368 | `cd0ca17ea71a` | p99.999 | 0.076704, 0.073723, 0.073478 | Chronicle lower |
