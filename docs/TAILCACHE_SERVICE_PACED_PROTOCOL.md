# Matched-arrival load and payload check — prospective plan, 17 November 2026

Declared during the fixed service replication, before this check's implementation/collection. This separately identified cohort tests a specific limitation: saturated backends complete different traffic volumes per second, so equal operation mix does not mean equal delivered cache-allocation demand per second. It also supplies a matched scheduled-response payload comparison, rather than contrasting disjoint historical ballast ranges.

## Fixed design and budget

Payloads **256 B and 4 KiB**, common application ballast **0/208/336 MiB**, both backends, **two fresh paired repetitions per cell**: **24 workload JVMs**. Fixed seed 24301, deterministically shuffled cell order and alternating backend order. This is a bounded load-control/response diagnostic with two pairs, not a calibrated significance claim or a precise threshold campaign. Do not pool these forks with saturated or earlier short-trace observations.

Use the same frozen long-trace ServiceCrossoverRunner runtime as the service screen/replication, ordinary immutable 95/5 operations, 32,768 residents, 512 MiB G1 heap and common offered churn. Keep 12/2/30-second phases. Change only the declared arrival regime to the supported **50,000 intended arrivals/s**, with serial no-skips queue-debt retention. Each complete measurement contains 1,500,000 intended/completed operations and identical logical trace/write contents within a backend pair. Report achieved demand, dropped churn, actual duration and censoring; an incomplete fork is not a complete latency distribution.

Primary service endpoint remains **p99.9**; p99 and higher service tails and read/update distributions are diagnostics. Scheduled-response p99.9 is the explicitly labelled follow-up endpoint, with p99.99/p99.999 and strict stall/exceedance probabilities secondary. Service inside a paced workload does not become saturated service by changing its label. Quantiles stay per fork, seeds/regimes remain separate, and zero observed stalls do not establish zero risk.

Four separately labelled matched controls use 12/2/4-second phases at this arrival rate: timer floor, single 20 ms injected stall, fresh-supply floor at each payload. Validate conservation and injected service/response visibility before dependent workloads. Retain every control warning. These controls establish accounting/observability, not neutrality or long-run rare-event precision.

## Quality and interpretation

Keep the native exclusive lock/scope, host readiness, immutable/resumable slots, source/runtime fingerprints and all raw-data audit requirements. The runtime must match the prior service cohort byte-for-byte; no recompilation while another performance experiment measures. Both backends receive the same common ballast and offered churn, not equalized heap occupancy. Record actual worker PID/cgroup, GC intervals, compilation, allocation, RSS, power/thermal/CPU and lost allocation demand. Preserve contrary, warning-bearing and failed outcomes; no replacement slots or retrospective measurement-window selection.

Compare service rankings across the declared traffic regimes as a load-regime sensitivity, not an isolated causal heap intervention. Compare the two payloads **at the same arrival rate and ballast levels**. A baseline advantage, a reversal between observed endpoints, an unresolved middle, no reversal, or a feasibility boundary are all valid outcomes. Do not interpolate an exact or universal crossover. The three ballast levels can constrain an observed response bracket, but two pairs cannot supply a precise population threshold interval.
