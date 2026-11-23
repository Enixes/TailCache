# Task 12 completion execution plan — 5 November 2026

This plan precedes the remaining implementation. The work continued from the retained WSL and native attempts, applying the experiment gates in order. Previous 96-warmup compiler qualification remains scoped to its archived sources and native host-v2 screen; a changed observer needs fresh matching qualification.

## 1. Native observation and review

Use a temporary, user-owned systemd scope for the benchmark controller and its descendants. The real host probe successfully created such a scope without CPU pinning. Launch Gradle with `--no-daemon` inside it so a shared daemon cannot put worker JVMs outside the accounted group. Retain worker cgroup evidence and reject a mismatch. Do not set CPU quotas, affinity, priority or memory limits.

Retain raw aggregate `/proc/stat` counters and the scope's cgroup-v2 `cpu.stat usage_usec`, sample brackets, CPU count/clock tick rate, CPU pressure/load, available frequency/temperature/throttling counters and ancestor resource controls. Compute outside-scope busy CPU from the two accounting sources, with a conservative read/quantization uncertainty bound. Reject missing, nonfinite, nonmonotone, stale, inconsistent or mismatched accounting. CPU acceptance uses the final ten settling seconds plus measurement windows; preflight uses its full window. Initial ceiling: outside-scope CPU upper bound no greater than 10% of total logical-CPU capacity. Preserve full-block power, memory PSI and paging rules; native minimum available RAM is 1 GiB. Record missing optional sensors explicitly; reject an observed thermal critical limit or increasing thermal-throttle counter.

Version this as a new host rule and measurement identity. Old attempts must replay under their original rules. Qualify accounting with synthetic counter/clock/containment failures and a real temporary-scope probe. The kernel's cgroup-v2 `cpu.stat` and systemd's transient-scope documentation are the implementation references:

- https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html
- https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html

## 2. Measurement preparation and observer study

Keep the validated candidate 96 one-second warmups, eight measurements, 32,768 residents, fixed 512-MiB G1 heap, seed 24301 and current numerical compiler limits. Requalify functional/pause evidence, both complete two-order compiler screens and matching pressure diagnostic under the new observer. Do not relax limits or combine old forks to fill a new attempt.

Implement a separate counterbalanced observer study: timer floor, common fresh-value supply floor, ordinary unprofiled SampleTime and every-operation channel at identical low/high candidate inputs. Use independent JVMs and retain raw counts, service versus completion-gap distinctions, achieved churn, host/compiler acceptance and sampled/complete endpoints. Predeclare sample adequacy and floor ratio criteria; treat cross-channel direction and pause capture as coherence evidence rather than requiring equal percentile values. Review before primary protocol freeze. A floor is descriptive and is never subtracted from a percentile.

## 3. Calibration and pilot

Run a fresh 64-JVM, both-recorder candidate calibration with the existing common inputs and unchanged occupancy/churn/replica gates. No Windows-only replacement policy applies. Stop on quality rejection and retain it. Revise a demonstrated workload/pressure problem in a new declaration; no ranking-based reruns. Independently recompute GC/window exposure from retained logs and inspect measured bands, sustainable high-pressure coverage and absent sensors.

Run/review the guarded eight-cell pilot only with matching passed prerequisites. Pilot results cannot enter the confirmatory campaign. Freeze durations, sample/tail/GC exposure, variance, observer/coherence rules, pressure bands, seeds/order and bounded rejection handling before confirmatory collection.

## 4. Campaign implementation and review

Implement immutable protocol, schedule, resume, per-fork audit and final acceptance commands. Run 16 conditions × two counterbalanced passes × three fresh forks per primary channel (192 primary JVMs), plus declared supporting diagnostics. Use paired independent-fork/block statistics and histogram endpoints. Declare robustness seeds before their use; evaluate candidate crossings and adjacent pressure points on two additional seeds as separate evidence. Preserve all valid noisy forks and every rejected/missing condition. No global no-crossover claim is permitted for missing pressure coverage.

## 5. Delivery

Produce a source-matched analysis-ready dataset, coverage and uncertainty tables, RQ1/RQ2 claim limits, researcher review after each implementation unit, machine-readable status and a verified raw/source archive outside `build/`. Mark Task 12 complete only when the final acceptance work is done; a launched job or partial grid is not completion. Long durations are expected: the 96-second warmup makes calibration, pilot and campaign multi-hour stages. One benchmark driver runs at a time, and development/analysis work stays outside timed collection.
