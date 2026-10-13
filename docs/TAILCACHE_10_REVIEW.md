# TailCache 10 — secondary-work decision and researcher review

## Final decision on 2026-10-04

**NO GO for secondary experiments. TailCache 10 is closed as a scope decision.**

Candidate B materially improved the TailCache 08 environment: boundary memory PSI stayed at zero, swap use fell, diagnostics recorded zero major faults/read bytes, and the 4-KiB order comparisons were stable. A later 12/8/3 targeted replication also brought all 256-B two-order p99 ratios below 1.25. Nevertheless TailCache 08 still fails its conservative JIT gate, and—more importantly—TailCache 08 is not RQ1/RQ2 at all.

The primary heap/live-set crossover workload has not yet been implemented. RQ1 and RQ2 therefore remain `missing`, while persisted-warm remains `invalid` for promotion because its machine-quality artifact is an overall rejected TailCache 08 candidate and primary-fork residency is not directly proven.

`scripts/tailcache10_gate.py` must consequently return `NO_GO`. This is the intended scope guard, not an unfinished task.

## What is cut

Do not start, in current priority order:

1. persisted two-JVM sharing;
2. Chronicle `getUsing` / object-reuse sensitivity;
3. cold/open/page-fault behavior;
4. eviction simulation.

TailCache 09 remains useful as a completed capacity/sizing diagnostic, but its timing validation is not expanded merely to consume the remaining schedule.

## What work is protected instead

The next engineering/research work belongs to Milestone 1 and the primary RQ1/RQ2 campaign:

- validate a pause-sensitive latency method rather than relying on SampleTime alone for GC-tail claims;
- remove the Chronicle replacement-value heap shadow from the crossover path;
- add backend-neutral allocation/churn;
- define measured live-set/old-gen pressure levels and occupancy semantics;
- verify warmup/JIT stability or explicitly redesign the measurement policy around the observed compiler behavior;
- then sweep Caffeine versus Chronicle in-memory across pressure and payload size.

## Audit and claim limit

The gate consumes explicit `sound`, `invalid` or `missing` states plus the cited evidence artifact and schedule reserve. Missing remaining research hours fail closed. A synthetic all-sound input has already verified that the priority ordering is encoded.

This decision says nothing about whether two-JVM sharing, `getUsing`, cold starts or eviction would perform well. It only says they should not be run before the primary crossover evidence is sound.
