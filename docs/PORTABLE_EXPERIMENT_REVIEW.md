# Portable experiment review and validation

18 November 2026. Implementation review by the coding agent, not independent peer
review and not an additional research campaign.

## Delivered scope

The standalone archive freezes the existing continuous-stream ordinary-get workload
and resolved runtime bytes. It replaces the dated build-directory, absolute Java
path and systemd dependencies for **new** collections. A strict configuration
controls the heap, JVM processor budget, seeds, phase durations, payload, retained
application data, write ratio, eligible update population, churn and pacing.
The original measured Java source and all historical acceptance decisions remain
unchanged. The explicit processor budget is a prospective protocol setting; old
host-default runs are not retrospectively described as pinned.

The small locality replication is the first research profile: eight JVMs, about
21 minutes of timed workload plus setup. Write-ratio and original pressure/payload
matrices are explicit options. No research profile was launched during this change.

## Review findings and repairs

- Combining age tracing with GC logging padded the unified-log level field and broke
  the retained parser in the first extracted smoke. Age logs now use their own file,
  matching the old launch convention. The failed diagnostic attempt stays retained.
- The first source-only rebuild exposed a missing resource directory. Source,
  resources, wrapper, build configuration, collector, parser, profiles and tests are
  now included; extraction does not need to preserve shell executable permissions.
- Runtime identity originally covered only selected JDK files. It now hashes the
  launcher, release metadata and files under the runtime's bin/lib/conf directories.
- Java option injection through environment variables is rejected. Heap and JVM
  processor budget are explicit; a flags-only probe records actual ergonomics.
- Completed result receipts are sealed and raw files inventoried. Resume detects
  changed results, source bundle, JDK, host resources or configuration. Interrupted
  slots are retained and block replacement; completed failed outcomes remain visible.
- Offline analysis reconstructs bins, GC and allocation statistics instead of merely
  trusting cached summaries. Independent Java checks verify compressed HDR and the
  logical write stream after collection.
- Zero timer readings, empty update/response histograms, insufficient tail support,
  incomplete pairs and small seed counts stay unresolved where appropriate. A
  zero-valued quantile cannot create a division error or a spurious winner.
- Point conclusions require agreement across all planned seed pairs. Reversal
  brackets compare cells with every other input matched, and do not imply an exact
  or universal crossover. Warning-inclusive and warning-free summaries stay separate.

## Completed checks

- **43 portable behavioral tests passed**, including malformed configurations,
  counterbalancing, phase-scoped paging, CPU/power/throttle events, histogram ranks,
  threshold bounds, empty/zero values, locks, result/raw tampering, missing/failed
  pairs, genuine matched-input reversal detection and resume without new workers.
- **31 existing mechanism tests passed.** Existing scientific analysis was preserved.
- The final ZIP was extracted outside the checkout into a path containing spaces.
  Its included source rebuilt successfully from `/tmp`, using the existing dependency
  cache. The rebuilt **bundle content ID was identical**, and all 30 runtime files
  (JARs and Python modules) matched byte-for-byte. ZIP container bytes differ because
  packaging metadata is not the content identity.
- The exact final archive completed its functional validation, four timing controls
  (two backends, with/without a known pause) and four short diagnostic workers.
  All five compressed histograms per worker/control passed independent decoding.
  Logical replay passed for all diagnostic workload workers.
- Additional bounded diagnostics exercised four-call priming, closed-loop service,
  zero writes/empty histograms, 4 KiB values and a smaller update population:
  **8/8 workers completed**. Those diagnostics and their separate controls remain
  outside research evidence.
- Offline re-analysis worked without Java or access to the original running host.
  Repeating the final smoke command reused completed workers; retained worker and
  control hashes were checked before and after resumption.
- All four canonical datasets (mechanism, predictor, original preprint and
  17 November service extension) retained their previous SHA-256 hashes.

The machine-readable [validation receipt](portable-validation-20261118.json) gives
artifact identities and retained diagnostic evidence locations. The final smoke's
short warmup produced compiler and occasional paging warnings. These were preserved;
installation validation does not establish a clean research dataset.

## Limits before interpreting a fresh research run

Linux is tested here. Windows/macOS launch/path/lock branches are implemented but
not verified on those operating systems; missing native host telemetry is diagnostic.
Chronicle still requires a compatible Java/native platform. Use a full JDK 21 and
Python 3.10+, with the same JDK build where hardware replication is the question.

The JVM processor budget does not bind physical cores or equalize hardware. Host
detection and 1 Hz counters cannot prove absence of interference or causally
attribute paging. External-power and thermal sensors may be unavailable. A per-user
lock coordinates this collector, not unrelated benchmarks or other users. Use local
storage with advisory locking and hard-link support for exclusive receipt publication.

The supplied two-seed screens give paired directions and descriptive spread, not
strong publication-level confidence intervals. Bootstrap intervals require at least
four independent seed pairs and remain exploratory. Rare-tail support flags still
apply: 30 seconds at 50k requests/s gives about 15 observations beyond p99.999.
Longer windows, fresh seeds and independent host replications should be frozen before
a stronger confirmation campaign. There is no automatic outlier removal, pooling,
model refitting or conversion of warning-bearing results into unconditional claims.

Persisted Chronicle cold/open/page-fault experiments, buffer reuse, other collectors
and the historical JMH campaign are separate protocols. This package does not claim
to replace them or to repair the original unconditional Task 12 NO_GO.
