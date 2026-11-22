# Literature verification and novelty boundary

## 23 November citation update

The [current Related work section](MANUSCRIPT.md#2-related-work) connects the prior literature to three distinct parts of the study:

- **Tail latency and workload design.** [Dean and Barroso](https://research.google/pubs/the-tail-at-scale/) motivate reporting tails, and [Li et al.](https://courses.cs.washington.edu/courses/cse452/23wi/papers/sharma-et-al-tales-of-the-tail.pdf) distinguish several sources of server stalls. The scheduled-response measurement follows intended arrival timestamps, with HdrHistogram recording the directly observed durations.
- **JVM measurement.** [Georges et al.](https://users.elis.ugent.be/~leeckhou/papers/oopsla07-stat.pdf) distinguish variation within and between JVM invocations. [Barrett et al.](https://doi.org/10.1145/3133876) and Traini et al. motivate reporting warmup and steady-state limitations alongside fork-level outcomes.
- **Memory management.** [TeraCache](https://www.usenix.org/conference/hotstorage20/presentation/kolokasis), [Yak](https://www.usenix.org/conference/osdi16/technical-sessions/presentation/nguyen), and [NG2C](https://www.dpss.inesc-id.pt/~rbruno/papers/rbruno-ismm17.pdf) provide context for serialization and object-lifetime costs. TailCache varies where writes land in two existing in-memory cache configurations.

## 15 November review update

Rechecked the primary Nunez preprint/DOI record, USENIX open/closed proceedings entry and Traini publisher record. The TeraHeap author page was temporarily unavailable to the fetcher; its previously verified citation is retained, with the publication DOI checked as the alternative. This is not a claim of a new exhaustive literature search.

Inspected the [pinned HdrHistogram 2.2.2 implementation](https://github.com/HdrHistogram/HdrHistogram/blob/HdrHistogram-2.2.2/src/main/java/org/HdrHistogram/AbstractHistogram.java): `getValueAtPercentile` reduces the requested floating-point percentile by one representable step, applies a ceiling rank and returns the upper-equivalent bin value for nonzero percentiles. This supports the numerical method used in the paper's fixed endpoints. The generic current README alone was insufficient to pin these semantics; the bibliography now points to the versioned implementation. No source claims recorder neutrality.

The revised manuscript separates the original same-ballast conditional payload evidence from the focused payload sweeps' different ballast ranges. Different results across those focused regimes alone cannot identify a payload effect or movement of a common response threshold. No new literature evidence upgrades that experimental limitation.

## Initial 11 November verification

Checked 11 November 2026 using Exa to fetch known primary sources, followed by one five-result targeted TeraHeap search. This is a bounded verification pass supporting the draft, not a systematic review. The broader initial search remains in [the literature strategy](../TAILCACHE_LITERATURE_AND_PUBLICATION_STRATEGY.md). Search-result slots are not papers read.

| Citation | Primary page checked / material examined | Established knowledge | TailCache distinction and limit |
| --- | --- | --- | --- |
| `nunez2016` | [Author preprint record and abstract](https://arxiv.org/abs/1610.04790), authors and related OOPSLA DOI | Cache space benefits interact with collection cost; priority references and a runtime-supported cache are an intervention. | Existing-library empirical comparison, not discovery of cache/GC tension or a new runtime. |
| `schroeder2006` | [Official proceedings entry](https://www.usenix.org/conference/nsdi-06/open-versus-closed-cautionary-tale), [primary paper abstract/introduction](https://www.usenix.org/legacy/events/nsdi06/tech/full_papers/schroeder/schroeder.pdf) | Completion-driven and independently arriving workloads can behave differently. | Cache-specific instrumented application, not discovery of open/closed effects; intended arrivals in one process, not independent network load. |
| `kolokasis2020` | [Official paper page, abstract and BibTeX](https://www.usenix.org/conference/hotstorage20/presentation/kolokasis) | TeraCache avoids serialization through a managed mmapped storage heap for Spark. | Ordinary in-memory library access and ownership tradeoff; not the same storage or analytics system. |
| `kolokasis2023` | [Publication DOI/abstract](https://doi.org/10.1145/3582016.3582045), [author record and abstract](https://foivos.zakkak.net/publication/teraheap-2023-asplos/) | TeraHeap addresses serialization and renewed heap pressure when cached objects return, using a second managed heap. | Materialization is established prior motivation; our contribution is its measured interaction with specific tail objectives and resource metrics. |
| `traini2023` | [Publisher author list, abstract and introduction](https://link.springer.com/article/10.1007/s10664-022-10247-x) | Fixed warmup and steady-state assumptions can fail in Java microbenchmarks. | Report observed warnings and qualify claims; not a new steady-state detection technique. |
| `knasiecki2022` | [Practitioner's article, experiment section and tables](https://blog.allegro.tech/2022/06/gc-hands-off-my-data.html) | Direct Caffeine/OHC comparison already asks whether GC relief compensates for access cost and shows payload-dependent tradeoffs. | Closest practical overlap. Common retention, explicit service/response, repetitions and full-tail/resource audits must carry the distinction. Not peer-reviewed. |
| `chronicle2026` | [Versioned interface source/Javadoc](https://raw.githubusercontent.com/OpenHFT/Chronicle-Map/chronicle-map-2026.1/src/main/java/net/openhft/chronicle/map/ChronicleMap.java) | Reusing a supplied value can reduce garbage depending on deserializer support. | Separate borrowed-buffer contract; no mandatory-reuse or universal allocation-free claim. |
| `hdrhistogram` | [Official README precision/representation description](https://github.com/HdrHistogram/HdrHistogram) | Configurable finite-resolution histogram counts and quantiles. | Numerical analysis is checked against pinned runtime evidence; documentation is not evidence of observer neutrality. |

TeraHeap search: five results, five unique URLs; the selected author page and DOI were read. One result was presentation slides and one an artifact record; they were not treated as the main paper. An attempted arXiv URL resolved to unrelated mathematics and was excluded, not cited. No numerical results from other studies are reused as TailCache measurements. Metadata not verified (such as page ranges) is omitted rather than guessed.

## Working contribution statement

TailCache provides a reproducible empirical case study in which application retention, materialization, arrival/service definition, percentile and process-memory metric lead to different conclusions about the same pair of cache backends. A new source-matched follow-up repeats a scheduled-response ranking change while preserving an unresolved midpoint, rather than fitting a sharp universal threshold.

This is a candidate contribution for human review. The broad off-heap crossover premise, GC-driven stalls, serialization costs and open/closed workload distinction are prior knowledge. Different libraries, a rarer percentile or a large audit trail alone do not establish novelty. Before journal submission, complete citation chaining and seek a systems/performance researcher's assessment. No professor was contacted by this work.

## 18 November targeted model/measurement check

Read the primary abstract/introductory portions of [Cai et al., ISPASS2022](https://arxiv.org/abs/2112.07880), [Zhao et al., PLDI2022](https://www.steveblackburn.org/pubs/papers/lxr-pldi-2022.pdf) and [Blackburn et al., ASPLOS2025](https://www.dacapobench.org/assets/pdf/dacapo-asplos-2025-with-appendix.pdf). The LXR first-page table explicitly separates application latency from GC pauses; DaCapo's abstract/introductory methodology discussion motivates refreshed workloads and latency measurement. These sources constrain novelty: lower pause times need not mean lower application latency, and improved JVM measurement is established work. We do not claim to reproduce these collector studies or to have systematically surveyed queueing/pause-model literature. The residual/FIFO calculation is an approximate explanatory model, not a new general law. DOI/title/author metadata were checked on those primary records. No acceptance odds or venue ranking follows from this check.
