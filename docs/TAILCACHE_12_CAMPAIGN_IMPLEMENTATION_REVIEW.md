# Task 12 implementation and researcher control review — 5 November 2026

This review follows the completion plan and the prospective native retry declaration, before any accepted native calibration or pilot/campaign endpoints. The implementation is ready for source-matched qualification; it is not an accepted research dataset.

## Workload and host validity

Both primary channels now consume the returned first byte. JMH also blackholes the array reference; worker allocation counters corroborate minimum payload allocation at iteration boundaries. The existing functional tests check value parity, fresh immutable writes, entry counts and retained-heap slopes. These checks constrain dead-code elimination but do not prove every copy survives optimization. The retained application heap remains common across backends; total heap occupancy is measured separately rather than equalized.

Native accounting uses a temporary unthrottled scope and single-use Gradle descendants. The launcher now holds a nonblocking repository-wide lock until the command exits. Actual worker cgroup records, raw cumulative CPU counters, complete ancestor controls, RAM/boot/kernel/governor/power and exact VM builds are checked. Scope names may change between stages, while normalized hardware/resource controls must agree. Source changes reject before launching another JVM. New environment-declared functional attempts require host acceptance as well as mechanical acceptance; historical diagnostic interpretations remain separate.

The v4 CPU interval correction retains and validates every raw increment. The new environment baseline represents power violations using the existing explicit host reasons, so the prospective power replacement policy applies to actual replayed failures without hiding a different environment failure. Boot/kernel/memory/control changes remain fatal. Neither a quiet preflight nor a previous compiler screen waives a fork's own checks.

## Replacement and coverage audit

Calibration and pilot integrate the native policy separately from historical Windows-only handling. New native manifests freeze canonical logical slots and the declaration hash before collection. Selection is the first quality pass in fixed order; passing candidates cannot be replaced, skipped or appended after completion. CPU/power-only failures allow at most two extras per slot and eight per stage, with a raw-replayed 120-second quiet prerequisite. Unknown failures, compiler activity, thermal/paging/memory/integrity/materialization/exposure problems stop collection. Valid statistical outliers and between-pass variance receive no replacements. Every candidate remains in the exported coverage table.

## Observer and statistical design

Independent floors are ten fresh JVMs: two counterbalanced supply replicas per backend/payload and two timer replicas. The pilot supplies six independent primary JVMs per channel/condition for coherence. Floors are never subtracted. Time outside service intervals includes real between-call GC/OS pauses, so it is descriptive rather than a pressure rejection. Opposite resolved channel directions reject coherence; overlapping intervals do not prove equality. Floor/pilot sources, native environment, preparation and exact VM must agree.

Campaign freezing requires replayed pilot, variance and coherence gates, and records all source, environment, schedule, prerequisite, analysis and replacement controls before the first primary fork. The full grid has 192 primary JVMs and 128 descriptive diagnostic JVMs. Two counterbalanced passes each contain three fresh paired forks per primary condition/channel. Diagnostic profiler/XML forks never supply primary endpoints. Actual GC counts, durations and post-GC occupancy are retained; eight seconds and 100,000 samples do not establish exposure to rarer unseen pauses.

Statistics use independent forks and passes, never operations or iterations as replicas. Nominal adjusted intervals use 50,000 hierarchical bootstrap resamples with a 32-comparison Bonferroni family alongside descriptive 95% intervals. Two outer passes provide coarse, conditional uncertainty; the adjustment does not make the bootstrap exact or justify broad JVM/hardware claims. Valid variance failures remain unresolved and cannot be converted into a no-crossover conclusion. Missing/unstable coverage blocks a full-range claim.

Seed robustness is a separate experiment on predeclared seeds 0xC0FFEE and 0xBADC0DE. It always covers the tested range endpoints and covers every adjacent point-estimate crossing in either primary channel/endpoint plus its immediate neighbors. This deterministic rule is frozen before primary collection; no seed data are pooled with primary endpoints. A setup-only utility exports deterministic trace fingerprints before any seed experiment.

## Verification and remaining empirical risks

All 62 Python tests and 34 Java tests pass; JMH and result-tool compilation succeeds using the pinned Java 21 toolchain. Tests exercise raw counter failures, versioned legacy replay, allocation demand, bounded replacement selection/preflight ordering, campaign balance, missing/unstable coverage and scope-normalized environment matching. They do not substitute for real native stage replay.

The final qualification sequence is observer probe, 120-second quiet preflight, functional/retention/pause validation, separate two-window pause validation, complete 96-warmup JMH and every-operation screens, matching pressure96 diagnostic and independent floors. It stops on any failure and records each completed raw-replayed stage. No source or document edits are permitted while a stage is collecting. After reviewing qualification, calibration and pilot must still pass; only then can the confirmatory protocol be frozen.

The campaign and export controls have not yet been exercised with a real complete dataset. Potential problems remain empirical: sustainable severe pressure, replica occupancy drift, compiler stability, achievable churn, floor dominance, channel coherence, rare-pause exposure and run-to-run variance. A demonstrated failure requires diagnosis and a new prospective declaration; no gate is bypassed to finish. The exporter verifies all archived bytes and leaves taskComplete false until final researcher review. The recovery timer remains enabled until the final status is genuinely complete.
