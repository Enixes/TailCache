# Task 12 implementation and researcher review — 2026-10-13

Implemented locally on `nacht` in `/home/y/TailCache`, branch `tailcache-12-crossover`, starting from `c008dad`. The seven-stage plan was saved before implementation. This delivery completes the dedicated 12A workload and the functional pause-capture portion of 12B. **Task 12 remains open; no pilot or crossover campaign was launched.**

## Workload contract and 12A evidence

`CrossoverWorkload` is shared by JMH and the every-operation runner. It populates incrementally, retains boxed keys and primitive version metadata, and supplies a fresh deterministic immutable array on each existing-key write. Each array is owned by one insertion; later writes never mutate it. Ordinary Chronicle `get` remains the parity path. Fresh allocation and generation belong to the measured boundary for both backends. A 40,000-operation uniform trace contains exactly 38,000 reads and 2,000 writes. Different throughput means paired elapsed-time forks consume different lengths of the same logical sequence; equal prefixes have identical values and operations.

Caffeine receives `ceil(1.25*N)` maximum size; Chronicle receives `2*N` entries with fixed-size values, bloat factor 1, tiering enabled, checksums disabled and analytics disabled. Full-content checks verify residents and every key outside measurement. Caffeine's frequency sketch is inspected during setup against the pinned 3.2.4 implementation; initialization was observed, rather than assumed from the ratio. This private inspection is deliberately diagnostic and fails closed if the implementation changes.

Common application data are touched small arrays in linked groups. Churn runs on an independent paced worker, retains a bounded ring, records offered and achieved payload bytes, actual worker JVM allocation, dropped demand and lateness, and caps catch-up batches. Cache throughput does not set its allocation rate. Object/array overhead makes actual JVM bytes larger than nominal payload bytes; both are retained. The smoke's achieved payload rate stayed close to its 8-MiB/s input, with zero dropped bytes and a 524,288-byte retained payload ring. This validates the control at the smoke input; it does not calibrate a severe-pressure condition.

The final full-GC/class-histogram diagnostic compared 512 and 8,192 resident 4-KiB values in independent JVMs. Java byte-array bytes grew by **4,112.26 bytes per additional Caffeine entry**, versus **2.55 bytes per Chronicle entry**. Repeated earlier diagnostics gave the same qualitative result. Together with the source ownership structure and parity tests, this supports absence of an `O(N*payloadBytes)` retained Chronicle payload bank over the inspected range. It is a differential class histogram, not a complete object-dominator census or proof of total off-heap memory savings. Library startup and common metadata remain part of measured heap occupancy.

The review repaired three implementation risks before proceeding: propagated churn-worker failures/corroborated JVM allocation, corrected a Gradle configuration-cache wrapper failure, and removed large common metadata containers that could enter G1's humongous-object path. The trace is about 320 KiB and supported resident metadata is bounded to 32,768 keys. Extending that range requires revisiting/chunking metadata before calibration.

## Every-operation recorder and 12B evidence

The instrumented channel retains service duration, inter-completion gaps, completed counts, actual worker timestamps, rare-stall counts/events, and per-iteration HdrHistogram bins plus compressed histograms. The recorder is single-writer, preallocated, uses three significant digits, has a 60-second range, and rejects histogram/event overflow. Histogram recording passed a thread-allocation test. All measurement recorders are created before warmup and exported after the final measurement window; moving export out of iteration gaps removed a source of allocation carried into the next measurement. Its additional retained memory must still be included in channel calibration.

Known 50-ms operations were observed in service intervals for both backends. The final two-window GC validation confirmed logged `System.gc()` pauses and overlapping worker evidence:

| Backend | Logged full-GC pause | Observed completion gap | Largest service interval | Clock alignment uncertainty |
|---|---:|---:|---:|---:|
| Caffeine | 13.264 ms | 13.454 ms | 13.454 ms | 1.091 ms |
| Chronicle in-memory | 27.920 ms | 28.117 ms | 1.910 ms | 1.046 ms |

The Chronicle pause occurred between measured calls: service durations alone did not cover it, while the completion gap did. This validates retaining both channels. It does not turn gaps into service latency, add an arrival model, or apply coordinated-omission correction. A single rare pause among millions of operations can leave p99.9 unchanged; maximum/stall counts and pause exposure are necessary alongside percentiles.

Every exported service and gap histogram count matched its measurement's completed-operation count. The final timer-only floor had p50 around 16 ns and p99 around 51 ns, but these are short diagnostic observations on a disturbed host and are never subtracted from percentiles. Low-pressure sampled/every-operation comparisons were retained as observer characterization, **not qualified coherence evidence**: independent repeats and a frozen acceptance rule remain required.

## JIT and host qualification — failed, subsequent blocks suspended

The final workload's first compiler qualification point used Caffeine, 256 B, 8,192 residents, 8-MiB retained application data, 16-MiB/s offered churn, G1 and a fixed 512-MiB heap. After 12 warmups, JMH's compiler profiler reported **93 ms** over eight measured seconds, above the predeclared 80-ms aggregate ceiling. Its per-iteration values were `1,3,29,20,0,3,2,35` ms, exceeding the 10-ms per-iteration rule. The narrower worker envelope recorded `0,2,26,20,0,0,1,0` ms. Thus broad reporting overhead explains some activity, but there is also compilation within the worker envelope. These counters measure whole-JVM compiler time, not pause duration or a specific method's causal effect.

The prototype investigation also retained 12- and 30-warmup probes, method compilation/deoptimization XML and raw GC logs. Longer warmup reduced the prototype's aggregate, but still failed its per-iteration rule. The source changed afterward to bound the trace, so those earlier probes are not a controlled warmup comparison for the final workload and do not freeze a new duration. No acceptance rule was relaxed after seeing results.

The final compiler block also failed the host screen because swap-in/out counters increased. Most functional blocks had pressure/paging rejection reasons. The monitor samples cumulative PSI and swap counters throughout each Gradle block, storing raw samples, rather than relying only on boundary snapshots. It covers the full launch/diagnostic block and does not attribute every host event to a timed operation. On host failure the driver suspended the remaining seven qualification blocks; missing points are explicit, not silently considered passing.

**12B qualification is incomplete.** Functional pause capture passes, but repeated host/JIT qualification and observer effects do not. Calibration bands, pilot cells, the 16-condition campaign and statistical inference are absent. “No crossover” would be unsupported at this stage.

## Reproduction, verification and next unit

Thirty-one unit tests passed, with no failures/errors; JMH classes compile. Tests cover paired logical contents/fresh ownership, exact mix, bounded application/churn retention, real churn allocation, zero-allocation recording, between-call gaps and both overflow paths. The final validation bundle passed its functional audit, and the raw-data replay reproduced the decisions with hash checks. All these artifacts are explicitly `reportable=false`.

Commands from the checkout (new IDs required):

```sh
rtk proxy ./gradlew --offline test compileJmhJava
rtk proxy python3 scripts/tailcache12.py validate <new-attempt-id>
rtk proxy python3 scripts/tailcache12.py pause <new-attempt-id>
rtk proxy python3 scripts/tailcache12.py jit <new-attempt-id> --warmups 12
rtk proxy python3 scripts/tailcache12.py audit <existing-attempt-id>
```

Evidence is under `build/reports/tailcache12/12ab-final-20261013`, `12b-pause-bounded-20261013` and `12b-jit-bounded-20261013`, plus their manifest-linked child directories. Earlier attempts and the configuration-cache failure are retained. Source archives preserve the exact uncommitted code used at each diagnostic, with Git HEAD/status, hashes, JVM flags, command lines and raw monitoring. Archive these outside disposable build output before cleaning.

Next resolve repeated host/JIT and observer qualification without changing the result-selection rule, then implement 12C/12D: actual post-GC occupancy/concurrent-cycle evidence, exact pause/window overlap parsing, calibrated input bands, and complete fail-closed quality schemas. These gates precede 12E's eight-cell pilot. The fixed heap/resident/churn defaults are exploratory controls, not a frozen campaign protocol.

## 2026-10-18 tooling and transfer update

Added a calibration runner with counterbalanced independent JVMs, resumable manifests, raw-hash replay, fingerprint/configuration checks, and measured backend-specific occupancy bands. The new GC parser uses the same `timenanos` clock as worker windows, clips pauses crossing window edges, retains post-collection heap and old/humongous regions, distinguishes concurrent cycles and reports pause exposure/frequency. Missing GC/region evidence, lost histogram counts and incomplete grids fail closed. This implements calibration tooling; a full accepted grid is still absent.

The host monitor now also checks compressed-swap (`zswpin`/`zswpout`) traffic, power/governor changes, OOM counters and monitoring failures. Plain swap counters had missed compressed-memory paging. The local host continues to fail these conservative screens. At the user's request, qualification/campaign execution will move to a larger machine.

Iteration formatting, percentile queries and exports in the every-operation runner now occur after all measurement windows. JMH observations are buffered and written to a per-fork CSV at JVM shutdown: printing during trial teardown contaminated the final broad profiler envelope, and shutdown stdout was not reliably retained. The CSV is required by new compiler qualification attempts. Cache integrity verification/close remain part of trial teardown; the existing broad JIT screen remains unchanged and can still reject compilation from that wider envelope. Narrower worker counters support investigation and do not override rejection.

A paired 256-MiB-heap diagnostic at 8,192 resident 4-KiB values, 64 MiB retained application data and 32 MiB/s churn produced complete histogram/GC evidence. Caffeine had seven measured pauses; Chronicle had 44. An independent raw-line recomputation matched the logged-duration totals (17.974 and 47.079 ms). Clipped clock-window exposure was 17.972 and 47.039 ms. Both recorded zero humongous regions and met the churn screen, but both were rejected for host paging. These figures validate the pipeline and are not backend performance findings.

Known-pause validation passed again: raw full-GC pauses of 12.469 ms (Caffeine) and 20.112 ms (Chronicle) were covered by worker completion gaps. Direct clock matching confirms both without the former millisecond-clock alignment tolerance. A new 30-warmup compiler attempt still failed the unchanged broad JIT limits and host screen, so subsequent qualification blocks remained suspended. The final per-fork CSV export was checked with a short functional compiler smoke; it is not a reportable JIT qualification.

The transfer runbook documents preparation, functional validation, qualification, calibration, replay, candidate input bands and archiving. The Python drivers no longer require RTK on the destination machine. Raw local evidence remains ignored under `build/reports/tailcache12`; it is not included in the source push. Pilot/campaign orchestration and inferential summaries remain future work; the analysis module's block-bootstrap helper alone does not complete 12G.
