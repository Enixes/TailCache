# Delivery plan

## Milestone 0 - scaffold (now)

- [x] Java 21 / Gradle Kotlin DSL structure
- [x] common cache interface
- [x] Caffeine adapter
- [x] Chronicle Map adapter
- [x] deterministic uniform/hotspot workload model
- [x] initial JMH smoke suite
- [x] methodology and scope guard

## Milestone 1 - trustworthy harness

- [ ] generate standard Gradle wrapper on a networked development machine
- [ ] run unit tests on Java 21
- [ ] run `jmhSmoke` on Java 21
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
