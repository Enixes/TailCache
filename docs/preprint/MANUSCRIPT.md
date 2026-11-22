# TailCache: Update Locality Reverses Tail-Latency Rankings in Java Caches

**Working draft for author review | 22 November 2026**

## Abstract

An off-heap cache can relieve Java heap pressure while incurring higher access and materialization costs. We compare Caffeine and ordinary in-memory Chronicle Map under G1, separating cache-call latency from response latency measured against scheduled arrivals. With 32,768 resident entries, 4 KiB values, 5% writes, 50,000 intended arrivals/s, and zero added application ballast, changing only the eligible write set reverses the response p99.9 ranking. Caffeine leads when writes target 2,048 keys, while Chronicle leads when writes target all 32,768. The direction repeats on two hosts, including four fresh seeds at 90 seconds. With distributed writes, the second-host 30-second cohorts record response p99.9 of 3.09-3.65 ms for Caffeine and 7.48-7.90 µs for Chronicle. In a separate 48-pair saturated-service matrix, Chronicle leads at 256 B and Caffeine leads at 4 KiB across both tested pressure levels and all three write fractions. On the second host, mixed collections account for most of the added Caffeine pause time when writes are spread out. The experiment changes update locality, value lifetime, and cache policy activity together. We distinguish call and response tails and report the update set alongside the write fraction.

## 1. Introduction

Cache choice depends on how often values are read, where they are stored, and how often retained values are replaced. For the byte arrays used here, Caffeine holds the values on the Java heap and a hit returns the stored array. In-memory Chronicle Map holds the stored values off-heap and its ordinary get materializes a fresh Java array on a hit. This trades on-heap retention of cache values for allocation and copying on reads. A workload can pay for those costs during the call itself, in garbage collection, or in the time a request waits before its call starts.

Our original questions are whether increasing application heap pressure produces a p99 or p99.9 service-latency crossover (**RQ1**) and how payload size changes the ordering (**RQ2**). A later question asks whether the update working set changes the scheduled-response ranking at matched arrivals and offered write demand (**RQ3**). We retain the original pressure outcome, report the two-host locality result and its limits, and make the second-host raw measurements available for offline reconstruction.

## 2. Related work

Prioritized garbage collection provides explicit runtime support for the competing retention and collection costs of software caches [1]. A practitioner comparison of Caffeine and OHC already demonstrates that cache size and collection costs can change the preferred storage placement [2]. TeraHeap tackles related materialization and memory-pressure costs through a new heap design [3]. Our contribution is a specific empirical comparison of existing cache configurations at matched fresh-write demand, with a controlled update-set intervention and independent hardware replication.

Open and closed workload models can yield materially different latency results [4]. We apply that distinction to the measurement boundary of a cache call and a scheduled request. Java warmup and steady state are also known sources of experimental error [5]. We report compilation warnings, earlier qualification failures, and warning-free sensitivity alongside the measurements. Prior collector studies motivate examining application latency alongside pause summaries [6].

## 3. Methods

### 3.1 Cache semantics and timing

We use Java 21, Caffeine 3.2.4, Chronicle Map 2026.1, and HdrHistogram 2.2.2. Chronicle uses its ordinary get API [7]. Both configurations start with 32,768 resident entries and allocate a fresh immutable byte array per measured overwrite. Reads hit resident entries. Cache placement, layout, and maintenance differ across the two libraries. The experiments use one cache worker and allow JVM and library helper threads.

Service latency measures completion minus call start. In the saturated experiment, the worker issues the next call immediately. Scheduled response measures completion minus the request's intended arrival. It retains overdue work in order. At 50,000 arrivals/s, the intended interval is 20 µs. A pause can delay multiple scheduled requests, including requests whose actual calls start after the pause. The schedule is generated in process. A network client, concurrent callers, and miss handling are outside this measurement. The p99.9 is the observed latency at roughly the boundary of the slowest one in 1,000 operations.

### 3.2 Locality intervention and replication

A deterministic indexed stream generates operation flags and keys. Both backends see the same stream for each seed. In both treatments, reads sample uniformly across all resident keys. For writes, the key index is mapped into either a fixed prefix of 2,048 eligible keys or the full set of 32,768. We use 4 KiB values, 5% nominal writes, G1, a fixed 512 MiB heap, and zero added application ballast. The offered background allocation is 32 MiB/s. The write rate is about 2,500 overwrites/s, giving nominal mean per-key replacement intervals of 0.82 s and 13.1 s. These intervals describe the update stream. Individual object survival and promotion are separate quantities.

The first Linux host supplies two seeds with reversed backend-order repeats. The second Linux host is a Ryzen 7 5800X with a 12-CPU JVM budget and Temurin 21.0.13+9. Its 30-second replication uses two fresh seeds, and a separate 90-second cohort uses four additional seeds. Both hosts use 120 seconds of warmup and four seconds of conditioning with zero priming for the locality result. Host, JVM build, seed, and window length differences limit comparisons of effect magnitude. We keep each cohort and pair separate.

### 3.3 Pressure, write-rate, and quality checks

The second-host saturated matrix varies payload (256 B or 4 KiB), added strongly retained application data (0 or 288 MiB), and nominal writes (1%, 5%, or 10%), with four pairs per cell. Application ballast is retained data independent of cache contents. Zero ballast still includes the resident cache and temporary allocations. We fix the offered rate of background allocation (churn) and report when it cannot be sustained. Saturated backends can complete different numbers of operations. The separate paced sweep varies writes from 0.5% to 2% with 4 KiB values, all 32,768 keys eligible, zero added ballast, and four seed pairs per cell.

Each comparison pairs two JVM runs within a seed and workload. We report individual fork quantiles and descriptive ranges. We preserve warnings, including compilation, external CPU activity, and dropped churn. The second-host native observer handoff tightened process attribution before the 48-pair saturated matrix. One eligible external-noise pair was rerun and is included only in a separate warning-free sensitivity view. The original observations remain intact.

## 4. Results

### 4.1 Write locality reverses scheduled-response p99.9 on two hosts

Each cohort favors Caffeine with 2,048 eligible write keys and Chronicle with 32,768. Figure 1 plots all 20 paired comparisons. The first-host repeated seeds document repeatability under reversed order. The fresh second-host seeds test whether the direction survives a hardware and runtime change.

![Figure 1. Scheduled-response p99.9 by eligible write set and cohort.](figures/fig08_cross_host_locality.svg)

**Figure 1.** Each dot is one paired seed and run block. Ratios below 1 favor Chronicle. Filled dots indicate pairs with zero recorded warnings. Open dots retain measured pairs with warnings.

| Host and window | Write keys | Caffeine p99.9 | Chronicle p99.9 | Warning-free pairs |
| --- | ---: | ---: | ---: | ---: |
| First, 30 s | 2,048 | 24.75-28.06 µs | 74.82-244.10 µs | 0/4 |
| First, 30 s | 32,768 | 8.90-9.70 ms | 125.38-226.56 µs | 1/4 |
| Second, 30 s | 2,048 | 6.42-6.53 µs | 7.61-9.26 µs | 1/2 |
| Second, 30 s | 32,768 | 3.09-3.65 ms | 7.48-7.90 µs | 2/2 |
| Second, 90 s | 2,048 | 6.44-8.13 µs | 7.24-9.66 µs | 3/4 |
| Second, 90 s | 32,768 | 2.90-3.20 ms | 7.50-9.43 µs | 3/4 |

With all keys eligible on the second host, Caffeine's service p99.9 is 6.36-7.42 µs in the 30-second paced runs, while its response p99.9 exceeds 3 ms. Chronicle's response p99.9 stays near 8 µs. The divergence between service and response is consistent with requests spending more time waiting to begin their calls.

Caffeine's measured GC pause overlap increases from 8.21-9.91 ms with concentrated writes to 59.57-65.13 ms with distributed writes. Chronicle remains at 12.79-13.15 ms. Within each backend and seed, measured allocation per operation is unchanged by the treatment.

Figure 2 groups archived GC pauses by recorded type and shows that Caffeine's time in G1 mixed collections rises from 3.90-4.03 ms to 36.14-39.68 ms in the 30-second runs and from 8.27-10.47 ms to 108.53-117.04 ms in the 90-second runs. Both backends record zero full collections in these locality windows.

![Figure 2. G1 mixed-collection pause time by eligible write set.](figures/fig09_mixed_collection_time.svg)

**Figure 2.** Each point is one fork. Both panels use the same scale. Open marks belong to pairs with recorded warnings. Chronicle's mixed-collection time is zero in these runs.

A Caffeine value stays live while the cache holds it. If it survives young collections, it can move to the old generation. A later overwrite can make the former value unreachable, allowing reclamation. G1 mixed collections reclaim young and selected old regions [8]. Distributed writes lengthen the time until replacement and could give more values time to age, while ongoing overwrites can turn some of those older values into garbage. The increase in mixed-collection time is consistent with that explanation. Per-value promotion and the contribution of cache policy activity remain unmeasured.

The extreme tail has exceptions. Chronicle leads at scheduled response p99.99 and p99.999 in three of four 90-second pairs in each update-set arm. The two contrary Chronicle forks have completion gaps of 18.783 ms and 19.730 ms without overlapping logged GC pauses or JVM safepoints. At 30 seconds, roughly 15 operations lie beyond the nominal p99.999 rank per fork, and several affected operations can come from a single stall.

### 4.2 Payload changes the saturated-service ranking

At p99 and p99.9, Chronicle leads every 256 B pair (24/24) and Caffeine leads every 4 KiB pair (24/24), at both tested pressure endpoints and at all three write fractions. Of 48 first-pass pairs, 36 have zero recorded warnings. The external-noise rerun yields 37 pairs in the warning-free sensitivity view and preserves the direction at that cell. At 4 KiB and 288 MiB, all pairs at 5% and 10% writes have dropped churn demand. The direction there rests on warning-inclusive evidence. A robust pressure-induced p99 or p99.9 crossover remains unestablished.

![Figure 3. Saturated service p99.9 ratios at 5% writes.](figures/fig10_saturated_payload.svg)

**Figure 3.** First-pass pairs at 5% writes. Each point is a Chronicle-to-Caffeine p99.9 ratio. The dashed line marks equal latency. Open marks indicate a recorded warning in either run of the pair.

Read timings help explain the payload effect. At 256 B, 5% writes, and zero ballast, the median of the four fork-level read p50s is about 0.10 µs for each backend. For read p99.9, Chronicle is at 0.65 µs and Caffeine at 1.80 µs. The advantage is visible in the slower reads. At this size, Chronicle retains a lower read tail despite the cost of copying the value. Earlier policy and JMH comparisons show that small-value rankings depend on the cache settings and measurement harness. The cause of Caffeine's slower reads at this point remains unresolved.

At 4 KiB and the same write rate and ballast, the median read p50 across forks is 0.13 µs for Caffeine and 0.59 µs for Chronicle. Chronicle's worker allocates about 4,122 bytes per operation, compared with 206 for Caffeine, across reads and writes. The higher allocation and read latency are consistent with Chronicle allocating and copying larger values on ordinary hits. The experiment measures the complete call, so it does not partition the latency difference among copying, allocation, lookup, and policy work.

### 4.3 A write-rate bracket and the limits of pause-based prediction

In the separate second-host paced sweep, every pair at 1.25% writes favors Caffeine and every pair at 1.5% favors Chronicle. All eight pairs across those two settings are warning-free. The 0.75% and 1% cells are mixed. This is an observed bracket between two tested points. Earlier first-host write-rate forecasts failed, with disagreement near the low-write boundary. A single production threshold cannot be inferred.

The distinct timing boundaries explain how a GC-heavy run can still have a small service p99.9. In a first-host discovery fork, large pauses overlapped 312 of 28.5 million timed calls despite substantial wall-time GC exposure. At fixed arrivals, one pause can delay a series of requests and their backlog. Models using measured pauses help reconstruct response tails, but earlier held-out evaluations show near-boundary errors and no winner-prediction advantage over comparing total GC pause time. These reconstructions use information measured during the run.

### 4.4 How the newer measurements change the earlier pressure result

In the earlier short-trace runs, 4 KiB response p99.9 favored Caffeine at 0 MiB and Chronicle at 208 MiB. The 104 MiB pairs were mixed. In the second-host 5%-write, full-key continuous-stream matrix, Chronicle leads at 0, 96, 208, and 288 MiB in both seeds. The earlier trace repeated about every 0.8 s and wrote to roughly 1,940 keys per seed. The later stream spread updates across all 32,768 keys, and its response advantage for Chronicle was already present at zero ballast. The earlier 0-to-208 MiB bracket therefore applies to its own workload. The controlled locality test in Section 4.1 independently changes the eligible write set at zero ballast.

![Figure 4. Scheduled-response p99.9 in the two application-pressure studies.](figures/fig11_response_pressure.svg)

**Figure 4.** Both panels use the same latency scale. The earlier panel shows the primary short-replay runs. The newer panel shows the second-host full-key runs. Open marks indicate pairs with recorded warnings. The simultaneous changes in workload and host limit direct causal comparison between panels.

The earlier p99.99 and p99.999 Chronicle advantages already appear at zero ballast. The second-host full-key pressure matrix agrees at baseline. The contrary 90-second locality pairs in Section 4.1 limit how broadly that extreme-tail result applies.

## 5. Limitations and implications

The strongest result concerns one worker, two libraries, G1, a bounded synthetic workload, and fixed intended arrival intervals. The eligible-key intervention changes overwrite interval, write locality, and policy activity together. The two-host replication supports the response direction under the tested setup. It does not isolate one JVM mechanism or estimate a production SLA. High-percentile observations remain correlated within stalls and are descriptive across a small number of seed pairs.

The original unconditional Task 12 qualification remains NO_GO. Earlier conditional results, JMH versus every-operation differences, and resolved or unresolved follow-up points are preserved in the supplements. Small-value service rankings depend on measurement and cache configuration. The main experiments compare hit and overwrite traffic with ordinary in-memory access. Miss performance, persisted-map timing, read skew, and shared-cache contention remain separate questions. Earlier buffer reuse runs use a different caller ownership contract. In the midpoint follow-up, Chronicle had lower retained Java-heap occupancy and higher sampled RSS. An equal-total-memory comparison remains open.

For small values, measure the call tail under the cache policy the application needs. For larger values, compare call latency with scheduled response and check whether replacing long-lived values coincides with pauses and queueing. Report intended arrival rate, write fraction, and the set of keys eligible for writes. The same write fraction can yield different response rankings. A focused future experiment would test whether the locality reversal survives at 10% writes. The current result is supported by the two-host evidence at 5%.

## 6. Reproducibility and disclosure

The second-host archive contains raw HDR histograms and bins, GC and age logs, measurement windows, and frozen schedules. The offline verifier reproduces the reported percentile tables, point conclusions, and retry comparisons from 252 research runs, two retry runs, 36 diagnostic runs, and 60 timing controls. The [versioned archive and instructions](https://github.com/Enixes/TailCache/tree/4c3ab6794643febf676d91446f80b9724517ff74/docs/second-host-20261120/archive) identify the source commits and evidence checksums. The [current verifier](https://github.com/Enixes/TailCache/blob/codex/tailcache-portability/scripts/tailcache_verify_archive.py) supports offline reconstruction on Linux and macOS. The [first-host mechanism dataset](https://github.com/Enixes/TailCache/tree/5772fb212692244a29b6ab61d416340db600f0c8/docs/mechanism) provides the earlier pairs and reviews. The [paper evidence map](CLAIMS.md) identifies the inputs behind the figures. The [interactive companion](https://github.com/Enixes/TailCache/blob/codex/tailcache-preprint/output/html/tailcache-preprint-reader.html) exposes the paired measurements and provides filters for latency, payload, and workload. Source collection inventories and launcher logs remain on the respective hosts.

The authors will confirm contributions, artifact access and licensing, and the description of AI-assisted implementation, analysis, and editing before deposit. The current manuscript is for review.

## 7. Conclusion

At matched write demand and zero added application ballast, concentrating versus distributing updates flipped which cache had lower scheduled-response p99.9 on both hosts. At 256 B, Chronicle led the saturated-service comparison. At 4 KiB, Caffeine led that comparison even though it lost scheduled-response p99.9 under distributed writes. The results show why cache comparisons need to report both the timing boundary and which keys receive writes.

## References

[1] D. Nunez, S. Z. Guyer, and E. D. Berger. Prioritized Garbage Collection: Explicit GC Support for Software Caches. OOPSLA, 2016. [DOI](https://doi.org/10.1145/2983990.2984028).

[2] M. Knasiecki. GC, hands off my data! Allegro engineering blog, 2022. [Article](https://blog.allegro.tech/2022/06/gc-hands-off-my-data.html).

[3] I. G. Kolokasis et al. TeraHeap: Reducing Memory Pressure in Managed Big Data Frameworks. ASPLOS, 2023. [DOI](https://doi.org/10.1145/3582016.3582045).

[4] B. Schroeder, A. Wierman, and M. Harchol-Balter. Open Versus Closed: A Cautionary Tale. NSDI, 2006. [USENIX](https://www.usenix.org/conference/nsdi-06/open-versus-closed-cautionary-tale).

[5] L. Traini, V. Cortellessa, D. Di Pompeo, and M. Tucci. Towards effective assessment of steady state performance in Java software: are we there yet? Empirical Software Engineering, 2023. [DOI](https://doi.org/10.1007/s10664-022-10247-x).

[6] Z. Cai, S. M. Blackburn, M. D. Bond, and M. Maas. Distilling the Real Cost of Production Garbage Collectors. ISPASS, 2022. [DOI](https://doi.org/10.1109/ISPASS55109.2022.00005).

[7] OpenHFT. ChronicleMap interface, 2026.1. [Versioned API source](https://github.com/OpenHFT/Chronicle-Map/blob/chronicle-map-2026.1/src/main/java/net/openhft/chronicle/map/ChronicleMap.java).

[8] Oracle. Garbage-First (G1) Garbage Collector. Java 21 Garbage Collection Tuning Guide. [Garbage collection cycle](https://docs.oracle.com/en/java/javase/21/gctuning/garbage-first-g1-garbage-collector1.html).
