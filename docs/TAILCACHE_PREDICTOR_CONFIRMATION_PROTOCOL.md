# Fresh confirmation of pilot-derived drain model — 18 November 2026

Primary30-fork validation and audits are complete. Original before-run0.5–2% crossover forecast failed: at0.5% writes all three pairs already favor Chronicle;0% favors Caffeine. Preserve this failure. M1 called15/15 p99.9 winners, tied by the lower-total-GC baseline, but median relative numerical error is50.5%. These are finite-window/transient-qualified observations, not unconditional steady-state passes.

The separate M2 candidate was specified atafe73bd after the pilot while primary collection was running, before its outcomes were unblinded. Its frozen rule passes: median absolute p99.9 error139188.5ns versus210316.5ns M1, p90 303809ns versus443890ns. This first30-fork secondary assessment is model-development evidence; fresh confirmation must not be pooled with it or the qualification data.

## Fixed fresh test

Exactly **12 new research JVMs**: write basis points0/50/500 × backends Caffeine bounded-default / ordinary Chronicle × two paired seeds44811/44812. Fixed shuffled cell order, alternating backend order; capture all complete/contrary/warning-bearing outcomes, no replacements. Same measured classes, G1512MiB,4KiB payload,32768 residents, zero application ballast,50k/s,32MiB/s common churn,120/4/30-second phases, continuous stream and identical actual paired write counts. The earlier qualification's transient warning remains; no retroactive steady-state claim. Existing four controls and three functional JVMs are reused, not counted again as fresh checks.

Primary outcome: all-fork response-p99.9 numerical error of frozen M2 versus M1 and a newly explicit constant-quantile baseline. Secondary p99.99; p99/p99.999, GC, compiler activity, allocation, RSS and full tails remain diagnostics. M2 parameters/algorithm are unchanged; M0/M1 forecasts remain available but do not become newly fitted. Report winner coverage and errors per backend as well as overall. No significance or precise threshold claim from two pairs.

The constant numerical baseline is the per-backend/per-percentile median response from all three120-second-warmup pilot cells, including warnings. It is fitted only to pilot data, frozen before these12 and reported as an additional retrospective comparator on the primary30. This differs from the already declared constant-winner baselines.

A separate updated replication forecast (not the original prediction): response-p99.9 favors Caffeine at0%, Chronicle at0.5% and5%, based on primary30. Freeze it before fresh collection. A mixed or contrary fresh result is retained and reported, never used to alter the model or pick a different seed.

## One diagnostic JVM, not research replication

Before the12, run **one Caffeine2%-write diagnostic JVM** with the same phases/classes plus compilation-only JFR and timestamped JIT completion logs. Nine primary forks exceeded the80ms compilation warning after120s warmup; this probe asks which methods/tasks cause it. Its instrumentation changes and single-arm selection are explicit, it is not a replacement, and its latency distributions do not count toward confirmation. Retain command/source/raw hashes and event files. Do not erase existing warnings even if the probe suggests counter/window effects. All measured confirmation forks retain the original flags, without JFR/JIT debug logging.

No extra control/benchmark expansion follows automatically. After the fixed12, independently audit HDR/stream/GC/RSS/source, score immutable predictions and updated replication forecast, review every warning and numerical limitation, and finish the paper/artifact. Any further intervention needs its own worth justification within the user's eight-hour budget; obtaining a desired win is not a stopping criterion.
