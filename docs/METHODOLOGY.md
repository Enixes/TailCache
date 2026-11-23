# Experiment methodology

## Cache and workload contract

Caffeine stores values on the Java heap and returns the cached reference.
Ordinary Chronicle Map `get` materializes a Java value from its off-heap entry.
Both backends receive fixed-size, immutable byte-array values and pre-boxed keys.
Caffeine's `maximumSize` is an eviction limit. Chronicle Map's `entries` is a
sizing input. The runner verifies the resident count and cached values and logs
the backend configuration.

The portable workload uses a deterministic stream indexed by operation ordinal.
Reads span the resident set. Writes select from an explicit eligible set and
allocate and fill a fresh value inside the operation. It retains key and version
metadata alongside the cache. Added live application data and offered background
allocation are independent controls. The heap occupancy, delivered churn, and
process memory are measured outcomes.

Chronicle uses a constant-size value layout, `putReturnsNull(true)`, and disabled
analytics. A maximum bloat factor of 1.0 still allows normal segment tiering under
the explicitly enabled tiering policy. See the [portable profiles](../experiments/portable/)
for frozen heap, payload, seed, load, and warning settings.

## Timing boundaries

| Channel | Interval |
| --- | --- |
| Saturated service | From the start of a benchmark operation through result consumption, with back-to-back operations. Includes fresh value creation on writes. |
| Scheduled response | From intended arrival to that operation's completion. Includes time waiting for the worker and retains overdue requests. |
| Completion gap | Time between completed operations. Includes loop and recorder work. |
| Read and update service | Service histograms restricted to their respective operation types. Their counts reconstruct combined service. |

The portable runner records every operation for service, and every scheduled
response in a positive-arrival-rate profile. Timer-floor, value-supply, and
known-pause controls are recorded separately. Percentile floors are never
subtracted. The [optional split timing](PORTABLE_EXPERIMENT.md#split-write-timing-on-the-pop_os-host)
uses a separate qualification. Both retained split pilots failed their gate.

## Evidence and interpretation

- Freeze source, runtime and host metadata, workload inputs, pair order,
  measurement windows, and warning rules before a run. Equal offered demand
  allows differences in achieved throughput, churn, and total heap occupancy.
- Preserve per-fork histograms, count support, GC and safepoint windows, allocation,
  heap occupancy, RSS, and host observations. Verify raw histograms, schedule,
  operation conservation, values, and report provenance before interpreting them.
- Compare backends within matching pairs. Report fork variation and warnings, along
  with a separate warning-free view. Mixed or missing pairs are unresolved. An
  OOM or evacuation failure may be a workload outcome and stays in the record.
- Retain p99.99 and p99.999 with their support counts. A burst of delayed requests
  can share a single pause. Keep hosts, observers, trace variants, and API
  contracts separate. Heap occupancy and total process memory are distinct.

## JMH validation and the original campaign

`CacheSmokeBenchmark` checks individual hit, miss, and overwrite paths with
per-worker caches. `CacheWorkloadBenchmark` shares one cache across workers and
uses preallocated replacement values, a different allocation contract from the
portable workload. The shared-cache smoke exercises 16 workers. JFR and allocation
profiling are diagnostic channels. The
[benchmark configuration](../build.gradle.kts) defines the smoke parameters.

The original [Task 12 protocol](TAILCACHE_12_PLAN.md) compared sparse JMH timing
and an every-operation recorder. It used a different periodic trace and qualified
only within its [observer-conditional scope](TAILCACHE_12_FINAL_OUTCOME_REVIEW.md).
The [cliff diagnostic](TAILCACHE_12_CLIFF_DIAGNOSTIC_AND_SYNTHESIS.md) used synthetic
arrival correction. The portable scheduled-response channel measures the offered
schedule directly.

For persisted tests, warm and prefault mapped pages before measuring steady-state
access. Retain mount, filesystem, storage, and page-fault evidence. Opening and
first-touch latency belong to a separate diagnostic. See the
[persisted-mode review](TAILCACHE_08_FINAL_REVIEW.md).
