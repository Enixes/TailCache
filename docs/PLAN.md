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

## Milestone 1 - trustworthy harness

- [ ] align the committed Gradle wrapper with the project-pinned Gradle version
- [x] run unit tests on Java 21
- [x] run `jmhSmoke` on Java 21
- [ ] capture benchmark environment metadata
- [ ] add reportable JMH profile(s) only after smoke passes

## Milestone 2 - primary study

- [ ] write 2-4 concrete hypotheses before running the main matrix
- [ ] freeze experiment factors and seeds
- [ ] run Caffeine vs Chronicle Map campaign
- [ ] retain raw outputs
- [ ] perform robustness reruns for surprising results

## Milestone 3 - Chronicle Map sizing / #533

- [ ] create minimal sizing reproducer independent of primary JMH suite
- [ ] vary estimate error systematically
- [ ] determine failure boundary/repeatability
- [ ] inspect upstream implementation only after reproducer is stable
- [ ] prepare useful upstream contribution

## Milestone 4 - analysis and write-up

- [ ] summarize distributions and tails
- [ ] document limitations and semantic differences
- [ ] publish negative/null findings
- [ ] decide whether eviction simulation fits remaining budget

## Cut line

If schedule slips, cut eviction simulation first. Do not cut reproducibility, raw-result retention, sizing/#533 work, or honest reporting.
