# TailCache: Heap Pressure, Allocation and Tail-Latency Tradeoffs in Java Caches

**Revised working draft — 16 November 2026.** This version incorporates source/data, raw-evidence and research-method reviews. It is not a submitted or author-approved preprint. Author names, affiliations, contributions, acknowledgements, final licence and tool-use disclosure require author agreement. Citation keys refer to [references.bib](references.bib); exact claim boundaries and evidence identities are in [CLAIMS.md](CLAIMS.md). Full captions and vector figures are in [FIGURES.md](FIGURES.md).

## Abstract

Moving cache values off the Java heap can reduce retained heap pressure while introducing materialization costs on access. We compare Caffeine and Chronicle Map using saturated operation service latency and response measured against a fixed intended-arrival schedule. A separately planned follow-up uses 4 KiB values, a 512 MiB G1 heap and three paired JVM repetitions at each of three application-retention levels, plus two additional seeds analysed separately. At zero additional ballast, response p99.9 is 24–33 µs for Caffeine and 282–325 µs for Chronicle. At 208 MiB it is 921–1,189 µs and 239–334 µs, respectively; the 104 MiB comparison remains mixed. Chronicle's response p99.99/p99.999 advantage already exists at baseline. Historical saturated-service experiments give different, percentile-specific rankings. At 208 MiB, Chronicle uses less post-GC Java heap but has higher sampled RSS: approximately 795–812 MiB versus 600–605 MiB. These exploratory results identify a repeated endpoint ranking reversal, not an exact or universal threshold. We preserve qualification failures, compiler warnings and per-fork provenance, and provide offline figure reproduction.

## 1. Introduction

A Java cache can trade memory for reduced application work, but the retained objects and their lifecycle also affect collection and access costs. Moving values outside the GC-managed heap changes that balance. Ordinary reads can reconstruct heap objects, while reuse APIs can change the caller's ownership obligations. Consequently, an off-heap implementation need not be uniformly better in latency, allocation or total process memory.

TailCache examines this decision for two versioned libraries under controlled application retention and allocation demand. The original questions concerned operation latency: **RQ1**, whether increasing application heap pressure produces a p99/p99.9 advantage for ordinary Chronicle access over Caffeine; and **RQ2**, how payload size changes that result. We preserve these questions even where the answer is negative or unresolved. A later, explicitly identified follow-up asks the analogous question for scheduled response, which includes backlog after stalls. It does not replace the service-latency question.

The contribution is a bounded empirical case study with three results: a separately planned repetition of a response ranking reversal whose intermediate point remains mixed; evidence that the percentile and timing boundary can change the library ordering; and an observed separation between retained-heap relief and total process residency. The accompanying artifact makes per-fork evidence, warnings and figure generation inspectable. These are workload-specific observations, not a general cache-selection algorithm, a new GC architecture or discovery of the underlying tradeoffs.

## 2. Related work

### 2.1 Cache retention and garbage collection

Nunez, Guyer and Berger introduce prioritized garbage collection and a space-aware cache to manage the tension between caching benefits and collection costs [@nunez2016]. TailCache shares that motivation but evaluates existing libraries without modifying the JVM. We cannot claim the underlying cache/GC tension as new.

The closest practitioner comparison identified is Knasiecki's Caffeine-versus-OHC study [@knasiecki2022]. It varies cache item sizes and capacities and reports GC, median request time and throughput, including regimes where off-heap storage becomes advantageous. Our narrower distinction is common application ballast with fixed cache residency, separate service/response endpoints, repeated JVM observations, full-tail evidence and explicit warning/provenance records. Different library choices alone are not a novelty claim. This article is primary practitioner evidence, not a peer-reviewed paper.

### 2.2 Materialization and reuse

TeraCache addresses serialization costs in Spark by extending the managed heap over memory-mapped storage [@kolokasis2020]. TeraHeap similarly identifies serialization and renewed heap pressure when off-heap objects return for processing, and develops a second heap with different GC management [@kolokasis2023]. These systems establish prior motivation for avoiding materialization. Our ordinary-get allocation measurements concern an existing in-memory library API and do not reproduce their storage/runtime design or workloads.

Chronicle's versioned API documents reuse as a way to reduce garbage when the reader can populate a supplied value [@chronicle2026]. In TailCache, ordinary access and caller-buffer reuse are therefore separate contracts. Reuse results cannot silently stand in for ordinary access, and the retained sensitivity batches do not contain a matched three-arm comparison of Caffeine, ordinary Chronicle and reusable Chronicle.

### 2.3 Arrival models and JVM measurement

Schroeder, Wierman and Harchol-Balter show that independently arriving and completion-driven workloads can exhibit different response behavior [@schroeder2006]. TailCache applies this established distinction to cache pressure: back-to-back service durations and intended-arrival response answer different questions. Our schedule is generated in process and retains queue debt; it is not an external network-load experiment.

Traini and colleagues show that Java microbenchmarks do not necessarily achieve steady state and that fixed warmup estimates can be inaccurate [@traini2023]. We accordingly report compilation activity and historical qualification failures rather than declaring that a fixed warmup proves steady state. HdrHistogram supplies configurable finite-resolution distributions [@hdrhistogram]; its precision and the number of rare observations constrain interpretation independently of warmup.

This is a targeted comparison, not an exhaustive systematic literature review. The verification log records the primary sources and portions examined. The closest practical overlap already demonstrates the broad crossover premise; TailCache's contribution must therefore rest on the more specific measurements above.

## 3. Methods

### 3.1 Study sequence and separation of evidence

The investigation has distinct stages. The original Task 12 study attempted all 402 planned invocations, including 192 campaign slots and 64 robustness slots. An invocation is not always a single JVM because some functional controls contain multiple checks. Final acceptance retained 191 campaign forks conditionally and one hard rejection. The stopping policy was amended after interruption; the original unconditional protocol remains **NO_GO**. That stage measured sparse JMH samples and every-operation service timing and is not retrospectively qualified by subsequent work.

A separate 30-JVM cliff diagnostic selected regions of interest. Its synthetic expected-interval correction is not the response measurement used below. The focused exploratory stage subsequently collected 132 workload JVMs across 12 bounded batches, plus 36 controls. Batch choices adapted to the observations; two compiled-runtime groups and different measurement windows must remain distinct. Extreme-percentile/full-tail extensions to that stage were post hoc analyses of retained distributions.

The fresh midpoint follow-up was planned separately and collected on 10 November 2026. It comprised 18 primary workload JVMs and 12 seed-sensitivity JVMs, plus nine controls. All 30 workload JVMs completed. These are new repetitions rather than replacements for earlier rejected observations. Figures and derived evidence use stable identities `(dataset, batch, label)` and do not pool these stages.

| Evidence stage | Retained unit count | Measurement / interpretation |
| --- | --- | --- |
| Original conditional investigation | 402 invocations; includes 192 campaign forks and 64 robustness forks | Sparse/every-operation service observers; original unconditional protocol unqualified |
| Cliff discovery diagnostic | 30 workload JVMs | Region selection and synthetic expected-interval correction; not pooled |
| Focused exploration | 132 workload JVMs plus 36 controls | Adaptive batches, two compiled-runtime groups, 8 s or 30 s windows; exploratory |
| Midpoint follow-up | 18 primary plus 12 seed-sensitivity JVMs, nine controls | Predeclared bounded 0/104/208 MiB replication; 12/2/30 s phases; secondary seed cohorts kept separate |

The original campaign used 30 one-second warmups, eight conditioning intervals and eight analysed intervals at 0/96/208/288 MiB, rather than the later follow-up's phase counts. Its quality classifications and numerical outcome summary appear in Section 4.1 and [the complete original comparison table](ORIGINAL_CAMPAIGN.md).

### 3.2 Cache semantics and common workload

Both backends receive deterministic uniform keys, approximately 95% reads and 5% existing-key updates, with 32,768 resident entries. The trace has 40,001 operations, comprising 38,001 reads and 2,000 writes, and repeats; it is not an unbounded IID stream. The trace cursor resets at phase boundaries. Fresh update arrays encode key/version-dependent contents and remain immutable after insertion. End-of-run checks verify every resident value and entry count. The worker consumes a value byte into a checksum published through a volatile field, making measured work observable; this is not a formal proof against every compiler transformation.

Uniform describes trace generation, not equal visitation of all resident keys. Offline reproduction with the verified retained classes and matching configuration fingerprints shows that seed 24301 touches 23,169 distinct keys, including 22,570 read keys and 1,939 updated keys. The other 9,599 resident keys are absent from measured trace access, and 30,829 are never updated by that trace; setup and final integrity scans still visit all residents. Seeds 24302 and 24303 touch 23,109 and 22,991 distinct keys, with 1,945 and 1,944 updated keys. At the fixed arrival rate one full trace occupies 0.80002 seconds; a 30-second offered window contains 37 full periods plus a prefix. Resident retention, the active access set and the repeatedly updated subset therefore differ substantially.

Chronicle's ordinary `get` materializes a value array; Caffeine returns its retained array reference. We preserve this API-level difference rather than equalizing read allocation. Chronicle retains no heap bank of all cached payloads. The optional `getUsing` path populates a supplied caller buffer and verifies identity with that buffer; subsequent reads may overwrite it.

Caffeine is configured with `maximumSize=40,960` and its default common-pool executor; the initialized frequency sketch has 65,536 slots. Chronicle is configured for 65,536 entries, constant payload sizing, `maxBloatFactor=1.0`, segment tiering enabled, entry checksums disabled and null-returning puts. These capacity settings provide headroom for 32,768 residents; they are not asserted to have equal storage overhead. There is no eviction workload. One cache worker does not mean a single-threaded process: churn, JVM GC/compiler and Caffeine maintenance can also run.

This compares two complete library configurations. Their metadata, layout, maintenance, capacity headroom and access semantics differ along with value placement. The study does not isolate a causal effect of moving otherwise identical storage off heap.

### 3.3 Pressure, allocation and resource accounting

Application ballast means strongly retained application data independent of the cache, not a second copy of cache payloads. Its labels count byte-array payload, excluding object headers/reference-container overhead; zero denotes no additional ballast, not zero application/harness memory. Arrays are filled during setup. The fresh levels are 0, 104 and 208 MiB. Common background churn offers 32 MiB/s using 4 KiB allocations and a bounded 128-slot retention ring. Achieved payload bytes and dropped demand are retained. The backends receive the same algorithmic application demand; saturated runs can complete different total operation counts.

We hold application ballast and offered churn equal, not total heap occupancy. Equating total heap occupancy would remove the retained-heap difference under investigation. Worker allocation is reported per completed operation separately from churn. Post-GC used-heap summaries describe occupancy rather than an exact live-object census. GC pause exposure is the overlap of pause intervals with the measurement envelope divided by measured duration; GC and safepoint totals can overlap and must not be added.

Fresh process residency is sampled from `/proc/PID/status` at approximately 1 Hz. We report the measured-window sampled maximum RSS. This is neither an exact maximum nor PSS/native-allocation accounting, and equal JVM heap limits do not imply equal total-memory budgets. The study therefore cannot establish overall memory savings from a reduction in retained Java heap.

### 3.4 Timing boundaries and arrival schedule

For operation *i*, service is `completion_i − actualStart_i`. Saturated service runs execute operations back to back and form their own experiment. In scheduled runs, intended arrival is `phaseStart + i × 20,000 ns`, corresponding to 50,000 requests/s. Response is `completion_i − intendedArrival_i`. Intended times are never reset after a pause, and overdue requests are not skipped. The worker spins until future intended times and processes backlog serially; there is no separate producer thread or network queue.

Each fresh offered measurement window is 30 seconds, or 1,500,000 intended requests. A cooperative loop condition stops admitting subsequent operations once the previous observed completion reaches ten seconds beyond the offered end. This does not preempt an in-flight operation or impose a hard wall-clock bound. Incomplete completion would be censored rather than represented by a full latency distribution. All fresh forks completed every intended request. Gaps measure consecutive completion intervals and remain a separate diagnostic channel. Service within a paced run must not be substituted for saturated service from separate JVMs.

The timed operation includes trace traversal, value generation on writes, cache access and value-byte/checksum consumption. The completion timestamp precedes histogram recording, bookkeeping and the next operation's pacing. A pause occurring between operations can therefore affect gaps and later responses without appearing inside either service duration. Histogram recording/pacing can alter the workload even outside the individual service boundary; we make no observer-neutrality claim. Three-significant-digit HdrHistogram distributions retain counts and finite-resolution bin boundaries over the configured range. Quantiles use the pinned implementation's next-down/ceiling rank and upper-equivalent bin value [@hdrhistogram]. No timing-floor subtraction or synthetic correction is applied to directly measured response.

### 3.5 Fresh replication protocol

The fresh primary seed is 24301, with three paired forks per ballast. Additional seeds 24302 and 24303 each contribute one pair per point and are analysed separately. Within a pair, backends share trace and application settings. The complete cell order is deterministically shuffled, with alternating backend order; three pairs cannot provide perfect order balance. Each fresh JVM has 12 seconds of warmup, 2 seconds of conditioning and 30 seconds of offered measurement. These durations are the fresh protocol, not the original campaign's warmup settings.

The main fresh endpoint is scheduled-response p99.9. Secondary endpoints include p99, p99.99, p99.999, per-fork survival distributions and strict exceedance probabilities at 100 µs, 1 ms and 10 ms. We preserve all three ratios at each primary point. Consistent direction means all three complete pairs agree; this descriptive rule is not a statistical-significance test. The prospective adaptive rule permitted one point at 52 or 156 MiB only with complete clean, consistent endpoint/midpoint comparisons. Because 104 MiB was mixed and warning-bearing, that addition was skipped.

### 3.6 Runtime, host and quality records

Collection used one Intel Core i7-8750H host, with six physical cores and twelve logical CPUs, OpenJDK 21.0.12.1+1, G1 and `Xms=Xmx=512 MiB`. Dependencies include Caffeine 3.2.4, Chronicle Map 2026.1 and HdrHistogram 2.2.2. The earlier JMH campaign uses JMH 1.37. The fresh source archive SHA-256 is `782a41005d94954297debf9d4e2560a8f71cc3db496dc464f23efb01d7783dd0`; all 68 retained runtime files and the classpath match the later historical response cohort. The Python controller added seed handling and coarse RSS sampling; unchanged measured Java code does not establish unchanged observer interference. Historical runtime identifiers use their original fingerprint scheme and are not relabelled as fresh hashes.

Chronicle analytics is disabled through a checked JVM property, and tiering/capacity configuration is logged. The maps in this paper's focused comparison are in memory. Persisted warm access, cold/open faults and cross-process sharing are outside this scope; a populated in-memory map is not evidence about storage opening behavior. Host, power, thermal, mount and storage records accompany collection. The controller uses exclusive scope/locking, verifies retained slots on resume and does not replace noisy observations.

Nine floor/injected-stall controls passed integrity and request-conservation checks. They demonstrate observability within their control settings, not observer neutrality or precise long-run extreme-tail error bounds. Five fresh workload forks exceeded the declared 80 ms measured compilation-activity warning. At primary 104 MiB these were Caffeine block 1 (505 ms) and Chronicle block 3 (191 ms). No fresh host warnings, OOMs or censored arrivals occurred. Warning-inclusive results and clean-pair coverage are both visible; fixed warmup does not prove compilation-free steady state.

The no-host-warning statement concerns workload forks. All nine short controls retain a warning for missing native CPU settling/measurement coverage, and the seed-24302 injected-stall control also has a compilation warning. Each control has a single one-second measurement without the workload's warmup/conditioning sequence. They check accounting and stall visibility, not equivalent host qualification, a subtractable overhead correction or a calibrated 30-second tail distribution.

### 3.7 Analysis and uncertainty

All quantiles and curves remain per fork. Pair ratios divide Chronicle by Caffeine within the same batch, runtime, seed, payload, pressure, window and workload. Ratios below one favor Chronicle. No rejected histograms, outlier trimming, pooled percentiles or retrospective window movement are used. Min–max fork ranges are labelled ranges, not confidence intervals. Three primary pairs and one pair per added seed do not support a precise crossover confidence interval.

At an HDR upper-bin boundary, the empirical survival function counts observations strictly above that boundary. For a threshold inside a bin, definite and possible exceedance counts bound quantization ambiguity; they are not sampling-confidence bounds. Zero observed exceedances retain the observation count and do not imply zero risk. A 1.5-million-response fork has only about 15 nominal observations in the upper 0.001%; multiple queued responses may share one pause. We do not treat response count as the number of independent stall episodes or assign each latency outlier to a specific GC event using aggregate histograms.

## 4. Results

### 4.1 The original campaign does not establish an unconditional crossover

The original conditional evidence is informative but observer-dependent. In the every-operation regime, qualified 256 B p99.9 ratios are 0.479, 0.495 and 0.539 at 0/96/208 MiB: Chronicle's advantage is already present at baseline. At those same ballast levels, the 4 KiB ratios are 1.298, 1.321 and 1.348, favoring Caffeine. These are original audit point ratios, not the fresh paired-fork ratios below. The sparse observer does not reproduce a clean universal ordering, and all 288 MiB comparisons have quality limitations.

| Original condition | Qualified conditional result | Limit |
| --- | --- | --- |
| 256 B, every-operation service, 0/96/208 MiB | p99.9 favors Chronicle: ratios 0.479/0.495/0.539 | Baseline advantage, not pressure-emergent crossover |
| 4 KiB, every-operation service, 0/96/208 MiB | p99.9 favors Caffeine: ratios 1.298/1.321/1.348 | No qualified Chronicle win at those points |
| 256 B, sparse service, 96 MiB | p99 favors Caffeine; p99.9 unresolved | Recorder-specific result |
| 4 KiB, sparse service, 0 MiB | p99/p99.9 favor Caffeine: 1.125/1.354 | Other sparse cells carry quality/missing-data limitations |

The original study used coarse uncertainty from two outer passes; its nominal interval classifications are retained in the original audit. We neither infer an ordering from an unresolved point estimate nor transport those intervals to the later experiments. The same-pressure 256 B versus 4 KiB conditional comparisons support a limited payload-related difference within that measurement regime. They do not resolve a pressure threshold or the disagreement between observers.

### 4.2 The response bracket repeats, but its midpoint remains mixed

Figure 1 shows the fresh scheduled-response p99.9 result. At zero ballast, the three Chronicle/Caffeine ratios are 11.474, 8.494 and 13.647; at 208 MiB they are 0.215, 0.363 and 0.259. All six endpoint pairs are clean. At 104 MiB the ratios are 0.427, 0.447 and 8.500, with only one clean primary pair. The two clean additional-seed observations at 104 MiB disagree, so compiler warnings alone do not explain away the mixed transition. We retain the 0–208 MiB bracket and do not infer monotonicity or an exact threshold.

| Common ballast | Caffeine response p99.9 (µs) | Chronicle response p99.9 (µs) | Paired Ch/C ratios (blocks 1–3) | Clean primary pairs |
| --- | --- | --- | --- | --- |
| 0 MiB | 23.823–33.183 | 281.855–325.119 | 11.474, 8.494, 13.647 | 3/3 |
| 104 MiB | 33.311–426.239 | 153.343–283.135 | 0.427, 0.447, 8.500 | 1/3 |
| 208 MiB | 921.087–1,188.863 | 239.231–334.335 | 0.215, 0.363, 0.259 | 3/3 |

Ranges span individual forks and are not confidence intervals. “Bracket” describes opposite observed endpoint directions; it is not a population-threshold confidence bound. Both added seeds repeat those endpoint directions, with one pair per point, and disagree at 104 MiB.

### 4.3 A response ranking is not a service ranking

Figure 2 contrasts separate historical service and scheduled-response experiments at 352 MiB using the same earlier runtime. Historical saturated 4 KiB service favors Caffeine at p99/p99.9/p99.99 at all five tested points (328–368 MiB across two separately identified runtime groups). At p99.999, Chronicle is lower throughout that range, already at the lowest point. Neither statement supplies a newly bracketed service threshold. Rare pauses and delay outside the service boundary can consume wall time while leaving an operation-weighted p99.9 comparatively small. Response backlog and throughput expose costs that this percentile alone cannot summarize. The result does not establish whether the dominant source of each individual stall was GC, compilation, recording or scheduling.

### 4.4 The full tail explains why a single percentile is inadequate

Figures 3, 5 and 6 report per-fork survival, threshold probabilities and endpoint sensitivity. At 104 MiB the primary Caffeine >100 µs response probabilities are approximately 0.1124%, 0.11367% and 0.09273%, straddling the 0.1% tail boundary defining p99.9. Small frequency changes can therefore move that percentile sharply. At response p99.99 and p99.999, every fresh pair favors Chronicle even at baseline. This is an already-present extreme-tail advantage, not evidence that the corresponding crossover was induced by pressure.

### 4.5 Heap relief has allocation and residency costs

Figure 4 reports about 4,121.6 worker B/op in the ordinary 4 KiB Chronicle workload versus 205.6 for Caffeine, including the 5% fresh-write path and excluding common churn. At 208 MiB, primary post-GC heap occupancy is approximately 43.8% for Chronicle and 71.5–72.1% for Caffeine. Nevertheless, sampled measured-window RSS is approximately 795.5–811.7 MiB for Chronicle and 599.8–605.0 MiB for Caffeine. The result is relief of GC-managed retention, not demonstrated total-memory efficiency. Heap commitment/page residency, native map sizing and other process structures are not isolated by these measurements. Allocation/GC observations are consistent with a materialization tradeoff but do not prove the unique cause of each tail event.

### 4.6 What RQ2 can and cannot answer

The historical earlier-runtime 256 B service experiment gives opposite percentile-dependent direction changes between 448 and 480 MiB: p99.9 changes toward Caffeine, p99.999 toward Chronicle, while p99.99 favors Caffeine at both points. These are within-256 B observations. The focused 256 B and 4 KiB sweeps use different ballast ranges; their contrast alone does not isolate a payload effect or estimate movement of a common threshold. The original same-pressure conditional comparison provides the narrower payload-related observation in Section 4.1. A matched 256 B scheduled-response design is absent, so the response-threshold-shift part of RQ2 remains unanswered. Figure 7 compares Caffeine with Chronicle reuse in different pressure settings; it is not a payload-only comparison.

## 5. Threats to validity

**Internal validity.** Timer/recording activity, busy-spin pacing, background churn, compiler/GC activity and asynchronous cache maintenance can affect outcomes. Whole-library differences prevent attributing a ranking solely to heap placement. The finite trace repeatedly updates a small fixed subset; its locality and phase repetition can interact with collection and scheduling. Source-matched controls and end-of-run correctness checks constrain specific errors but do not establish recorder neutrality or production realism. Short controls lack native CPU coverage. Some JIT warnings remain. The original protocol's failed gates and stopping-policy amendment must be disclosed.

**Construct validity.** Service, scheduled response and inter-completion gaps are different constructs. Intended-arrival response is computed within the worker, not observed by an independent client. Equal heap and application ballast do not equal total memory; post-GC heap and 1 Hz RSS are imperfect summaries. Ordinary get and reuse offer different value ownership.

**Conclusion validity.** Short windows, few forks, periodic traces, adaptive historical point selection, post hoc extreme endpoints and correlated stall responses limit inference. An observed bracket is not a fitted threshold or confidence interval. Clean-subset views cannot erase contrary warning-bearing pairs, and no monotonic relation is assumed. Threshold bin bounds address representation error only.

**External validity.** Results concern one host, one collector and heap limit, a uniform read-heavy workload, fixed residents and one cache worker. Other load rates, payloads, concurrency, skew, eviction, persistence, collectors, hardware and memory budgets can change the ranking. Broad cache-selection rules or hard latency guarantees are not supported.

## 6. Reproducibility and disclosure

The working package provides per-fork derived inputs, losslessly compressed fresh primary response histograms, input/output checksums, CSV exports and offline figure generation. Raw logs/source archives and earlier delivery bundles remain retained on the collection host and require a selected, licensed off-host release before artifact publication. The protected explorer is supplementary and is not the sole accessible artifact. Portable checks require complete curve/schedule coverage, recompute quantiles and histogram threshold bounds, and reject inconsistent counts/probabilities. A source audit matches all 162 exported observations and all 18 primary distributions to their frozen inputs.

A second host-only pass on 16 November decoded all 621 available focused/follow-up workload and control histograms, reconciled 486 published full curves, checked 4,632 raw-file hashes, 207 GC summaries and all 30 fresh sampled-RSS summaries, and verified 68 retained runtime files. A rerun of the original independent auditor reproduced its 3,088-window, 1,544-endpoint, 30-bootstrap-comparison and 19,782-archive-member checks without changing its conditional acceptance. The original auditor's 5,952 prior HDR-decode receipts were checked as retained metadata, not freshly re-decoded in that rerun. The [dated re-review](RE_REVIEW_20261116.md) states exact coverage and remaining limits; neither data reconciliation nor successful figure regeneration validates the experimental design.

Human authors must agree contribution roles and review the complete manuscript. Agent-assisted implementation and research-method review are not independent human peer review. Final tool-use disclosure should accurately describe the assistance used and follow the selected venue's requirements. Nothing has been submitted or deposited as an author-approved preprint.

## 7. Discussion

### 7.1 Research-question answers

| Question | Answer supported by this study | Boundary |
| --- | --- | --- |
| Original RQ1: pressure-emergent ordinary-service p99/p99.9 win | No qualified 4 KiB forward crossover was established in the tested conditions. Some 256 B regimes already favor Chronicle at baseline; others disagree or reverse toward Caffeine. | Does not establish absence of crossover outside the measured conditions; the original unconditional protocol failed. |
| RQ2: effect of changing payload | The original same-pressure conditional results differ between 256 B and 4 KiB; focused service observations are also percentile-specific. | A change in a shared crossover threshold, particularly scheduled response, was not estimated by a matched design. |
| Scheduled-response follow-up | Fresh p99.9 endpoint directions repeat at 0 and 208 MiB; 104 MiB is mixed. | Descriptive workload-specific reversal, not an exact threshold or universal selection rule. |
| Extreme-tail and resource sensitivities | Extreme response advantages already exist at baseline; lower heap occupancy coexists with higher sampled RSS. | No claim of distribution-wide superiority, zero tail risk or total-memory savings. |

### 7.2 Implications for a cache decision

A decision based on p99.9 operation duration need not match a decision based on delayed responses or a rarer percentile. A practical comparison should state its intended arrival behavior and latency budget, then examine exceedance probabilities as well as quantiles. In this study, the same endpoint can change sharply when the proportion of moderately slow responses crosses its defining tail probability. An unresolved midpoint is therefore a useful limit on a sharp-threshold explanation, not justification for discarding a fork or continuing bisection until a desired answer appears.

Ordinary materialization and borrowed-buffer reuse also answer different application questions. A caller that retains a returned value may not be able to adopt a reusable buffer without copying or changing ownership. Likewise, a deployment constrained by total resident memory cannot infer a benefit from Java-heap occupancy alone. Our data motivate these checks; they do not supply an automatic predictor for unseen workloads.

### 7.3 Mechanism and follow-up priorities

The observed access allocation, GC overlap and occupancy are consistent with known retention/materialization tradeoffs. The response result also depends on in-process scheduling and recording. Identifying the cause of each stall would require suitably aligned event-level evidence or a separate controlled intervention. A different offered load, an equal-total-memory design or an independent recorder sensitivity would test specific threats more directly than an unbounded sweep of additional pressure points. These are extensions, not results of this dataset.

## 8. Conclusion

TailCache shows that the answer to an on-/off-heap comparison depends on the measured objective and resource accounting. A separately planned 4 KiB follow-up repeats a scheduled-response p99.9 reversal between zero and 208 MiB of additional retained application data, while leaving 104 MiB unresolved. Extreme response advantages already exist at baseline, and historical saturated-service rankings depend on percentile and regime. Chronicle reduces retained GC-managed heap while incurring materialization allocation and higher sampled process residency in the fresh cohort. The defensible result is a scoped empirical tradeoff, not an exact universal crossover or unconditional off-heap advantage.

## Author-review checklist

- Refine the contribution and related-work coverage with a systems/performance reviewer.
- Review the included original-campaign outcome table and decide how much operational history belongs in the appendix.
- Finalize figure numbering/layout and select the generated historical 256 B/4 KiB paired tables in [RESULT_TABLES.md](RESULT_TABLES.md); retain runtime and contract identity.
- Review evidence for any proposed causal wording; otherwise keep descriptive language.
- Complete clean harness reproduction, raw-evidence backup/release selection, licences and artifact accessibility checks.
- Confirm names, affiliations, contributor roles, acknowledgements, disclosure and publication venue before preparing an author-approved release.
