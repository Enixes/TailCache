# TailCache 08 — implementation and researcher review

## Decision

The six-condition, two-order single-JVM validation layout completed on 2026-10-04, with unprofiled SampleTime and throughput forks and separate OS/JIT and JFR forks. **No 08 result is reportable.** The run used one one-second warmup, one one-second measurement, and one fork per block to validate the pipeline under a pressured host. The default runner retains the planned eight/five iterations and two primary forks for a future quiet-host candidate. The `quality.json` result is `rejected`; it must not be read as a backend ranking.

## Raw evidence and repairs

- `scripts/tailcache08.py` writes a manifest with hashes of every raw file, machine and storage snapshots before/after each block, Gradle capture, raw JMH JSON/text, diagnostic OS CSVs, JFR recordings, `summary.csv`, and `quality.json`. It refuses an existing run ID. `--audit-only` recalculates derived files without rerunning or altering raw files.
- The first audit looked for workload setup lines in JMH's `-o` text file, while fork `System.out` was actually in the Gradle capture. That audit defect was repaired and the unchanged raw run was audited again. The final rejection reasons are four block-variance failures and the deliberately short validation duration/fork count. The repaired audit verifies the same trace SHA-256, disabled Chronicle analytics, and logged tiering policy in every block.
- JMH JSON records `-Xms512m -Xmx512m`, G1, Java 21, the analytics flag, backend/payload factors, and unprofiled versus JFR/OS/compiler mode. The filesystem was ext4 on `/dev/sda2` with `rw,noatime`; `lsblk` reported a nonrotating SATA disk. These describe the host, not proof of steady-state residency.
- This validation ran from an uncommitted working tree. Its environment files retained the Git HEAD and changed-file names, but not an exact source snapshot. The runner now archives its benchmark source and checks a source hash before and after every future block. This validation's exact source provenance remains limited, another reason it cannot be promoted.

## Construct validity and confounders

1. The workload is a one-worker, uniform, all-hit, 95/5 read/existing-key-put access-cost baseline at 2,048 populated and 4,096 configured entries. Its replacement-value bank keeps substantial payload data on heap for Chronicle, so it cannot answer RQ1/RQ2's live-heap or GC-tail crossover. The mixed percentile is not a read-only percentile. The three backends also differ in serialization and persisted checksums by construction.
2. Caffeine and Chronicle in-memory are the primary access-cost pair. Persisted Chronicle is a separate warm deployment stratum. Trial setup sweeps entries and iteration setup touches mapped file pages, but mapped pages can later be evicted. Primary forks have no process fault counters; diagnostic forks cannot prove the primary fork's page state. The short diagnostic measurement intervals showed zero major faults and zero process read bytes, but that is insufficient residency evidence for the primary samples. Mixed puts legitimately dirty mapped storage.
3. The host began with approximately 593 MiB available memory, 7.0 GiB swap in use, and nonzero full memory pressure. The run ended with still-heavy swap use and ongoing memory pressure. This violates the environmental stability expected for tail comparison.
4. Compiler diagnostic forks recorded 81–203 ms of whole-JVM compilation during their one-second measured intervals. They cannot identify which methods compiled, but they invalidate a claim of JIT stability. The primary forks were deliberately short, so late JIT is plausible there too.
5. Reversing backend order changed p99 by 1.31× for Chronicle in-memory 256 B, 1.68× for persisted 256 B, 1.26× for Caffeine 4 KiB, and 2.44× for Chronicle in-memory 4 KiB. The 25% audit threshold is a screening rule, not a statistical significance test. A single fork per block cannot estimate between-fork uncertainty. JMH's `±` from sampled observations does not substitute for independent-run replication.
6. JFR data were collected in separate forks and are diagnostic only. They were never pooled with the unprofiled latency CSV. The six JFR recordings and six OS-counter sidecars exist; the diagnostic profiler's process counters cover the whole JVM and its setup envelope.

## Claim limit and next candidate

The validation demonstrates that all six factor combinations and artifact channels execute and that the controls are logged. It does **not** establish a backend ordering, warm persisted latency, or a GC-pressure advantage. A future candidate needs a quiet host, the default longer warmup/measurement and independent forks, repeated counterbalanced blocks, stable compiler activity, and primary-fork-specific page-state evidence or a stronger residency method. The current memory pressure and variance make TailCache 10 a no-go for secondary experiments.
