# TailCache 08 — implementation and researcher review

## Status

**Closed as a completed baseline gate; no performance result is reportable.**

The initial short validation, full candidate A, cleaner full candidate B, and targeted long replication have all been reviewed. Candidate B removed the broad host/page-fault failure from candidate A. A 12-warmup / 8-measurement / 3-fork two-order 256-B probe then reduced all counterbalanced p99 ratios below the 1.25 screening threshold, so future TailCache 08-style runs now use 12/8/3 as the minimum.

The remaining blocker is JIT stability: a separate 12/8 compiler diagnostic still recorded material compilation throughout measurement. This fails the conservative compiler screen and prevents promotion of the access-cost numbers.

See `TAILCACHE_08_FINAL_REVIEW.md` for the evidence, ratios, protocol change, rejected CPU-affinity experiment, persisted-state limits, and final claim boundary.

## Claim boundary

TailCache 08 is not the heap/live-set crossover experiment. Its replacement-value bank keeps Chronicle payload shadows on the Java heap, SampleTime can miss rare pause-exposed requests, and persisted diagnostics are separate forks. It validates the baseline machinery and exposes measurement limits; it does not answer RQ1/RQ2.
