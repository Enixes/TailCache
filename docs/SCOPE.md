# Experiment scope

TailCache compares ordinary Caffeine access with ordinary in-memory Chronicle
Map access under controlled Java 21 workloads. The [README](../README.md)
states the three experiment questions and the results under the tested settings.

## Primary comparisons

- Saturated operation p99 and p99.9 under matched levels of added application
  data, payload size, and offered background churn.
- Fixed-arrival response p99.9 under matched write demand with 2,048 and 32,768
  eligible write keys. Reads span the resident set in this comparison.
- Descriptive allocation, G1, occupancy, and observed process memory alongside
  latency. Keep operation timing, queue delay, and total response separate.

The portable profiles use one cache worker, synthetic byte-array values, and
fresh immutable overwrites. Report results within the corresponding workload,
measurement channel, host, and protocol. Keep warned and rejected forks visible.

## Separate comparisons

File-backed and cold/open access, caller-owned `getUsing()` buffers, skewed reads,
shared-cache contention, alternate collectors, and equal-total-memory budgets
change the workload or API contract. Keep those comparisons separate from the
ordinary-access results. The JMH smoke and profiling tasks validate the harness.

Use synthetic workloads or publicly documented inputs. Confidential source,
traces, settings, and customer data are outside the dataset.
