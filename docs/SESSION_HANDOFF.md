# TailCache research handoff

Checkpoint recorded on 19 November 2026. Use this file to continue the project
from a new Codex chat on a second machine.

## Start here

- Work on `codex/tailcache-portability` for the runner and the next replication.
  The reviewed runner is at `b8318490947f9d104edea089956616f4d67801bd`, with
  later documentation commits on the branch. [Draft portability PR #11](https://github.com/Enixes/TailCache/pull/11)
- The manuscript is on `codex/tailcache-preprint`. PR #11 uses the
  pre-portability snapshot as its review base. The first two portability commits
  also appear in the manuscript branch, so coordinate integration before merging.
  [Draft manuscript PR #10](https://github.com/Enixes/TailCache/pull/10)
- Read the [research state](TAILCACHE_CURRENT_STATE.md), the
  [research and portability review](PORTABLE_EXPERIMENT_DEEP_REVIEW.md), and the
  [run guide](PORTABLE_EXPERIMENT.md) before making changes.

## Scientific position

The strongest result is a bounded scheduled-response p99.9 reversal. At 5%
writes, 4 KiB values, 50,000 intended arrivals/s, and matched fresh-write
allocation demand, Caffeine led with 2,048 update keys and Chronicle led with
32,768. Both directions repeated across two seeds and reversed backend order on
one host. Warning-free coverage was 0/4 concentrated pairs and 1/4 distributed
pairs. Chronicle led at p99.99 and p99.999 in all four concentrated pairs.
The extreme tail is sparse in 30-second paced windows.

The original pressure-induced ordinary-service p99/p99.9 crossover was not
established. Payload changed rankings without establishing a stable threshold.
Measured GC pauses help explain response latency after a run. The prospective
write-rate boundary forecasts failed. Treat lifetime, locality, and policy
activity as bundled effects. The original unconditional Task 12 decision
remains NO_GO. [Retained mechanism results](mechanism/RESULTS.md)

## Resume the experiment

As of this checkpoint, the portability branch passed the Gradle quick suite
with four diagnostic workers and four timing controls. The eight-JVM
independent-host locality replication and the full 84-JVM campaign are pending.
The historical recovery timer on the collection host was inactive.

Clone the review branch on the second machine and open that checkout in Codex.

```sh
git clone --branch codex/tailcache-portability git@github.com:Enixes/TailCache.git
cd TailCache
```

Use Java 21 and Python 3.10+ on a quiet Linux host. Keep the frozen 512 MiB
experimental heap, the JVM CPU budget, and zero priming. Prefer the same JDK
build when comparing hosts. Confirm which machine is running the workload and
inspect live processes and existing manifests before launching. The quick check
uses a separate output directory.

```sh
./gradlew --no-daemon tailCacheReproduce -PtailcacheSuite=quick -PtailcacheOut=results/second-host-smoke
```

Once the host is ready and the quick report has been reviewed, the next research
run is the locality suite. It takes about 21 minutes of workload time. Use the
following command to let Gradle exit after the build and before timing.

```sh
python3 scripts/tailcache_portable.py reproduce --suite locality --out results/second-host-locality
```

Use a new result directory for each host. Repeat an identical command in the
original directory on the original host to resume verified slots. Preserve
failed, interrupted, and warning-bearing attempts. Keep the two hosts' paired
distributions separate, record absolute latencies and ratios, and report
warning-free coverage. The summary and point conclusions are under
`suite-analysis-*/`. Stop and review after the locality suite before turning to
the broader matrix.

## Evidence to carry

The tracked repository includes the derived datasets, audits, figures, and
manuscript. The original host's git-ignored `evidence-archives/` and local
`results/` are separate. A fresh independent run can start from the clone.
For a raw-evidence audit, copy the relevant complete cohort directories with
manifests, logs, and hashes over a private channel. Keep recoveries and rejected
forks in their original cohorts. See the
[retained mechanism evidence review](mechanism/REREVIEW_20261118.md).

## Prompt for a new Codex chat

> Continue the TailCache research from this checkout. Read
> docs/SESSION_HANDOFF.md, docs/PORTABLE_EXPERIMENT_DEEP_REVIEW.md, and
> docs/PORTABLE_EXPERIMENT.md. Verify the branch, current host, live processes,
> and retained manifests first. Plan before implementing or collecting. Focus
> on an independent eight-JVM locality replication and preserve the historical
> evidence. Review raw and paired results before making a research claim.
