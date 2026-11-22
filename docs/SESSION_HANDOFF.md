# TailCache research handoff

Updated 22 November 2026 after the second-host experiments and raw evidence audit.
This is the resume point for the Codex task **Start experiment on new host**.

## Start here

- `codex/tailcache-portability` holds the reproducible suites and second-host
  evidence. Commit `d78ab90` adds the measured results and `4c3ab67` archives
  the raw evidence. [Portability PR #11](https://github.com/Enixes/TailCache/pull/11)
- `codex/tailcache-preprint` holds the manuscript. The manuscript predates the
  second-host results. The two branches share some portability changes, so
  inspect their history before integrating the new evidence.
  [Manuscript PR #10](https://github.com/Enixes/TailCache/pull/10)
- Relative links in this handoff point to tracked files. Start with the
  [second-host conclusions](second-host-20261120/README.md),
  [raw archive and audit](second-host-20261120/archive/README.md), and
  [working manuscript](preprint/MANUSCRIPT.md).

## What the study can claim

| Question | Current answer |
|---|---|
| Does extra heap pressure flip p99 or p99.9 for ordinary cache-call latency? | The study did not establish a robust pressure-induced reversal. On the second host, at 4 KiB Caffeine led every pair at 0 and 288 MiB of extra retained application data across 1%, 5%, and 10% writes. |
| Does payload size affect service latency rankings? | Yes. In the same saturated-service matrix, Chronicle led all 24 pairs at 256 B and Caffeine led all 24 at 4 KiB. Some high-pressure 4 KiB runs dropped churn demand. A general payload threshold remains unresolved. |
| What flips scheduled-response p99.9? | At 4 KiB, 5% writes, and 50,000 intended arrivals/s, Caffeine led when writes targeted 2,048 keys and Chronicle led when writes targeted all 32,768. The effect replicated on the second host at 30 and 90 seconds with matched fresh-write demand. |
| Where is the write-rate crossover? | In the second-host 4 KiB sweep, Caffeine led 4/4 warning-free pairs at 1.25% writes and Chronicle led 4/4 at 1.5%. The 0.75% and 1% cells were mixed. The bracket applies to that setup, and earlier prospective boundary forecasts failed. |

A GC pause can delay many scheduled requests while overlapping few timed cache
calls. The observed pause shapes and backlog help explain the two rankings.
Update locality, value lifetime, and cache policy activity still vary together.
The observed-GC models do not provide a reliable before-run selector.
The p99.99 and p99.999 results include contrary runs with completion gaps
unexplained by logged GC or safepoints. The original Task 12 unconditional
pressure-crossover decision remains **NO_GO**.
[Mechanism data and limits](mechanism/RESULTS.md)

## Resume on another host

Clone the evidence branch, or update an existing clean checkout, before opening
the project in Codex.

```sh
git clone --branch codex/tailcache-portability git@github.com:Enixes/TailCache.git
cd TailCache
python3 scripts/tailcache_verify_archive.py
```

The verifier uses only the clone and Python 3.10+. It reconstructs the tracked
percentiles and point conclusions from **252 research JVMs, two retry JVMs,
36 diagnostic JVMs, and 60 timing controls**. Keep any private Codex session
backup separate from the clone. If only the clone is available, use the resume
prompt below.

The next task is to integrate the second-host evidence into the manuscript
abstract, results and figures, claims table, and reproducibility section on the
preprint branch. Cite the frozen archive. Report host-specific outcomes and
warning-free coverage, and retain the high-pressure churn and extreme-tail
caveats. Then complete author review, artifact access and licensing, and approval
for deposit. The manuscript is still a working draft.

No repeat of the completed suites is needed for that revision. For a new
replication, inspect active processes and retained manifests first, state the
question and plan before collection, and use a fresh output directory on each
host. The [portable run guide](PORTABLE_EXPERIMENT.md) has the Gradle commands and
Java 21 requirements. When resuming an interrupted run, preserve the same host,
original output directory and frozen settings. Keep original attempts and
bounded retries separate, and report paired results separately by host and
cohort.

## Prompt for a new Codex chat

> Continue TailCache from the 22 November handoff in
> `docs/SESSION_HANDOFF.md`. Read the second-host conclusions, verified archive
> index, and manuscript. Plan the manuscript integration before making changes.
> Use the replicated update-locality reversal as the main result and preserve
> the bounded negative answer for pressure-induced service crossover. Check PR
> and branch history before moving evidence to the preprint branch. Verify the
> archive offline in place of rerunning completed benchmarks.
