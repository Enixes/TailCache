# TailCache research handoff

Updated 23 November 2026 after the Pop!_OS locality extension and split-timing pilots.

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
- The [23 November follow-up](nov23-popos-followup/README.md) is collected.
  The locality suite completed all 32 research JVMs. Both the all-write and
  sampled split-write pilots completed but failed their overhead gates.
  No split-write research forks were released.

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

## Resume the research

Read the [23 November review](nov23-popos-followup/README.md) and verify the new
evidence from the portability checkout.

```sh
python3 scripts/tailcache_verify_archive.py --popos-followup
```

The locality reversal at scheduled-response p99.9 held at 100,000 intended
arrivals/s at the same approximate writes/s as the 50,000-arrival baseline.
With 32,768 write keys Chronicle led at all tested loads. With 2,048 write keys
the rankings were mixed at 10% and 20% writes. Keep the paired warning and
scope details from that cohort.

The split-write gates rejected both instruments. The bounded sampled attempt
is complete. The existing combined-operation results still cover the original
service questions, and the decomposition into construction and adapter
`put()` remains unresolved. No benchmark is queued. The next manuscript
revision should add the locality sensitivity results and disclose the split
qualification outcome, then proceed through author review, artifact licensing
and access, and deposit approval.

## Resume the conversation

Restore the separately transferred private Codex session backup, then run
`codex resume -C "$PWD" <session-id>` from the updated checkout. Keep the
session and its tool history outside Git. The backup includes the exact ID
and recovery instructions. If the session backup is unavailable, open Codex
from the checkout with the prompt below.

> Continue TailCache from the 23 November handoff in `docs/SESSION_HANDOFF.md`.
> Read and verify the Pop!_OS follow-up archive. Add the bounded locality
> extension and split-timing qualification outcome to the manuscript and claims
> map. Preserve the completed saturated-service evidence and the failed gates.
