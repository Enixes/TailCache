# First complete exploratory matrix: researcher outcome review

All42 fresh JVMs completed under the prospectively frozen exploratory protocol, with zero replacements and no missing/hard-rejected fork. Collection/export ran7 November2026,09:55:59–10:37:34UTC (15:25:59–16:07:34IST), about41m35s after protocol freeze. Source was unchanged throughout, commit06ea68dd19ebaffb827d5ba9fa80a15982640131, measurement fingerprint5015fa79565c07b3a32eb5e247b40386dfc953491b87c7e8d96ca630c23d37e6. Protocol SHA2566d99d39158ec2d54b5f19818382182b6418b9b377cd57881b37dafaa8350b30d. The twelve-slot common-observer diagnostic remains deferred/uncollected; it was not adopted.

## Acceptance and provenance

Streaming-v5 preparation passed the user-approved4GiB available-RAM rule with6569276KiB available,2815428KiB free and swap0. Fresh120s quiet and360s first-block age replayed. All32 workload cells and ten floors used30 warmups/8 conditioning/8 analysed intervals with the declared common inputs, fixed sparse sampler and unprofiled channels. No historical fork filled a slot and no per-fork histograms were pooled.

Forty-one forks met the original per-fork quality/host checks. The sole strict rejection retained as a prospective exploratory warning is Caffeine256B/live96MiB/every-operation: outside-CPU upper bound22.0414%, above the original10% but below the declared exploratory25% ceiling. Its p99/p99.9=972/2767ns remain visible; it was not replaced or discarded. All other forks' outside-CPU bounds were below10%. This warning prohibits treating that cell as clean primary evidence.

No compiler warning was needed: maximum analysed interval and maximum per-fork total were both5ms, within original10/80ms limits. Minimum sampled count354358 exceeded100000. This establishes only this run's observed counters, not general qualification of30 warmups. All full-block memory/paging/power/thermal/accounting/identity/churn/allocation and recorder controls passed. Minimum host available RAM was5076264KiB, swap remained0. Every one of576 physical compressed HDR distributions matched its CSV/configuration/count through the actual decoder; exporter/count conservation retained zero overflow. All eight low-pressure median floor ratios passed unchanged ceilings (maximum supply ratio0.18182 vs0.5; maximum timer ratio0.12174 vs1/3). No floor was subtracted.

Fresh complete raw replay preceded export. A separate small implementation independently recomputed168 per-fork percentiles across42 forks directly from retained JSON/CSV distributions, matching all reported values/counts. Another independently matched32 workload post-GC used-heap medians and2291 measured collection-end samples from raw heap-end log lines and actual measurement windows. This checks used-heap ends, not an exact live-object census or independent validation of every pause-exposure field.

The outside-build dataset is evidence-archives/native-final-exploratory-e2e-dataset-20261107-001. Its raw/source/control/preparation archive is17713692bytes,1948 verified members, SHA256951d4ad5d4e5f4677ead19c28b2bc5bec9592c69bffd001a48408873b014fa9e. Every member was read back and checked. Independent percentile/occupancy proofs and this review are supplemental unique files beside that archive; the original collection dataset/archive were not overwritten. Earlier001–003 preparation rejections and prior archives remain preserved.

## Descriptive results

Each entry below is one independent fork under its indicated observation mode; values are p99.9 in microseconds. Columns are not interchangeable replicas and have not been pooled.

| Payload | Common live MiB | Sampled Caffeine | Sampled Chronicle | Every-op Caffeine | Every-op Chronicle |
| --- | ---: | ---: | ---: | ---: | ---: |
|256B|0|1.656|1.182|2.237|1.200|
|256B|96|1.080|1.106|2.767*|1.104|
|256B|208|1.282|1.200|2.385|1.231|
|256B|288|1.600|1.256|2.367|1.204|
|4096B|0|8.128|11.024|8.155|10.719|
|4096B|96|8.160|10.720|8.191|10.863|
|4096B|208|8.288|10.736|8.175|10.927|
|4096B|288|8.400|11.168|8.383|11.047|

*The marked fork carries the declared outside-CPU warning.

At4096B, Caffeine has lower observed p99 and p99.9 at all four pressure points in both observation modes. At the highest common application demand its median post-GC used heap was89.84% sampled/90.82% every-operation, versus Chronicle61.91%/62.79%. This demonstrates the expected heap separation in the tested dataset, while the observed materialization/access cost still outweighs that advantage at these tail endpoints. It does not establish absence of a crossover beyond these inputs or under replication.

At256B, Chronicle's observed p99.9 is often lower even at zero pressure, so these observations do not establish a pressure-induced crossover. Caffeine's p99 is lower in every sampled condition, while the full recorder favors Chronicle at live0/96/288MiB. There are therefore three descriptive p99 channel-direction disagreements and one p99.9 disagreement at live96MiB. The latter involves the CPU-warning fork, but the p99 disagreements at live0/288 have no host warning. Observer dependence remains unresolved; the lenient policy enables complete collection, not a scientific resolution of that bias.

## Limits and decision

Accept this as the first complete, source-matched **exploratory end-to-end dataset** under the frozen warning policy. All42 invocations, actual raw audits, complete verified export and this researcher-style review are finished. This review is not an independent peer review.

Do not accept it as Task12's qualified primary campaign. One workload fork per cell, shortened warmups, one order sequence, uncalibrated current-source occupancy and absent robustness seeds cannot quantify run-to-run uncertainty, provide hierarchical confidence intervals or support a confirmatory crossover/no-crossover claim. The ratio/direction and pressure trends are descriptive. Floor replicas do not supply missing workload replicas; agreement of two different recording regimes does not replace replication.

The reasonable relaxations achieved the user's immediate goal without silently changing primary acceptance: one CPU-noisy fork was retained with its exact warning, while all hard integrity/safety/fairness checks held. Initial available-memory provenance, reduced replication/duration and scientific limitations are explicit. Primary taskComplete/campaignReady/reportable/currentHarnessQualified remain false and the recovery timer remains enabled. The next research work is a bounded reviewed observer-regime decision plus independent workload replication; another full exploratory rerun is not automatically justified.
