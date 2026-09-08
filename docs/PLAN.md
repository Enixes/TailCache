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

## Milestone 1 - trustworthy harness

- [x] commit and pin the Gradle 9.7.1 wrapper
- [x] run unit tests on Java 21
- [x] run `jmhSmoke` on Java 21
- [ ] capture benchmark environment metadata
- [ ] quantify benchmark key-selection / harness floor before reportable latency comparisons
- [ ] add reportable JMH profile(s) only after smoke and backend validation pass

## Milestone 2 - primary study

- [ ] write 2-4 concrete hypotheses before running the main matrix
- [ ] freeze experiment factors and seeds
- [ ] define single-thread and any shared-cache concurrency experiments explicitly
- [ ] run Caffeine vs Chronicle Map campaign
- [ ] retain raw outputs
- [ ] perform robustness reruns for surprising results

## Milestone 3 - sizing and robustness sensitivity

- [ ] vary Chronicle Map sizing assumptions systematically
- [ ] test capacity headroom and average-value-size sensitivity separately from the primary latency campaign
- [ ] distinguish serialization/materialization costs from sizing effects
- [ ] retain this as a secondary experiment so it cannot distort the primary comparison

## Milestone 4 - analysis and write-up

- [ ] summarize distributions and tails
- [ ] document limitations and semantic differences
- [ ] publish negative/null findings
- [ ] decide whether eviction simulation fits remaining budget

## Cut line

If schedule slips, cut eviction simulation first, then reduce secondary sensitivity work. Do not cut reproducibility, raw-result retention, primary-methodology controls, or honest reporting.
