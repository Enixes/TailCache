# Delivery plan

## North star - the research question

TailCache is **not** primarily a leaderboard asking whether Caffeine or Chronicle Map is faster in isolation.

The primary research question is:

> **At what level of JVM heap / live-set pressure does moving cache data off-heap become worthwhile because the reduction in GC-driven tail latency outweighs the additional serialization, materialization and off-heap access cost?**

The main scientific contribution should therefore be a **crossover curve**, not a generic backend ranking. At low heap pressure, Caffeine is expected to benefit from its cheaper direct Java-object access. As heap pressure rises, the study should determine whether and where GC effects make the off-heap design preferable at p99 / p99.9.

Primary outcome:

- identify whether a workload-dependent Caffeine -> Chronicle latency crossover exists;
- estimate where that crossover occurs under explicitly defined heap/live-set pressure;
- explain the crossover using allocation, GC and materialization evidence rather than latency numbers alone.

Primary explanatory variables:

- heap / live-set pressure;
- payload size;
- workload read/existing-key-put mix and locality;
- concurrency where justified by pilot stability.

Supporting / secondary questions must not displace the north-star question. Chronicle persistence, two-JVM sharing, `getUsing`, cold/open behaviour, eviction simulation and other sensitivities are useful only after the GC-pressure crossover protocol is sound.

### Scope guard against drift

Before adding a new experiment, ask: **does it help locate, explain or stress-test the off-heap crossover?**

- If yes, it can enter the primary or robustness plan.
- If it only characterizes another Chronicle feature, keep it secondary.
- Do not let the persisted-mode matrix become the headline result by itself.
- Do not treat smoke latency as evidence for the crossover.
- Do not use the TailCache 05 replacement-value bank to claim heap/GC savings; it intentionally keeps a Java-heap shadow payload set for Chronicle.

## Milestone 0 - scaffold

- [x] Java 21 / Gradle Kotlin DSL structure
- [x] common cache interface
- [x] Caffeine adapter
- [x] Chronicle Map adapter
- [x] deterministic uniform/hotspot workload model
- [x] methodology and scope guard

### TailCache 02 - JMH harness and shared benchmark model

- [x] dedicated `src/jmh` source set
- [x] deterministic synthetic key/value generator
- [x] named 256 B and 4 KiB payload sizes
- [x] shared JMH cache state
- [x] trial setup / iteration reset / trial teardown lifecycle
- [x] pre-generated hit and guaranteed-miss key sets
- [x] default warmup / measurement / fork policy
- [x] short `jmhSmoke` override
- [x] smoke operations: `getHit`, `getMiss`, `putExisting`
- [x] static Java compilation check with dependency stubs
- [x] real Gradle unit-test run on Java 21
- [x] real `jmhSmoke` run against Caffeine + Chronicle Map

### TailCache 03 - Caffeine measured-path validation

- [x] pre-box benchmark keys so cache calls do not include synthetic `Long` boxing
- [x] validate Caffeine hit / miss / overwrite / clear / capacity semantics
- [x] consume read results explicitly with JMH `Blackhole`
- [x] log backend configuration, including Caffeine's effective default executor
- [x] run allocation smoke with JMH `-prof gc`
- [x] generate and inspect a representative JFR recording
- [x] document the distinction between foreground lookup cost and asynchronous Caffeine maintenance
- [x] review and fact-check JFR / JMH interpretation
- [x] refresh validation after review fixes on the final PR head

### TailCache 04 - Chronicle Map measured-path validation

- [x] make Chronicle entry/value sizing explicit
- [x] configure `putReturnsNull(true)` to match TailCache's void `put` contract
- [x] use Chronicle `longSize()` for adapter size parity
- [x] document clear-vs-close lifecycle semantics for on/off-heap backends
- [x] extend Chronicle tests for hit / miss / overwrite / clear / close parity
- [x] add Chronicle allocation and JFR smoke tasks
- [x] run initial Java 21 unit-test, cross-backend smoke, allocation and JFR diagnostics
- [x] inspect representative hit/put JFR recordings
- [x] deep-review Chronicle sizing semantics against the actual fixed-size workload
- [x] replace `averageValueSize(...)` with `constantValueSizeBySample(...)`
- [x] align config naming, tests, logging and docs with exact fixed-size payloads
- [x] rerun unit-test and cross-backend smoke validation on the corrected layout
- [x] rerun Chronicle allocation/JFR diagnostics on the corrected layout and confirm the measured-path conclusions still hold

#### TailCache 04 peer-review follow-up carried into TailCache 05

- [x] disable Chronicle analytics in all test/benchmark JVMs
- [x] explicitly configure and log `allowSegmentTiering=true`
- [x] correct wording so `maxBloatFactor(1.0)` is not described as disabling tiering
- [x] add a wrong-value-size negative test for the constant-size Chronicle contract
- [x] describe backend configuration output as experiment-relevant rather than exhaustive
- [x] rerun TailCache 04 test/smoke/allocation/JFR validation on the peer-review-hardened head

### TailCache 05 - workload distributions, persistence and concurrency matrix

TailCache 05 is **supporting infrastructure**, not the final scientific experiment. It establishes controlled workload, persistence and contention mechanics that may be used to explain or stress-test the later crossover study.

- [x] add Chronicle storage modes `IN_MEMORY` and `PERSISTED`
- [x] implement persisted Chronicle creation with `createPersistedTo(...)`
- [x] create persisted benchmark files during trial setup and close/delete them during trial teardown
- [x] prepopulate all primary modes outside measurement
- [x] define comparison modes: Caffeine / Chronicle in-memory / Chronicle persisted-warm
- [x] add deterministic Zipfian access with initial exponent 0.99
- [x] preserve uniform access and legacy hotspot support
- [x] add exact complete-trace 95/5 and 70/30 read/existing-key-put mixes
- [x] separate key-selection and operation-mix random streams so changing the mix does not change the key sequence
- [x] preallocate one replacement payload per logical key so mixed puts allocate nothing and do not collapse Caffeine's resident values onto one shared object
- [x] document that the replacement bank excludes heap-footprint/GC conclusions from this mixed matrix
- [x] introduce `Scope.Benchmark` shared-cache state for the mixed workload
- [x] keep per-worker trace cursors in `Scope.Thread` with deterministic staggered offsets over one cyclic trace
- [x] move thread-index/trace-size/initial-offset work into `@Setup(Level.Iteration)` outside the measured path
- [x] add one-worker and 16-worker shared-cache smoke tasks
- [x] export mixed-workload smoke results as JMH JSON
- [x] keep two-JVM persisted sharing separate from the primary same-JVM matrix
- [x] run unit tests after the workload/persistence changes and after measured-path hardening
- [x] run `jmhWorkloadSmoke` and verify all 24 primary parameter combinations expand successfully
- [x] run `jmhWorkloadShared16Smoke` and verify one shared cache is used by all 16 workers
- [x] verify persisted map files are removed after successful trial teardown
- [x] verify Chronicle analytics remains disabled in workload benchmark forks
- [x] document persisted warm-state assumptions and keep persisted latency non-reportable until filesystem/page-fault controls are frozen
- [ ] close the final TailCache 05 research-review measured-path cleanup before merge

## Milestone 1 - trustworthy crossover harness

The purpose of this milestone is to make the **heap-pressure crossover** measurable without confounding it with harness overhead or an artificial Chronicle heap shadow set.

- [x] commit and pin the Gradle 9.7.1 wrapper
- [x] run unit tests on Java 21
- [x] run `jmhSmoke` on Java 21
- [ ] capture benchmark environment metadata
- [ ] quantify benchmark trace-selection / harness floor before reportable latency comparisons
- [ ] verify reportable warmup is sufficient for measured-path compilation stability
- [ ] document the Caffeine 50%-of-`maximumSize` frequency-sketch activation boundary discovered during review; do not inherit the 2048/4096 smoke ratio into reportable runs accidentally
- [ ] freeze backend-specific entry-count / occupancy semantics before reportable comparisons; do not assume equal numeric Caffeine `maximumSize` and Chronicle `entries` are scientifically equivalent
- [ ] design a dedicated GC-pressure workload/value-supply path that does **not** retain one Chronicle shadow payload per key on the Java heap
- [ ] pin `-Xms == -Xmx` for crossover experiments so heap resizing is not another variable
- [ ] use G1 as the initial primary collector unless pilot evidence justifies another baseline; keep ZGC or other collectors as sensitivity experiments
- [ ] define pressure levels using measured live-set / old-gen occupancy rather than payload bytes alone
- [ ] choose a small pilot set spanning low, moderate, high and severe heap pressure without relying on arbitrary percentage labels
- [ ] capture allocation rate, GC count, GC pause time, concurrent-GC activity and post-GC/live-heap occupancy alongside latency
- [ ] decide how workload seeds are replicated: one frozen primary seed plus robustness seeds, or multiple seeds in the main design
- [ ] add a stable workload/trace fingerprint to retained raw results
- [ ] verify deterministic trace coverage per measurement interval so repeated prefixes do not accidentally dominate results
- [ ] define the concurrency claim precisely as closed-loop N-worker operation/service latency; do not imply fixed-arrival-rate production response latency
- [ ] capture resolved Chronicle layout metadata when it can be obtained reliably
- [ ] add reportable JMH profile(s) only after smoke and backend validation pass

### Persisted-mode controls - secondary to the crossover

- [ ] make the persisted benchmark root configurable before any reportable persisted run
- [ ] capture filesystem, mount and storage-device metadata for persisted runs
- [ ] verify warm persisted trials are not dominated by first-touch page faults or setup writeback
- [ ] keep persisted mode out of the headline crossover unless it answers a specific follow-up hypothesis

## Milestone 2 - primary study: when does off-heap pay off?

### Primary research questions

- **RQ1:** At what heap/live-set pressure, if any, does Chronicle Map in-memory achieve lower p99 / p99.9 operation latency than Caffeine despite its higher ordinary-access/materialization cost?
- **RQ2:** How does payload size shift that crossover?
- **RQ3:** How do locality and read/existing-key-put mix shift that crossover?
- **RQ4:** Does same-JVM contention materially shift the crossover, and is that effect stable enough to retain in the reportable matrix?

### Pre-registered hypotheses before main runs

- [ ] H1: under low heap pressure, Caffeine should have lower median and tail latency because it avoids Chronicle's serialization/materialization boundary
- [ ] H2: as Caffeine's cache contributes more to the live heap, its tail latency should degrade faster if GC pressure becomes material
- [ ] H3: a workload-dependent crossover may exist where reduced heap/GC pressure outweighs Chronicle's higher per-access cost
- [ ] H4: if a crossover exists, larger payloads and tighter heaps should move it earlier; treat this as a hypothesis, not an assumption

### Primary campaign

- [ ] freeze the minimum reportable factors after pilot; resist building a combinatorial grid
- [ ] make **Caffeine vs Chronicle in-memory** the primary crossover comparison
- [ ] choose payload sizes sufficient to reveal whether value size moves the crossover; start with 256 B and 4 KiB and add another size only if pilot evidence justifies it
- [ ] freeze the primary workload distribution and read/existing-key-put mix before the main campaign; use additional mixes/distributions as robustness checks rather than automatically multiplying the full matrix
- [ ] sweep controlled heap/live-set pressure levels with identical workload semantics across backends
- [ ] retain p50 / p95 / p99 / p99.9 where sample counts support them
- [ ] retain throughput only as supporting context, not the primary outcome
- [ ] retain GC/allocation/live-set evidence needed to explain any latency crossover
- [ ] retain raw outputs, environment metadata, trace fingerprints and configuration exports
- [ ] repeat key findings across workload seeds / fresh forks
- [ ] perform robustness reruns for surprising or threshold-sensitive results
- [ ] report **no crossover** as a valid result if Chronicle never recovers its access tax in the tested pressure range

## Milestone 3 - explanation and sensitivity, only after the crossover protocol is stable

### High-value sensitivities

- [ ] repeat selected crossover points with a low-pause collector such as ZGC to see whether GC choice moves or removes the crossover
- [ ] test selected locality / read-put / concurrency variants around the observed crossover instead of rerunning a full Cartesian matrix
- [ ] vary Chronicle Map sizing assumptions systematically only if they could explain crossover movement
- [ ] test `entries` target / resident-set headroom separately from the primary latency campaign
- [ ] distinguish Chronicle serialization/materialization costs from GC-pressure effects
- [ ] keep `getUsing` / object reuse as a separate API-level sensitivity experiment

### Chronicle persistence / sharing - secondary track

- [ ] compare Chronicle persisted-warm with Chronicle in-memory at selected crossover-relevant points if persistence is still useful to the engineering story
- [ ] keep persisted cold/open behaviour separate from warm steady-state results
- [ ] run two-JVM persisted sharing only as a distinct secondary experiment
- [ ] do not let persistence or multi-JVM work displace the primary off-heap/GC crossover study

### Lower-priority robustness

- [ ] test fixed-size layout assumptions and deliberately perturbed sizing only if needed to explain a result
- [ ] decide whether eviction simulation adds enough value after the core crossover is understood

## Milestone 4 - analysis and write-up

- [ ] plot tail-latency curves against measured heap/live-set pressure and identify crossover regions with uncertainty rather than one magic threshold number
- [ ] correlate latency-tail changes with GC/allocation/live-set evidence
- [ ] distinguish low-pressure steady-state access tax from high-pressure GC benefit
- [ ] document backend semantic differences and limits of causal interpretation
- [ ] explicitly distinguish fixed-concurrency closed-loop service latency from fixed-QPS response latency
- [ ] report how payload size / workload / collector choice move or remove the crossover
- [ ] publish negative/null findings, including a possible "off-heap never pays off in this tested regime" result
- [ ] formulate the practical engineering answer: under what measured conditions is moving cache data off-heap advisable?
- [ ] decide whether the evidence is strong enough for a preprint

## Cut line

If schedule slips, protect the **GC-pressure crossover study** first.

Cut in this order:

1. eviction simulation;
2. persisted cold/open behaviour;
3. two-JVM sharing;
4. broad Chronicle sizing sensitivities;
5. extra workload/concurrency combinations that do not help locate or explain the crossover.

Do **not** cut reproducibility, heap/GC instrumentation, raw-result retention, primary-methodology controls, robustness of the crossover itself, or honest reporting.
