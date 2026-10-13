# TailCache 12 — current-state review and execution plan

Prepared before implementation on 2026-10-13 against clean commit `c008dad`. The state review below is the planning snapshot. Implementation and evidence updates are recorded in `docs/TAILCACHE_12_IMPLEMENTATION_REVIEW.md` and `docs/TAILCACHE_12_STATUS.json`; the campaign has not been run.

Source: [TickTick Task 12](https://ticktick.com/webapp/#p/60d767527eba1347b9b9006e/tasks/6a99b1248f0842fe140aa129), “Run RQ1/RQ2 crossover campaign, repeats and statistical summaries.” The task explicitly includes 12A–12G: repair, measurement validation, calibration, quality controls, pilot, campaign and statistics. The user chose **this machine during a quiet session** for the reportable campaign.

## Current-state review

**Ready to implement 12A; not ready to launch 12F.** Existing adapters, deterministic workloads and evidence tooling provide a useful foundation. The required heap-pressure experiment is absent.

| Requirement | Verified state | Consequence for Task 12 |
|---|---|---|
| Correct adapters and deterministic workloads | Fresh Java 21 test reports contain 21 tests, zero failures/errors/skips across six suites. Gradle `test jmhClasses resultToolsClasses` passes. | Reuse adapters and trace generation. Correctness tests do not establish measurement validity. |
| Primary crossover workload | `CacheWorkloadState` fixes 2,048 residents/4,096 configured entries and retains `byte[][] replacementValues`, one payload per key for both backends. | Implement a dedicated crossover state; current mixed-workload results cannot establish heap savings. |
| Identical write semantics | Existing writes reuse a payload bank, with no repeated payload allocation. | Freeze fresh immutable write payloads supplied identically to both backends. |
| Independent application churn | No driver or separate retained application live-set control exists. | Add and validate both controls. |
| Pause-sensitive latency | Only SampleTime/Throughput harnesses exist; no every-operation channel or known-pause validation. | Required before GC-tail claims. |
| JIT stability | Task 08's longer compiler probe still reports 246 ms for Caffeine and 190 ms for Chronicle in-memory over eight measured seconds. | 12/8/3 is a minimum replication policy, not a proven warmup solution. |
| GC/live-set evidence | Existing G1 profiler retains pause logs/count/total/max in wider profiler envelopes; no full occupancy/concurrent-cycle/exposure schema. | Extend parsing and add actual worker timing windows. |
| Campaign and statistics | Task 08 runner retains raw files, hashes, trace fingerprints and counterbalanced blocks; summaries aggregate JMH results. | Add pressure/seed/fork/iteration/channel identities and independent-replication statistics. |
| Secondary work | Task 10 gate still returns `NO_GO` using its retained 2026-10-04 evidence. | Protect RQ1/RQ2; Task 11 remains deferred. This is a reproduction of the old evidence decision, not a refreshed schedule assessment. |

Evidence checked directly:

- Candidate B's manifest has 12 invocations, all with successful exit codes. All 36 manifest-listed raw artifacts exist and match their SHA-256 hashes. Workload logs contain one trace fingerprint, `309730d3d60d2354ce710528051678c47c36ba630910d1f9d76c2d9fcaad529b`. This verifies the listed files, not every possible artifact or source-snapshot content.
- Both candidate A and B quality artifacts mark the baseline rejected. B fails compiler screens and 256-B p99 replication screens.
- The later 12/8/3 256-B probes reproduce the documented p99 ratios: Caffeine 1.006, Chronicle in-memory 1.075, persisted Chronicle 1.118. The separate 12/8/1 compiler probe reproduces 246/190/167 ms. These repairs do not make the baseline a crossover study.
- At this review's host snapshot, memory PSI `avg10` was zero, but approximately 2.5 GiB was already used in zram. Existing swap occupancy alone does not prove active disturbance; swap traffic and pressure during each run must be observed.

Raw evidence remains under ignored `build/reports/`. Freeze an archive with checksums outside disposable build output before cleaning or releasing the campaign.

## Experimental decisions

### Primary comparison and claim

Use Caffeine versus Chronicle **in-memory**, 256 B versus 4 KiB, one worker, uniform keys, 95/5 reads/existing-key puts, G1 and Java 21. Start with seed `0x5EED`; use two additional frozen seeds at any candidate crossover and its neighboring points. The claim is fixed-concurrency, closed-loop workload-operation latency. Throughput supports interpretation.

Keep a single resident key count `N`, heap size `H` and backend configuration fixed across the pressure sweep. Prefer the same `N` and `H` for both payload sizes so payload is the changed factor. Choose actual values through calibration; do not inherit the smoke key count or declare a 512-MiB heap adequate without measuring it.

Sweep a backend-neutral **retained application live set** at a separately fixed application allocation rate. Within each backend pair, use identical heap, resident count, application live set, offered churn schedule and logical workload. Measure each backend's resulting heap/old-generation occupancy as an outcome. Adding ballast to Chronicle solely to force equal total occupancy would remove the heap-saving effect being studied.

Report latency against both the common application-pressure input and measured occupancy for each backend. Do not compare differently configured points simply because their observed occupancy percentages happen to match. Choose a shared application-live-set schedule across payloads where practical; if calibration requires different schedules, limit RQ2 to the observed overlapping pressure range and document the changed control.

### Value supply and measurement boundary

Populate incrementally and discard setup references after each insertion. Retain common keys/traces but no Chronicle payload bank. For every measured write, create a fresh exact-size immutable byte array with deterministic content derived from key/update sequence. Both backends receive the same logical update sequence and generation algorithm. Never reuse or mutate arrays still referenced by Caffeine.

Include fresh payload creation in the measured workload-operation boundary for both backends. This intentionally changes the old allocation-free workload and measures an update-producing application. Ordinary Chronicle `get` remains the parity path. Extend methodology documentation to describe the new boundary rather than retaining the old universal “payloads generated outside measurement” rule.

Keep deterministic generation simple, benchmark its floor, and retain allocation evidence. Do not subtract a floor from latency percentiles. Caffeine retention of fresh values and Chronicle materialization/serialization are expected backend effects.

### Resident entries and cache policy

Treat `N` resident entries as the common workload invariant, not equal numeric backend capacity controls. Candidate policy: Caffeine `maximumSize = ceil(1.25 * N)` to leave headroom while staying away from the old 50% activation boundary; Chronicle `entries = 2 * N` initially, with fixed-size layout and explicit tiering/bloat/checksum settings. Validate these proposals before freezing them.

Check every key's contents and resident count outside measurement, including after warmup and trial completion. Prove there are no evictions/misses/capacity errors in the intended existing-key workload. Record Caffeine policy initialization and resolved Chronicle layout/native allocation where available. Capacity headroom is a configuration choice, not equivalent occupancy. Caffeine's pinned implementation activates its frequency sketch according to half its maximum; verify the chosen state rather than relying on a rounded ratio. [Caffeine 3.2.4 source](https://raw.githubusercontent.com/ben-manes/caffeine/v3.2.4/caffeine/src/main/java/com/github/benmanes/caffeine/cache/BoundedLocalCache.java).

## Delivery stages and gates

### 12A — Dedicated crossover workload

Add crossover configuration/state/benchmark classes alongside the existing validation harness. Add incremental population, deterministic fresh writes, bounded common metadata and an explicit retained application-live-set object graph. Use modest arrays/objects for ballast and churn so a single giant array does not silently create a G1 humongous-allocation experiment. G1 treats sufficiently large objects separately. [Java 21 G1 guide](https://docs.oracle.com/en/java/javase/21/gctuning/garbage-first-g1-garbage-collector1.html).

Add one paced application-churn thread with a frozen offered byte rate, object size and short retention lifetime. Keep its bounded ring and observable checksum so allocation is real. Record attempted/realized bytes, missed deadlines and retained ring footprint; cap catch-up bursts after a pause. The rate controller must not depend on cache-operation throughput. Check achieved non-cache allocation rates against the declared target in both backends.

Gate: parity tests cover full logical contents after fresh writes, unique Caffeine value ownership, cache size, lifecycle and deterministic trace/content fingerprints. A diagnostic retained-object inspection must show Chronicle has no `O(N * payloadBytes)` Java payload bank. Tiny controlled runs must prove churn allocation survives optimization and ballast is retained. Pin `-Xms == -Xmx`, G1 and resolved flags.

### 12B — Every-operation latency and JIT validation

Keep unprofiled JMH SampleTime as one channel. Add a separate runner using the **same workload core**, timing every operation and recording a preallocated, per-worker HdrHistogram. Also retain inter-completion gaps, completed-operation counts and actual measurement start/end timestamps, so a pause between calls is not presented as an uninterrupted worker. Export per-iteration histograms after the interval. Histogram recording and serialization must not allocate in the measured path. [HdrHistogram documentation](https://github.com/HdrHistogram/HdrHistogram).

Record ordinary closed-loop service latency without inventing a fixed arrival interval or adding coordinated-omission correction. Inter-completion gaps are availability evidence and must not be relabeled service latency. Record maximum and counts above frozen stall thresholds because even a perfectly recorded rare pause need not move p99.9.

Validation has two parts: a deterministic long operation verifies timing/recording; a deliberately induced **GC/safepoint pause in a validation-only run** must be confirmed in raw JVM logs and observed by the worker's service interval or inter-completion gap. A sleep alone does not validate JVM pause capture. Check timestamp overlap, observed duration, recording count and histogram overflow. Keep injection out of campaign results.

Use at least 12 one-second warmups, eight one-second measurements and three fresh forks per reportable condition/channel. Measure timer/recorder floor and low-pressure observer effects; declare a coherence rule from pilot evidence before the campaign. Do not require numerical equality between sampled and every-operation tails: their sampling and instrumentation differ. Rare-stall capture and direction under pressure are the relevant checks.

Run compiler diagnostics separately with per-iteration counters and method-level compilation/deoptimization evidence. Retain the existing 1% compiler-time screen initially. For an eight-second diagnostic, 80 ms is the aggregate ceiling; preserve per-iteration values so an aggregate does not hide late activity. If it fails, investigate which code compiles, try longer diagnostic warmup, then freeze a revised duration only after passing repeated probes. Do not relax the rule after seeing desired crossover results. Separate diagnostic forks support a condition-level JIT screen; they cannot prove every unprofiled fork was compilation-free.

Gate: known-pause detection, complete/overflow-free histogram counts, bounded observer effects and repeated compiler diagnostics pass. If JIT remains unstable, retain rejected diagnostics and revise the measurement protocol before proceeding.

### 12C — Pressure calibration

Measure empty/common-harness footprint, populated cache footprint and application live-set footprint separately. A setup-only full GC/retained-object diagnostic may help estimate retention; never force a collection inside reportable measurement. During normal G1 operation collect post-collection used heap, old/survivor/humongous region information and concurrent-cycle evidence. Post-young-GC occupancy is not an exact live-set census; label its collection type and interpretation.

Choose four common application-live-set levels spanning empirically low through severe sustainable pressure. Labels require measured occupancy/GC evidence, not allocated payload bytes alone. Freeze `N`, `H`, ballast values, non-cache churn rate and expected **backend-specific** occupancy bands in a calibration artifact. The same input can legitimately yield different occupancy in Caffeine and Chronicle. Distinguish an unsustainable/OOM boundary from an accepted severe-pressure observation.

Repeat calibration in independent JVMs for both payload sizes/backends. Proposed screens are ±5 percentage points around each calibrated post-GC occupancy band and ±10% of the non-cache churn-rate target. Validate their adequacy in calibration and freeze them before the campaign. If the low-pressure cell has too few collections to estimate post-GC occupancy, use a separately identified retained-footprint diagnostic and report measurement GC count as zero.

Gate: reproducible pressure separation and a sustainable high-pressure pair; no host swapping introduced by JVM/native memory demands. Missing occupancy evidence is not silently replaced with nominal ballast size.

### 12D — Host, GC and evidence pipeline

Use this machine on AC power with a stable declared power/governor mode and ordinary CPU scheduling. The old whole-process single-CPU affinity experiment was rejected; do not repeat it as a default control. Start a quiet session after unrelated builds/downloads and stop competing memory-heavy work through user-controlled session preparation.

Capture CPU topology, available RAM, swap, PSI totals, swap-in/out counters, load, power/governor and available temperature/frequency evidence before/after each block. Sample disturbance during the block, since boundary averages can miss transient interference. Record missing platform sensors explicitly; this host lacks the reviewed ACPI `platform_profile` path.

Proposed host gate: zero boundary memory-full `avg10`, interval memory-full PSI no more than 0.1% of elapsed time, no increase in swap-in/out counters, stable power settings and no documented competing workload. Pilot establishes the final screens; existing zram use is recorded rather than automatically treated as a failure. A host failure suspends subsequent blocks until it is quiet.

Extend GC logs/parser to retain collection identifiers/types, pause start/end intervals, young/mixed/full events, concurrent cycles, heap before/after, old-generation evidence and humongous-region counts. Count pause overlap with actual worker windows, clipping overlap for time-at-risk; retain whole event durations separately. The old completed-event-in-profiler-envelope rule cannot establish exact operation exposure at interval edges.

Channels: (1) unprofiled SampleTime, (2) every-operation timing with minimal retained GC/window evidence for within-fork pause association, (3) separate allocation/GC/compiler diagnostic runs and unprofiled Throughput support runs. Label instrumentation in channel 2 and validate its observer effect. Metrics from distinct forks are comparable-condition evidence, not event-by-event correlations.

Add immutable run/attempt IDs, complete source snapshots and hashes, exact JDK/build/backend versions, parameters, seeds, trace and value-generation fingerprints, per-fork/per-iteration artifacts and explicit rejected reasons. Refuse directory overwrite. Each attempt is resumable from its manifest; later audits must reproduce acceptance from raw inputs.

Gate: parser fixtures exercise real-log formats, concurrent-phase exclusion, window-edge overlaps and missing evidence. A real short G1 diagnostic agrees with an independent raw-log recomputation. Quality checks fail closed on absent or malformed required evidence.

### 12E — Eight-cell pilot

Run 2 backends × 2 payloads × calibrated low/high pressure. Use both backend orders and the 12/8/3 primary replication policy. Exercise all channels and final source/provenance exports. Pilot data tune the protocol; they do not enter the subsequently frozen confirmatory dataset.

Proceed only if pressure/churn, host/JIT, pause detection, artifact integrity and observer/coherence screens pass. Carry the old p99 1.25 between-order ratio as an initial descriptive noise screen; define a separate p99.9 screen from independent pilot replicates and tail counts. A ratio gate is not a statistical significance test.

Failure response: fix the identified harness/protocol issue or reject the disturbed attempt. Extend duration when GC or tail-event exposure is insufficient. Do not rerun a cell merely because its backend ranking is inconvenient.

### 12F — Frozen primary campaign

Run 2 backends × 2 payloads × 4 calibrated pressure inputs = **16 primary conditions**. Schedule two independent counterbalanced passes, three fresh forks each: at least six primary forks per condition/channel. Counterbalance backend, payload and pressure order across passes with a frozen order seed, keeping paired comparisons close in time.

Freeze a machine-readable protocol after pilot: input values, versioned workload, measurement boundaries/durations, seeds, order, numerical gates, endpoint priorities and rejection/retry rules. Each condition gets an accepted/rejected/missing status. “No crossover in the tested range” requires accepted coverage of that range; missing high-pressure cells cannot support that conclusion.

Repeat any candidate crossing and adjacent points with the two robustness seeds. Add narrower pressure points only as a separately declared follow-up. Persisted mode, contention, object reuse, cold/open and eviction stay outside this task's primary matrix.

### 12G — Statistics and acceptance

Reconstruct each fork's percentiles from its retained histograms, preserving iteration boundaries. Summarize medians, dispersion and counterbalanced block ratios. Use independent runs/forks as replication units; sampled operations and repeated iterations in one JVM are not independent experimental replicates. Report SampleTime and every-operation results separately.

Report paired Chronicle/Caffeine p99 and p99.9 ratios with uncertainty, using a documented hierarchical/block bootstrap or another justified replication-level method. With two outer passes, interval precision is limited; add independent passes near a threshold if the uncertainty cannot resolve the prespecified effect. Do not average per-fork percentiles and call that a pooled percentile. A pooled histogram may be offered as a separately labeled descriptive summary.

Require at least 100,000 recorded observations per fork for a p99.9 summary as an initial adequacy screen, and retain tail counts/GC-event counts; observation count alone does not prove rare-pause coverage. Withhold unsupported endpoints. A crossing is a supported region where paired ratios move from above to below one across accepted inputs, replicated across seeds and compatible with GC evidence. Ratios overlapping one are unresolved, not an exact threshold. Treat a p99-only crossing and a p99.9 crossing as distinct findings.

Retain all noisy valid runs and all invalid attempts. Retry only documented gate failures under a predeclared retry limit; do not retain the best-looking attempt. If valid replication fails the variance screen, report instability and investigate/extend the protocol rather than deleting statistical outliers.

Final gate: every primary condition has workload integrity, achieved calibrated pressure/churn, host/JIT acceptance, complete GC evidence, adequate channel/sample exposure, replicate statistics and immutable provenance, or an explicit reason it was rejected/unresolved. Task completion means an analysis-ready evidence package with honest coverage, not merely a successful Gradle exit.

## Implementation order and reviewable outputs

| Order | Concrete change | Evidence required before next stage |
|---|---|---|
| 1 | Crossover workload/configuration, fresh value supply, retained-live-set/churn controls, targeted parity tests; update methodology boundary | Correctness, retention and allocation diagnostic; dedicated harness smoke |
| 2 | Every-operation runner and histogram export; known-pause validation; compiler probe/protocol | Pause overlap/duration evidence, observer-floor report, JIT decision |
| 3 | Calibration runner; GC occupancy/exposure parser; host monitor; versioned raw/summary/quality schemas | Reproducible measured calibration and independently audited logs |
| 4 | Pilot orchestration and resumable manifests | Eight-cell pilot review and frozen campaign protocol |
| 5 | Counterbalanced campaign, robustness seeds and statistical summaries | Accepted/rejected coverage table and archived analysis-ready dataset |

Expected new homes: crossover classes in `src/jmh/java/.../benchmark`, reusable workload controls in `src/main/java/.../workload`, analysis extensions in `src/results/java/.../results`, `scripts/tailcache12.py`, and protocol/review artifacts in `docs/` with raw runs under `build/reports/tailcache12/`. Exact class names can follow implementation needs.

At the minimum 12+8 one-second schedule, 16 conditions × 2 passes × 3 forks consumes 1,920 timed seconds (**32 minutes per primary channel**) before JVM/setup/Gradle overhead. Both primary latency channels require at least 64 timed minutes; throughput, diagnostics, pilot, calibration, robustness and retries add materially. Budget measured wall time after the pilot rather than promising a completion date from this arithmetic. The TickTick due date is 2026-10-17; research gates remain the completion criterion.

**Immediate next work: implement and review 12A, followed by the pause/JIT validation slice of 12B.** The campaign begins only after 12C–12E produce a passing frozen protocol.
