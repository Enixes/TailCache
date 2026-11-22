# TailCache research handoff

Updated 23 November 2026 before the split-write experiment on Pop!_OS.

## Start here

- `codex/tailcache-portability` holds the launcher, the split-write suite,
  and the second-host results. Read the [run plan](PORTABLE_EXPERIMENT.md#split-write-timing-on-the-pop_os-host)
  and [second-host conclusions](second-host-20261120/README.md).
  The raw evidence is pinned at commit `4c3ab67`. [Portability PR #11](https://github.com/Enixes/TailCache/pull/11)
- `codex/tailcache-preprint` holds the current manuscript, PDF, and interactive
  companion on [Preprint PR #10](https://github.com/Enixes/TailCache/pull/10).
  It already includes the two-host results and the Agy review revisions.
  [Manuscript](https://github.com/Enixes/TailCache/blob/codex/tailcache-preprint/docs/preprint/MANUSCRIPT.md)
  · [Claim map](https://github.com/Enixes/TailCache/blob/codex/tailcache-preprint/docs/preprint/CLAIMS.md)
- The split-write experiment is implemented and planned. No Pop!_OS research
  forks had been launched at this handoff. The Gradle plan, launcher tests,
  Java functional checks, and four short Mac diagnostic forks passed. Two
  existing Java tests depend on Linux `/proc` and must pass on the target.

## Findings carried forward

| Question | Current answer |
|---|---|
| Does added heap pressure reverse ordinary saturated p99 or p99.9? | No robust reversal was observed in the tested range. The 4 KiB second-host matrix favors Caffeine at 0 and 288 MiB across 1%, 5%, and 10% writes. Some high-pressure forks missed a small fraction of churn demand. |
| Does payload size change saturated latency rankings? | In the 48 first-pass pairs, Chronicle led at 256 B and Caffeine at 4 KiB, including read-only p99.9. The original combined timing includes fresh-array construction on every write. |
| What reverses scheduled-response p99.9? | At 4 KiB, 5% writes, and 50,000 arrivals/s, Caffeine led with 2,048 eligible write keys and Chronicle led with 32,768. The direction repeated on both hosts, including the 90-second second-host cohort. |
| What supports the GC explanation? | On the second host, broad writes raised Caffeine mixed-GC pause overlap and shifted its reported tenuring threshold from 15 to 1. Chronicle's threshold remained 15. The logs describe aggregate heap behaviour. Individual cache-object promotion remains unresolved. |
| Where is the write-rate transition? | In the second-host 4 KiB sweep, Caffeine led all four pairs at 1.25% writes and Chronicle led all four at 1.5%. The 0.75% and 1% cells were mixed. The bracket is specific to the tested setup. |

Retain the unexplained Chronicle stalls, warning-bearing evidence, and the
distinction between Java heap occupancy and process RSS. The unconditional
Task 12 pressure-crossover decision remains **NO_GO**. The
[archive verifier](second-host-20261120/archive/README.md) reproduced 350 JVM
records offline. Reuse this evidence for the questions it answers.

## Resume the Pop!_OS work

Open the existing clean checkout on the Ryzen 7 5800X host. Fetch the two
branches before editing or collecting. An existing independent working tree
should be preserved before switching branches.

```sh
git fetch origin
git switch codex/tailcache-portability
git merge --ff-only origin/codex/tailcache-portability
./gradlew -q tailCacheReproductionPlan -PtailcacheSuite=split-write-timing
```

Inspect active benchmark processes and `results/split-write-popos-01` before
starting collection. Match native Linux, Temurin 21.0.13+9, G1, and the
12-CPU JVM budget used for the original saturated matrix. Use the run plan's
single Gradle command after confirming host readiness and run authorization.
Allow 65–75 minutes with cached dependencies. The command runs an eight-JVM
instrumentation pilot before 16 research JVMs. A failed pilot stops research.
Use the original output directory and frozen bundle to reuse sealed slots.
Keep any interrupted attempt, warnings, and the bounded external retry receipts.

After qualification and reconciliation, use the new research cohort as the
primary source for the paper's write-cost comparison at 256 B and 4 KiB,
5% writes, and zero ballast. Present array construction, adapter `put()`,
read-only and whole-operation measurements from the same forks. Retain
the earlier matrix for the broader pressure and write-rate comparisons and the
two-host scheduled cohorts for the response reversal. Keep pilot evidence in its
qualification role. Update the preprint and companion after the research outcome
is known. Author review, artifact access and licensing, and deposit remain
publication steps.

The optional next experiment is the [higher-arrival-rate locality suite](PORTABLE_EXPERIMENT.md#optional-follow-up-at-a-higher-arrival-rate).
It varies read demand at approximately 2,500 writes/s. Review the split-write
results first and run the load follow-up in its own result directory.

## Resume the conversation

Restore the separately transferred private Codex session backup, then run
`codex resume -C "$PWD" <session-id>` from the updated checkout. Keep the
session and its tool history outside Git. The backup includes the exact ID
and recovery instructions. If the session backup is unavailable, open Codex
from the checkout with the prompt below.

> Continue TailCache from the 23 November handoff in `docs/SESSION_HANDOFF.md`.
> Read the split-write run plan and inspect live workers and the retained
> result directory first. The implementation and Agy manuscript revisions are
> ready. Use the native Pop!_OS host and the frozen pilot and research design
> when collection is authorized. Preserve original evidence and gates. If the
> split results qualify, use them for the manuscript's write-cost comparison
> and retain the prior cohorts for the other claims.
