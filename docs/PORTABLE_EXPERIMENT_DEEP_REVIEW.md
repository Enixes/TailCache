# Research and portability review

Reviewed the retained Task 12, 17 November extension, write-rate and mechanism
evidence alongside the portable Gradle runner. This review distinguishes arithmetic
reproduction, repeated runs on one host, and independent replication.

## What the evidence supports

| Claim | Assessment | Evidence and scope |
|---|---|---|
| RQ1. Increasing application ballast reverses ordinary service p99 or p99.9 in Chronicle's favor. | Unsupported in the tested regimes. | In the 4 KiB saturated-service extension, Caffeine retained the p99.9 lead through 336 MiB of ballast. At 512 B, Chronicle already led in the custom recorder at both 0 and 208 MiB, and the separate JMH comparison was mixed. A baseline lead and a pressure reversal are different outcomes. |
| RQ2. Payload shifts the crossover. | Payload changes the ranking. Movement of a stable threshold remains unresolved. | At 4 KiB, the service result remains Caffeine-favoring at the tested pressure points. Smaller payloads show baseline and observer sensitivity. In the matched paced 256 B and 4 KiB cohort, response p99.9 favored Chronicle already at zero ballast. |
| The update working set reverses scheduled-response p99.9. | Strongest bounded result. | With 4 KiB values, 5% writes and 50,000 intended arrivals/s, Chronicle/Caffeine p99.9 ratios were 2.67–9.22 for 2,048 update keys and 0.0137–0.0234 for 32,768. Both directions held in two seeds and their reversed-order repeats. Warning-free coverage was 0/4 concentrated and 1/4 distributed pairs. |
| A backend that wins p99.9 also wins the far tail. | The rankings can diverge. | In all four concentrated pairs, Caffeine led at response p99.9 and Chronicle led at p99.99 and p99.999. The latter has roughly 15 observations beyond its rank per 30-second fixed-arrival fork. |
| Total pause time predicts latency and determines the winning cache before a run. | Pause logs have retrospective explanatory value. | The later conditional models got 21/22 calibrated transport directions. A lower-total-GC comparator got 22/22 using measured pauses from both cache runs. The prospective write-rate bracket and fresh 0.5% replication prediction failed. At 5% writes, doubling the heap reduced Caffeine's measured pause exposure but increased response p99.9 in both seeds. Pause size and timing matter to the numerical tail. |

The locality arms matched realized fresh-write demand within each backend and seed.
The maximum measured allocation difference between update sets was about 0.000166
bytes per operation. Different update reuse distances, object lifetimes and Caffeine
policy activity can all contribute. Chronicle's ordinary reads still materialize
values on the Java heap. This experiment can support an update-locality claim while
leaving promotion causality and equal-total-memory performance open.

The saturated 4 KiB, 336 MiB discovery fork shows why the timing metric matters.
GC occupied 39.36% of the window but 312 large pauses coincided with roughly 0.00109%
of timed calls. In that particular pair Chronicle had lower service p99.999
(1.465 ms versus 35.783 ms), while Caffeine had lower p99.9. The ordering at
neighboring tested pressures was nonmonotonic. Treat this as a useful extreme-tail
example and keep both the per-fork denominators and the full tail curves in view.

The original Task 12 unconditional protocol remains NO_GO. The most defensible
paper is a bounded case study of workload-dependent response tails, with the
negative ordinary-service result explicit. Put the two distinct seeds and the
clean-pair counts beside the headline result. Keep the 30/90-second disagreement
descriptive because seed and collection time also change. The hardware, collector,
cache policy, arrival model, and observer establish the scope of each result.

Sources: [mechanism data and results](mechanism/RESULTS.md),
[raw-evidence re-review](mechanism/REREVIEW_20261118.md),
[service extension](service-followup/RESULTS_20261117.md), and
[prospective write-rate study](predictor/RESULTS.md).

## Portability findings fixed before review

1. **P1. The default research suite enabled four priming calls.** The mechanism
   experiment selected zero after its priming comparison. All shipped research
   profiles now select zero. The runner also checks the actual priming and cache
   contract emitted by the JVM. New seeds and a fixed JVM CPU budget make the
   locality profile a fresh test of the same treatment.
2. **P1. CPU screening silently skipped intervals with partial counters.** A
   missing system counter now raises a warning. When worker ticks are unavailable
   but system ticks are valid, the runner bounds outside CPU by all observed busy
   time for that bracket and records that attribution was unavailable. This is
   conservative and can warn even when the worker accounts for much of the load.
3. **P1. Hitting the stall-event export cap discarded otherwise count-complete
   histograms.** The Java recorder still counts every operation in the histograms
   after the cap. The runner now checks detail row counts and operation indexes,
   records a truncation warning, and keeps complete histograms after independent
   validation. A count mismatch or invalid operation index still fails. This avoids
   selecting low-stall forks just because their event detail fits.
4. **P2. Offline alternate inputs looked like a power disconnect.** The power
   check now handles hosts with a live supply and another inactive input. A
   sample reporting every known input offline still warns or blocks preflight.

The Gradle task runs Java correctness tests before collection and saves the
JUnit receipts. The Python controller provides the host observer, evidence checks,
and reporting. Gradle stays resident when invoked through the task, making the
standalone bundle useful when minimizing background processes. The whole-machine
CPU metric can miss interference on a single core. The clock domains and native
observer are validated on Linux. Portability of the inputs does not establish
portability of the outcome.

## Next experiment with highest evidentiary value

Use the eight-JVM locality suite on a quiet second Linux machine, with the same
JDK build where possible. Record both backend order and clean-pair counts. Compare
each host's paired directions and absolute response latencies, keeping each
host's data intact. If the reversal persists, a preregistered follow-up with more
fresh seeds and a longer common window can strengthen the rare-tail claim. A
separate observer should independently check intended-arrival and completion
times. The 84-JVM suite is useful for broader exploratory coverage. It is a
lower priority than testing the headline effect on independent hardware.

## Checks

The fresh offline mechanism check passed 64 forks, 32 pairs, 1,580 nonempty
quantiles, 64 histogram unions, 960 threshold bounds, 790 paired ratios and
3,456 model summary fields. The service verifier passed 184 forks and 3,520
quantile checks. The predictor verifier passed 60 forks, 1,420 quantile checks
and 720 reconstructed model values. The four canonical dataset hashes matched
their archived values. These checks do not add a research observation or qualify
a previously warning-bearing fork.

The Gradle quick suite passed its Java tests, 48 runner tests, four timing
controls and four diagnostic workers. The 84-worker research suite was inspected
as a design. The quick suite has short windows and retains its quality warnings.
