# Delivery plan

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
- [ ] rerun TailCache 04 test/smoke/allocation/JFR validation on the peer-review-hardened head

### TailCache 05 - workload distributions, persistence and concurrency matrix

- [x] add Chronicle storage modes `IN_MEMORY` and `PERSISTED`
- [x] implement persisted Chronicle creation with `createPersistedTo(...)`
- [x] create persisted benchmark files during trial setup and close/delete them during trial teardown
- [x] prepopulate all primary modes outside measurement
- [x] define primary modes: Caffeine / Chronicle in-memory / Chronicle persisted-warm
- [x] add deterministic Zipfian access with initial exponent 0.99
- [x] preserve uniform access and legacy hotspot support
- [x] add exact 95/5 and 70/30 read/update mixes
- [x] separate key-selection and operation-mix random streams so changing the mix does not change the key sequence
- [x] preallocate one replacement payload per logical key so mixed writes allocate nothing and do not collapse Caffeine's resident values onto one shared object
- [x] introduce `Scope.Benchmark` shared-cache state for the mixed workload
- [x] keep per-worker trace cursors in `Scope.Thread` with deterministic staggered offsets
- [x] add one-worker and 16-worker shared-cache smoke tasks
- [x] export mixed-workload smoke results as JMH JSON
- [x] keep two-JVM persisted sharing separate from the primary same-JVM matrix
- [ ] run unit tests after the workload/persistence changes
- [ ] run `jmhWorkloadSmoke` and verify all 24 primary parameter combinations expand successfully
- [ ] run `jmhWorkloadShared16Smoke` and verify one shared cache is used by all 16 workers
- [ ] verify persisted map files are removed after successful trial teardown
- [ ] verify Chronicle analytics remains disabled in all workload benchmark forks
- [ ] review persisted warm-state assumptions before promoting any persisted latency number

## Milestone 1 - trustworthy harness

- [x] commit and pin the Gradle 9.7.1 wrapper
- [x] run unit tests on Java 21
- [x] run `jmhSmoke` on Java 21
- [ ] capture benchmark environment metadata
- [ ] quantify benchmark trace-selection / harness floor before reportable latency comparisons
- [ ] verify reportable warmup is sufficient for measured-path compilation stability
- [ ] freeze backend-specific entry-count / occupancy semantics before reportable comparisons
- [ ] capture resolved Chronicle layout metadata when it can be obtained reliably
- [ ] capture filesystem, mount and storage-device metadata for persisted runs
- [ ] verify warm persisted trials are not dominated by first-touch page faults or setup writeback
- [ ] add reportable JMH profile(s) only after smoke and backend validation pass

## Milestone 2 - primary study

- [ ] write 2-4 concrete hypotheses before running the main matrix
- [ ] freeze experiment factors and seeds
- [x] define one-thread and same-JVM shared-cache state ownership explicitly
- [ ] decide which concurrency levels survive the pilot into the reportable matrix
- [ ] run Caffeine vs Chronicle in-memory vs Chronicle persisted-warm campaign
- [ ] retain raw outputs and configuration exports
- [ ] perform robustness reruns for surprising results

## Milestone 3 - sizing and robustness sensitivity

- [ ] vary Chronicle Map sizing assumptions systematically
- [ ] test `entries` target / resident-set headroom separately from the primary latency campaign
- [ ] test fixed-size layout assumptions and any deliberately perturbed sizing configuration as secondary sensitivity checks
- [ ] distinguish serialization/materialization costs from sizing effects
- [ ] keep `getUsing` / object reuse as a separate API-level experiment
- [ ] keep persisted cold/open behaviour separate from warm steady-state results
- [ ] run two-JVM persisted sharing only as a distinct secondary experiment
- [ ] retain this as secondary work so it cannot distort the primary comparison

## Milestone 4 - analysis and write-up

- [ ] summarize distributions and tails
- [ ] document limitations and semantic differences
- [ ] publish negative/null findings
- [ ] decide whether eviction simulation fits remaining budget

## Cut line

If schedule slips, cut eviction simulation first, then reduce secondary sensitivity work. Two-JVM sharing and cold/open persistence behaviour are secondary. Do not cut reproducibility, raw-result retention, primary-methodology controls, or honest reporting.
