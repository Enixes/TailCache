# Second-host raw evidence

These archives contain the run protocols and measurements for the TailCache
campaigns collected on 20 November 2026. The [archive manifest](MANIFEST.json)
records SHA-256 checksums, original source commits and manifest hashes, fork
counts, and the corresponding derived reports.

| Archive | Research JVMs | Retry JVMs | Diagnostic JVMs | Timing controls |
|---|---:|---:|---:|---:|
| [Standalone smoke](smoke.tar.xz) | 0 | 0 | 4 | 4 |
| [Locality replication](locality.tar.xz) | 8 | 0 | 4 | 8 |
| [Write-ratio sweep](followups-01-write-ratio.tar.xz) | 20 | 0 | 4 | 8 |
| [Long locality confirmation](followups-01-locality-long.tar.xz) | 16 | 0 | 4 | 8 |
| [Payload and pressure matrix](followups-01-rq-matrix.tar.xz) | 64 | 0 | 4 | 8 |
| [Pressure and write preflight](pressure-write-02-preflight.tar.xz) | 0 | 0 | 4 | 4 |
| [Saturated observer pilot](pressure-write-02-saturated-pilot.tar.xz) | 0 | 0 | 4 | 4 |
| [Saturated write and pressure](pressure-write-02-saturated-write-pressure.tar.xz) | 96 | 2 | 4 | 8 |
| [Scheduled-response write transition](pressure-write-02-write-transition.tar.xz) | 48 | 0 | 4 | 8 |
| **Total** | **252** | **2** | **36** | **60** |

Each phase includes binary HDR histograms, raw histogram bins, GC and age
logs, measurement windows, host samples, stall records, and stream evidence.
Retry attempts are in `external-retry/`. First-pass observations and warnings
are in `slots/`.

Measurement files are byte-for-byte copies. The archived manifests retain the
frozen workload and schedule and omit machine-specific metadata such as the
boot ID, filesystem inventory, and JDK installation path. Worker configuration
paths are rewritten to `<repo>/`. The archived receipts and seals cover the
files in the archive. Each phase's `source-digests.json` records the original
receipt and configuration hashes, and the original run and results hashes
match the [collection manifest](../MANIFEST.json). Launcher output, process
records, build bundles, and full host inventories stay in the source collection
on the original host.

## Verify and reconstruct

From the repository root, run the offline verifier with Python 3.10 or later.
It checks the archive and slot digests, recomputes latency percentiles and GC
summaries from raw data, and compares the regenerated results with the tracked
percentile tables, point conclusions, and retry comparisons.

```sh
python3 scripts/tailcache_verify_archive.py
```

To keep a reconstructed report for one phase, extract its archive and run the
portable analyzer.

```sh
work=$(mktemp -d)
tar -xf docs/second-host-20261120/archive/pressure-write-02-write-transition.tar.xz -C "$work"
python3 scripts/tailcache_portable.py analyze --run "$work/research" --out "$work/report"
```

Both commands run offline and require neither a JDK nor new benchmark forks.
