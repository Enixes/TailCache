# Task 12 native Linux qualification — 4 November 2026

## Scope and prospective controls

Continue the pulled `491988b` checkpoint on native Linux `nacht`. The October WSL qualification and rejected calibration grids remain historical evidence; their raw archives were not imported into this checkout. Do not combine forks across machines, environments, rejected attempts or warmup settings.

Java is `/usr/lib/jvm/java-21-openjdk`, OpenJDK 21.0.12.1+1. Graphical login, Docker/socket and containerd were stopped; Codex CLI remains available. Clear the WSL observer and controller-scheduling environment variables. Keep G1 and the fixed 512-MiB heap. All evidence here is diagnostic and `reportable=false`.

Before timing, 34 Java and 40 Python tests passed, with no Java failures, errors or skips; JMH and result-tool classes compiled. Environment and copied Java test XML are in `build/reports/tailcache12/native-nacht-preparation-20261104-001/`.

## Completed evidence and research review

| Attempt suffix (all dated `20261104-001`) | Result |
| --- | --- |
| `native-nacht-quiet` | 61 samples, 60 consecutive quiet seconds passed |
| `native-nacht-functional` | Raw replay passed; all 14 existing host screens passed |
| `native-nacht-pause` | Two-window GC-pause validation and raw replay passed for both backends |
| `native-nacht-jit60` | Complete 8-block screen rejected: 8/8 host checks passed, 5/8 compiler checks passed |
| `native-nacht-quiet96` | Fresh 61-sample quiet preflight passed |
| `native-nacht-jit96` | Complete screen rejected: 8/8 compiler checks passed, 7/8 host checks passed |

The differential byte-array retention slope was 4,112.18 bytes per additional Caffeine entry and 1.80 bytes for Chronicle at a 4-KiB payload, comparing 512 and 8,192 residents. This supports absence of an O(entries × payload) retained Chronicle payload bank in that range. It is not a total-memory or dominator census.

The separate pause experiment matched Caffeine's logged 9.554-ms full GC with a 9.741-ms completion gap, while its largest service interval was only 0.062 ms. Chronicle's logged 12.582-ms pause matched a 12.717-ms gap. This independently reproduces why completed-call service timing alone can miss between-call pauses. Neither injected pauses nor these short runs provide primary latency endpoints.

At 60 warmups, Chronicle failed three per-iteration compiler checks (29, 15 and 12 ms; limit 10 ms). Narrower worker counters also failed (28, 14 and 11 ms). XML's largest possibly overlapping tasks include TreeMap serialization and JDK bytecode generation; task wall time is not compiler CPU time or pause time. These observations motivated a prospective preparation experiment, not a relaxation or retrospective acceptance.

`warmup96-declaration.json` was saved before the 96-warmup attempt. It applies the same 96 one-second warmups and eight measurements to both payloads/backends/channels, keeps 32,768 residents, the source code and the 80-ms aggregate/10-ms-per-iteration compiler limits unchanged, and requires both complete independent compiler screens. Latency endpoints were not used to select the preparation duration.

At 96 warmups, all eight JMH compiler checks passed: totals 3–16 ms, maximum iteration 9 ms. The final Caffeine/4-KiB host log nevertheless contained 37 AC-disconnected samples, followed by reconnection. Memory-full PSI and swap/zswap/OOM counters remained zero. Raw replay preserves this power rejection. A complete screen cannot be accepted from seven host-passing forks; no native replacement-fork policy was declared.

The user subsequently confirmed the charger is firmly connected and stable. The next attempt must use a fresh quiet preflight and a complete new 96-warmup JMH screen. Do not replace only the rejected fork or resume the old screen. If that screen passes, run the complete independent every-operation compiler screen and the matching pressure diagnostic before reviewing calibration readiness.

## Limits still requiring work

- The short functional observer/floor comparisons do not qualify independent observer coherence or overhead.
- The current native Linux host screen observes PSI, swap/zswap/OOM counters, governor and power stability. Its competing-CPU rule depends on the Windows observer and therefore does not apply on native Linux. No per-block native competing-CPU or thermal/frequency qualification is established by these runs. Review native observation coverage before accepting a primary dataset.
- A passing compiler screen at the probe inputs cannot establish pressure calibration, pilot acceptance or a crossover. Both recorder-specific occupancy calibrations and all later acceptance gates remain open.
- Keep the old WSL retry policy scoped to WSL. No CPU retry flag or replacement policy is adopted for these native runs.

Task 12 remains incomplete, with `campaignReady=false` and `reportable=false`. Raw and derived attempt directories remain under `build/reports/tailcache12/`, ignored by Git; preserve their manifest-linked sibling directories and source archives together.

## Second power rejection and user-requested reset

After the charger-stability confirmation and a fresh 61-sample quiet pass, `native-nacht-jit96-20261104-002` stopped at 5/8 blocks. All five completed compiler checks passed (totals 3–16 ms, maximum iteration 7 ms); four host checks passed and the fifth rejected AC disconnection/change. The remaining three blocks were suspended. Raw replay confirms rejection. The user independently reported another power fluctuation and requested a reset.

Reset means preserving both rejected 96-warmup attempts and starting a new complete screen, not deleting reports, resuming missing blocks, pooling their forks or changing acceptance thresholds. Before attempt `native-nacht-jit96-20261104-003`, require a prospectively longer 120-consecutive-second quiet preflight, with a 300-second timeout, under `native-nacht-quiet96-20261104-003`. Launch only if that preflight passes; stop again on any in-block power failure. This is a stricter preparation interval, not proof that power cannot fluctuate later. Independent every-operation qualification and pressure calibration remain unstarted.

The user reported another power fluctuation during preparation and requested another reset. Quiet preflight003 completed with 121 apparently quiet samples, but is explicitly superseded by that external report and must not authorize launch. The narrow stop request did not execute because automatic permission review timed out; the preflight completed independently and no Java benchmark was launched. Preserve its raw result and reset marker. Start fresh preflight004 with the same 120-second requirement before screen003.

## Replayed native compiler checkpoint

Fresh preflight004 passed with 121 samples over 120 consecutive seconds. The complete new `native-nacht-jit96-20261104-003` screen then passed all eight host and compiler checks. Raw replay passed; the maximum total compiler time was 10 ms and the maximum iteration was 7 ms. No earlier fork was used to fill this attempt.

Independent `native-nacht-everyop-jit96-20261104-001` passed all eight blocks in both orders and raw replay. Compiler totals were `[1, 0, 0, 0, 0, 0, 0, 0]` ms, with maximum iteration 1 ms. Both matching Caffeine/4-KiB/96-MiB-ballast replicas in `native-nacht-pressure96-jit96-20261104-001` also passed and replayed (totals 1/2 ms, maximum iteration 2 ms). Both channels used 96 warmups/eight measurements, with no changed Java source or compiler thresholds.

The full source archives for functional, separate pause, JMH, every-operation and pressure checks all match measurement-source fingerprint `866e0d76f0125b716007745824d2e85949a4c78ff9c4db0ef3ba0d4ff84a9888`. Across these five attempts, 34 collected blocks passed the existing host screen. `qualification-checkpoint.json` in the preparation directory records hashes and scope. Complete source archives differ where dated review/status documents evolved; the selected measurement sources match exactly.

This qualifies compiler preparation for the tested native probe inputs under the existing screen. It does not establish native competing-CPU/thermal observation, independent observer coherence, a calibrated pressure grid or reportable latency evidence. The native CPU coverage gap must be addressed prospectively before accepting the main dataset; changes to measurement controls require fresh source-matched qualification. No benchmark driver remains running, and calibration/pilot/campaign were not launched. Historical WSL qualification metadata is retained separately in the status file.
