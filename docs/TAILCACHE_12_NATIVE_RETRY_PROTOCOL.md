# Prospective native host-rejection handling — 5 November 2026

This is declared before the first native calibration, pilot or confirmatory dataset. It does not apply retrospectively to old native or WSL attempts. The Windows-v5 CPU-only policy remains separate.

New native stages may explicitly opt in to at most two extra JVMs per logical slot and eight extra JVMs in total per stage. A logical slot is the frozen condition/channel/pass/fork ordinal. The first quality-passing candidate is selected; a passing candidate can never be replaced. No latency endpoint or backend ranking enters selection. Every rejected candidate, source, host sample and reason remains in the dataset.

Eligible reasons are only the existing native outside-scope CPU upper-bound rejection and/or observed external-power disconnection/change. An unrecognized reason, compiler failure, thermal event, memory/paging disturbance, missing/stale observer, environment/VM/trace mismatch, insufficient exposure, allocation/materialization failure or integrity failure stops the stage. Valid statistical outliers and variance failures never receive replacements.

Each replacement requires a new retained/replayed 120-consecutive-second native quiet preflight (300-second timeout). It must finish after the preceding candidate, share the frozen source and native host environment, and precede the replacement by at most 360 seconds. Expired or failed preparation stops collection. Quota exhaustion, interruption or a partial directory does not authorize deletion or silent replacement. Resuming verifies immutable sources, declarations and raw artifacts; source/environment changes need a new attempt.

Native boot ID, kernel, RAM total, governor, external power, CPU/affinity/tick count and ancestor resource controls are declared before timed collection and checked across blocks. Temporary scope names can differ across stages, but normalized controls and the boot/environment must match qualification references. Gradle remains single-use inside the accounted scope; scheduling/quotas/affinity are not changed.

Replay verifies the canonical slot order, bounded candidate ordinals, immediate same-slot replacements, policy hash, first-passing selection, preflight hashes/source/raw timing and all selected/rejected/missing coverage. Extra candidates after completion, a passing slot or terminal failure reject the dataset. Defaults continue to stop at failure unless a new manifest explicitly declares this policy. This is host-quality handling under a fixed target environment; it is not a best-run selection rule.
