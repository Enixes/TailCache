# Second-host experiment conclusions

All three suites completed on the Ryzen 7 5800X host using Temurin 21.0.13+9
and commit `ae686f26823c7f7278a46e53c74090002ad5690c`. Each suite ran through
its own Gradle invocation with a separate output directory. The batch took
4 hours 41 minutes 25 seconds. All 100 research JVMs completed and all 50
pairs were usable. Twenty-seven pairs had no recorded quality warning.

## Write ratio

At 4 KiB, zero ballast and 50,000 intended arrivals/s, Caffeine led in both
seeds at 0% and 0.5% writes, while Chronicle led in both at 2% and 5%.
The 1% cell was mixed. The bracket with agreement across both seeds is
therefore 0.5–2% on this host, with a warning in one 0.5% pair. Both pairs
at 2% had no recorded warning. The first host's independent confirmation
was mixed at 0.5%. Treat the bracket here as specific to the tested host,
runtime, seeds and workload. Caffeine led in service p99.9 in all ten
write-ratio pairs, even when the scheduled-response winner changed.

## Longer locality confirmation

With four fresh seeds and 90-second windows, all four pairs at 2,048 update
keys favored Caffeine at scheduled-response p99.9, and all four at
32,768 favored Chronicle. Three pairs per arm had no recorded warning.
The response advantage of Chronicle at p99.99 and p99.999 held in three
of four seeds in each arm. The contrary pairs had no recorded run
warnings, so removing warning-bearing pairs does not restore unanimity.

The two contrary Chronicle forks had maximum recorded completion gaps of
18.783 ms (distributed, seed 61811) and 19.730 ms (concentrated, seed 61812).
Neither gap overlapped a logged GC pause or JVM safepoint. Retain both as
observed stalls of unresolved origin. This diagnostic does not establish
what caused either stall.

## Pressure and payload

At saturated service p99 and p99.9, Chronicle led all eight 256 B pairs
and Caffeine led all eight 4 KiB pairs. Each winner was already ahead at
zero ballast. The ranking persisted at 96, 208 and 288 MiB, so this matrix
showed payload-dependent ranking without a pressure-induced crossover.
Only one of the sixteen saturated pairs had no recorded warning. The
directions are warning-inclusive.

At fixed 50,000 arrivals/s, Chronicle led scheduled-response p99.9 in all
sixteen pairs, including zero ballast. Fourteen of the sixteen pairs had
no recorded warning. These results answer a different timing question
from the saturated-service results.

The [campaign review](CAMPAIGN_REVIEW.md) gives every cell's ratios and links
to the per-fork measurements. It was generated after checking the original
report hashes, slot seals, raw evidence inventories, histogram and stream
verification receipts, and derived statistics. The earlier host's results
and the prior 30-second locality experiment remain separate cohorts.
