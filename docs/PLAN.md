# Experiment plan

See the [experiment status](TAILCACHE_CURRENT_STATE.md) for completed comparisons,
[scope](SCOPE.md) for the workload boundaries, and [methodology](METHODOLOGY.md)
for timing and acceptance rules.

| Comparison | Completed evidence |
| --- | --- |
| Original heap-pressure campaign | [Final acceptance and limitations](TAILCACHE_12_FINAL_OUTCOME_REVIEW.md). The joint unconditional protocol remains `NO_GO`. |
| Short-trace pressure midpoint | [0, 104, and 208 MiB paired results](TAILCACHE_MIDPOINT_RESULTS.md). The 104 MiB direction remains mixed. |
| Payload and service-latency comparison | [Saturated pressure and write-rate matrix](second-host-20261120/pressure-write-02/CAMPAIGN_REVIEW.md). |
| Write locality under scheduled arrivals | [Two-host comparison](second-host-20261120/locality/CROSS_HOST_REVIEW.md) and [matched write-throughput follow-up](nov23-popos-followup/README.md). |
| Split timing of value construction and cache updates | [Both Pop!_OS pilots](nov23-popos-followup/README.md#split-write-timing-qualification) failed the predeclared 5% ratio-shift gate. Keep their component timings as diagnostics. |

## Repeat an existing comparison

Use the [portable collection guide](PORTABLE_EXPERIMENT.md) to choose a frozen
suite. Verify retained evidence first when the question is about an existing
result. The [offline verification commands](EXPERIMENT_EVIDENCE.md) require no
new benchmark run.

For a fresh run, record the source, JDK, dependency bundle, host, configuration,
seeds, paired order, and output directory before collection. Run functional,
timing-floor, and known-pause controls first. Keep source-matched warning and
rejection rules and preserve completed slots on interruption. Confirm the raw
histograms, counts, workload schedule, and report before comparing directions.

## Separate follow-up comparisons

- **Split timing.** Measure A/A repeatability with the original timer before
  attempting another source-matched split-timing qualification.
- **Collector sensitivity.** Repeat the matched write-locality comparison under
  a separately declared collector or heap configuration.
- **Caller-buffer reuse.** Compare ordinary `get` and `getUsing()` with explicit
  rules for whether callers retain or immediately consume each value.
- **Persisted access and shared workloads.** Use separate warm mapped, cold/open,
  and shared-cache protocols. Record filesystem and page-fault evidence for
  file-backed runs.

[Historical plans and outcomes](EXPERIMENT_EVIDENCE.md#historical-records) retain
individual protocol decisions and results.
