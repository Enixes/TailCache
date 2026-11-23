# Portable experiment implementation plan

18 November 2026. This is a new collection tool, separate from the completed dated cohorts.

1. Package the unchanged continuous-stream mechanism workload, functional checks,
   independent HDR verifier and pinned runtime dependencies. Build once with the
   Gradle wrapper; move the resulting ZIP without a checkout or Gradle on the target.
2. Freeze a versioned JSON configuration before collection. Supply a small locality
   replication first, plus explicit pressure/payload/service-response and write-ratio
   profiles. Show JVM count and approximate duration before running. Never resize the
   experimental heap automatically to match host RAM.
3. Discover Java 21 through an explicit path, JAVA_HOME or PATH. Record/hash the JDK,
   executable bundle, CPU/OS, available memory, cgroup limits, mount/storage and power
   information. Avoid systemd, old build directories and machine-specific paths.
4. Run one JVM at a time under an OS lock. Resume only completed hash-verified slots
   on the original machine/runtime. Preserve interrupted/failed slots; do not replace
   them automatically. Controls and smoke runs remain outside research observations.
5. Record Linux host/process observations at 1 Hz. Screen conditioning/measurement
   intervals separately from whole-lifetime events. Missing telemetry is explicit;
   non-Linux or containerized collection is diagnostic rather than silently clean.
   Genuine cache/GC pressure outcomes remain outcomes, not exclusion reasons.
6. Verify compressed HDR distributions against CSV bins and workload conservation.
   Report all five channels through p99.999, tail-count support, bounded threshold
   exceedance rates, GC/safepoints, allocation, achieved churn, RSS, per-fork results,
   paired ratios and independent-seed variability. Never pool fork histograms or
   machines. Show warning-inclusive and clean-pair summaries separately.
7. Test malformed configs, deterministic scheduling, locks, resumption/corruption,
   phase-scoped gates, histogram edge cases and statistics. Build the movable package,
   extract outside the checkout, and run only a short functional/control smoke.
   Review the implementation and document supported hosts and remaining limitations.

Same configuration means matched experimental inputs, not identical hardware or
performance. The package studies in-memory ordinary get; persisted cold/open and
buffer reuse remain separate experiments. Model fitting and claims about universal
crossover thresholds are outside this portability change.
