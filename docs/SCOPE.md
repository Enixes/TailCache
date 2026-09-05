# Scope guard

Target completion: **20 October 2026**
Total engineering/research budget: **35-40 hours**

## Must ship

- Java 21 + Gradle repository.
- Common cache interface.
- Caffeine adapter.
- Chronicle Map adapter.
- Deterministic synthetic workload generator with fixed seeds.
- JMH latency harness capable of reporting percentiles.
- Capacity-safe Caffeine vs Chronicle Map experiments.
- Chronicle Map sizing/estimation reproduction related to issue #533.
- Raw result retention plus enough environment metadata to reproduce runs.
- Written analysis that includes null, negative, failed and inconvenient results.

## Secondary / cut first

- Eviction-policy simulation.

It is allowed only after the primary comparison and #533 contribution are complete and only if at least ~5 hours remain in the budget. It must not delay the October 20 target.

## Explicitly out of scope

- UI.
- Spring Boot or another application framework.
- Cloud deployment.
- Distributed cache cluster.
- Custom ML eviction policy.
- Production service integration.
- Proprietary XTP source code, schemas, traces, datasets, logs, configuration or derived confidential data.
- Tuning dozens of cache libraries. Caffeine and Chronicle Map are the study.

## Scope-creep rule

Any task expected to consume more than **2 hours** that is not directly required for the primary comparison, reproducibility, or issue #533 must be explicitly justified before implementation. Default answer: cut it.

## Suggested 38-hour allocation

| Workstream | Budget |
|---|---:|
| Scaffold, adapters, tests, smoke JMH | 5 h |
| Workload design + correctness checks | 5 h |
| Benchmark protocol + environment capture | 4 h |
| Main Caffeine vs Chronicle runs | 8 h |
| Chronicle sizing/#533 reproduction | 7 h |
| Analysis, plots/tables, robustness reruns | 5 h |
| Write-up + cleanup + upstream PR/issue material | 4 h |
| **Total** | **38 h** |

The budget is a constraint, not a target to exhaust.
