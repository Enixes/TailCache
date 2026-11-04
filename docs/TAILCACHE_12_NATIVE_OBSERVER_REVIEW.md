# Native observer implementation and research review — 5 November 2026

The completion plan preceded this change. New runs use `tailcache12-host-v3-native-cpu` and measurement-source version 3. Old v2 reports replay under their original host/CPU rules and retain their historical source fingerprint; they do not qualify the changed observer.

## Implemented and verified

- A temporary user-owned systemd scope accounts the controller and its descendants, without changing affinity, priority, CPU quota or memory limits. Gradle uses `--no-daemon` for scoped native runs. Each actual benchmark/retention JVM writes setup-only cgroup evidence; replay checks containment and fork counts.
- Raw aggregate CPU ticks, scope CPU microseconds, read brackets, online CPU count and affinity are retained. The outside-scope CPU ceiling uses a conservative upper bound including two clock ticks per CPU and counter-read skew. Scope/resource identity, counter monotonicity, completeness and sampling gaps are validated. CPU acceptance covers the last ten available settling seconds plus measurement; preflight covers its entire interval.
- Native readings retain CPU PSI/load, optional frequencies, temperatures and thermal-throttle counts. Critical temperatures, counter increases, changed controls, restricted affinity, inherited quotas, native memory below 1 GiB and missing required evidence reject. Existing power, memory-PSI, swap/zswap and OOM rules remain in force.
- The first real probe correctly separated inside/outside CPU but rejected an overly strict requirement for a leaf CPU-limit file. Linux exposes `cpu.stat` even where the leaf CPU controller is not enabled. The correction records that absence explicitly and still reads/enforces every ancestor's CPU/memory limit; a regression verifies that a disabled leaf cannot hide an inherited quota. The failed probe is retained.
- Final source-snapshotted probe `native-v3-observer-20261105-003` passed: three bounded inside-scope CPU workers produced a 3.94% outside-CPU upper bound; three sibling-scope workers produced 28.71%, correctly rejected against 10%. Snapshot read wall time was median 4.64 ms, maximum 5.65 ms. These are observer diagnostics, not cache latency measurements or an isolated CPU-cost profile.
- All 34 Java tests and 47 Python tests passed at the observer checkpoint; benchmark and result-tool compilation passed. The retained v2 archive still resolves to fingerprint `866e0d76f0125b716007745824d2e85949a4c78ff9c4db0ef3ba0d4ff84a9888`.

## Critical limitations and prospective next work

Accounting cannot attribute every kernel task or prove absence of contention. CPU outside the scope includes unrelated kernel/interrupt work; the uncertainty bound makes this screen conservative. The current 10% ceiling permits some background activity and will be reviewed through the pilot without retrospective acceptance of rejected data. Missing optional sensors remain explicit; no fixed-frequency or temperature-equivalence claim follows from recording them.

The separate floor study declares two fresh timer replicas and two counterbalanced supply-floor replicas per backend/payload. Timer-median/every-operation-median ceiling is 1/3; supply-median/SampleTime-median ceiling is 1/2 at low pressure. Snapshot median read time ceiling is 10 ms. Pilot data supply six independent primary JVMs per channel/condition for coherence review. Opposite resolved backend directions across timing channels reject coherence; an unresolved interval does not prove equality. Floors are never subtracted from percentiles.

The histogram-derived fraction of wall time outside service intervals is bounded using HDR quantization. It includes recorder/loop work **and real pauses between operations**, so it is descriptive and cannot reject a severe-pressure condition merely because GC increased this fraction. This avoids confusing the phenomenon under study with instrumentation cost.

Fresh functional/pause, full compiler and pressure qualification are required for version 3 before calibration/pilot. A successful controlled CPU probe alone does not qualify these stages or complete Task 12. Dataset acceptance, pressure coverage, observer coherence, replication variance and final protocol freeze remain mandatory.

## Version 4 correction and materialization evidence

The first version-3 functional bundle passed all mechanical checks and 13/14 host screens. The short Caffeine observer block's final CPU fragment was 196 ms: outside CPU estimate 0.41%, conservative upper bound 10.87%. Clock-tick uncertainty dominated this fragment; it was not evidence of a 10% CPU burst. The rejection remains intact and still replays as rejected.

Version 4 uses native observer 2. It validates every raw increment, then merges a final fragment shorter than 800 ms with its preceding interval before calculating CPU bounds. No samples are deleted, counter resets remain invalid, the 10% ceiling is unchanged and old observer-1 data retain the original calculation. Measurement fingerprints distinguish versions 2/3/4 and reproduce the archived historical hashes.

Worker-thread allocated bytes are now read only at iteration boundaries in both channels, after setup and before teardown/integrity allocation. Native replay requires those counters and checks a conservative minimum: writes × payload bytes for Caffeine and the supply floor; operations × payload bytes for ordinary Chronicle reads plus fresh writes. Timer and retention diagnostics have separate modes. These bounds corroborate allocation demand and help detect eliminated materialization; they are not a type-level allocation profile or proof that every copy instruction survives optimization. Separate allocation diagnostics remain necessary.

Every-operation metadata now retain the exact VM name/build and runtime version. Calibration and pilot compare the exact build across recorders. This prevents treating a shared short Java version string as proof of identical JVM builds after moving machines.

At this revision, 34 Java and 52 Python tests pass, including final-fragment merging, raw-reset rejection, preserved legacy rejection and materialization-demand checks. Fresh version-4 functional/compiler qualification is required; version-3 functional characterization cannot qualify it.

`native-v4-observer-20261105-001` passed the source-snapshotted inside/outside CPU probe (upper bounds 4.72% and 28.68%). The first version-4 functional bundle, `native-v4-functional-20261105-001`, passed all mechanical checks and 14/14 host screens, including the new materialization-demand checks.

Boundary review then aligned JMH's useful work with the every-operation loop: both call the common workload and consume the returned array's first byte. JMH additionally blackholes the array reference to protect materialization. Floors remain the explicitly separate trace/fresh-value supply path. This small workload-boundary change requires fresh source-matched functional/compiler evidence; the preceding bundle remains a valid diagnostic of the earlier source, not a prerequisite for the changed boundary.
