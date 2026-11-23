# Targeted ordinary-service crossover follow-up — proposal, 16 November 2026

Status: implementation and bounded functional validation completed; operational rules are frozen in [the execution protocol](TAILCACHE_SERVICE_CROSSOVER_PROTOCOL.md) before performance collection. This is a separate exploratory cohort, preserving the current manuscript and its frozen evidence. Planning began 16 November; the collection attempt is dated 17 November 2026.

## Questions and motivation

Distinguish (a) a pressure-emergent reversal at fixed payload from (b) a payload-dependent ranking at fixed common application demand. Chronicle being lower already at baseline establishes a winning region, not a pressure-emergent crossover. A failure/OOM establishes a feasibility boundary, not a latency win.

Retained evidence suggests a bounded search among intermediate payloads rather than assuming larger values help. At fixed 32,768 residents, increasing payload increases Caffeine retention but also Chronicle ordinary-get copying/allocation and fresh write-generation cost. Historical ordinary-service results already favor Chronicle in some 256 B regimes and Caffeine at 4 KiB p99/p99.9.

In one historical 4 KiB / 368 MiB saturated pair (block 1), Caffeine spent 66.544% of its measurement envelope in GC pause overlap yet service p99.9 was 8,727 ns versus Chronicle's 11,111 ns. Caffeine had 666 measured pauses across 3,709,660 completed operations. A long pause has a large wall-time cost but can affect few service observations, or fall outside operation boundaries. This explains a plausible mismatch between service quantiles and experienced stalls; it is not event-level attribution. Source: frozen paper-data.json, focused-rq1-capacity-edge-20261108-001, block 1, ordinary closed regime.

## Required bounded implementation work

- Keep primary ordinary-get 95/5 mixed-operation service p99.9; p99 secondary; p99.99/p99.999, gaps, throughput and GC diagnostic. Do not change the endpoint after observing winners.
- Add read/update service histograms alongside the combined distribution, using identical timed boundaries and classification/recording after the completion timestamp. Fresh value generation remains included in update service. Retain count conservation and matched timer/control evidence; added recording is not assumed neutral.
- Use one frozen longer deterministic trace, with actual distinct read/update key counts and fingerprints reported. Record its increased common retained footprint. New trace/runtime observations are not pooled with the old 40,001-operation trace. Define the final trace size before collection.
- Keep one cache worker, 32,768 residents, ordinary access, G1 with a 512 MiB heap, common 32 MiB/s offered churn and equal application ballast within each backend pair. Log achieved churn, compiler activity, memory, GC, host and value integrity. Do not equalize total heap occupancy across backends.
- Freeze source/runtime, phase durations, seeds, discovery schedule, feasible-pressure search rule, meaningful effect margin and confirmation rule before launching. Reuse getUsing only as a separately labelled future extension.

## Bounded sequence

| Stage | Design | Maximum workload JVMs |
| --- | --- | --- |
| Payload screen | 256 B, 512 B, 1 KiB, 2 KiB, 4 KiB; 0 and 208 MiB common ballast; one paired fork per cell | 20 |
| Targeted pressure probes | At most one promising fixed payload; up to four additional paired pressure points, chosen using a predeclared occupancy/feasibility rule; one point may refine an observed reversal | 8 |
| Fresh confirmation | Two selected bracket endpoints, three new paired forks per point, plus one held-out-seed pair per endpoint | 16 |

Ceiling: **44 workload JVMs plus separately declared controls**, with resumable immutable slots. The first screen is discovery only. Existing 256 B/4 KiB observations motivate the design; fresh anchor arms are necessary after a trace/recorder change. Calibration/probe JVMs count toward the eight-probe budget, rather than becoming an unbounded hidden campaign. Freeze exact pressure selection before execution; both backends receive the same ballast at each selected point. Candidate-specific pressure probes do not by themselves isolate payload effects.

Stop with an explicit result when the budget is reached: confirmed opposite endpoint directions, a baseline advantage, mixed/inconclusive evidence, no reversal in the tested feasible range, or a feasibility boundary. Avoid indefinite retries, favourable-fork selection and assuming monotonicity. A discovery-selected bracket needs fresh confirmation; a three-pair direction rule is descriptive, not a calibrated significance test. Report uncertainty and every contrary/warning-bearing fork. Completed valid slots survive interruption.

## Interpretation

The desired output is a compact map of where each complete library configuration has lower ordinary service latency, with the mixed workload, operation-specific diagnostics, allocation, throughput and pause exposure shown together. Report a reproducible finite bracket if one exists; do not claim an exact or universal point. A read-only advantage discovered in diagnostic decomposition does not answer the original combined 95/5 question.

This proposal improves the causal diagnostic evidence but does not isolate heap placement from all library differences. A preprint can retain the existing scoped results if this bounded follow-up finds no forward service crossover.
