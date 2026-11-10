# TailCache: midpoint experiments and preprint plan

Planning date: **9 November 2026**, Asia/Kolkata. Earliest application deadline supplied by the user: **1 December 2026**. Target a publicly citable, reviewed version by **26 November**, with submission preparation earlier. These are planning targets, not guaranteed repository processing dates.

Status: **PLAN ONLY — no new benchmark, submission, public release or TickTick rescheduling performed.** The conditional Task 12 study and exploratory analysis remain complete in their declared scopes; this is new follow-up work, not a reopening or relabelling of historical evidence.

Publication planning update, 9 November: see [the initial literature and venue review](TAILCACHE_LITERATURE_AND_PUBLICATION_STRATEGY.md). Existing literature already covers the broad off-heap/GC tradeoff and open/closed workload distinction. ICPE 2027 EERCS is a candidate venue with registration closing 10 November at 17:29:59 India time according to its live submission page; no registration has been made. Its January notification date cannot provide a guaranteed acceptance for December applications. A possible 12 November preprint v1 is an accelerated drafting target, subject to evidence/claim review, not a promised journal publication date.

## 1. Paper-sized research contribution

Working title: **TailCache: Heap Pressure, Allocation and Tail-Latency Tradeoffs in Java Caches**.

The contribution should be a reproducible, workload-specific account of when moving retained cache values off heap helps, how payload materialisation changes that benefit, and why operation latency and scheduled response latency can rank the same caches differently. A universal threshold, a guaranteed GC cliff or an unconditional off-heap win is not required.

Keep the original RQ wording and identify scheduled response as an explicitly declared follow-up estimand. The original ordinary-service p99/p99.9 question may remain unresolved or negative in a tested range. Do not silently answer it with response p99.9, buffer reuse or a more extreme percentile.

Use the [frozen exploratory claims](TAILCACHE_FROZEN_CLAIMS.md) as the current claim boundary. Write the method, related work, original conditional/null results and limitations now; add the fresh midpoint results as a separate cohort later. Do not hold writing for a larger matrix.

## 2. Next collection: the missing 104 MiB midpoint

### Batch A — fixed 18-JVM follow-up

| Factor | Proposed frozen setting |
| --- | --- |
| Backends / contract | Caffeine versus Chronicle in memory; ordinary get, immutable fresh write values |
| Payload / resident entries | 4 KiB / 32,768 |
| Common retained application ballast | **0, 104, 208 MiB**; rerun both anchors with the midpoint |
| Replication | Three fresh paired forks per point: **18 workload JVMs** |
| Runtime | One exact source/compiled-runtime cohort throughout; Java 21, G1, Xms=Xmx=512 MiB |
| Workload | One worker, uniform approximately 95/5 reads/updates, seed 24301, 32 MiB/s offered background churn |
| Arrival schedule | 50,000 requests/second; response measured directly from intended arrival to completion |
| Phases | 12 s warmup, 2 s conditioning, 30 s offered measurement window; retain any drain time |
| Main endpoint | Scheduled-response **p99.9**, Chronicle/Caffeine ratio by paired fork |
| Secondary endpoints | p99, p99.99, p99.999; full survival curves; >100 microseconds, >1 ms, >10 ms; throughput, allocation, GC and occupancy |
| Order | Freeze the existing deterministic shuffled cells and alternating backend order; disclose that three pairs give imperfect order balance |

Purpose: repeat the 0-to-208 MiB response direction change and determine which side of it 104 MiB occupies. Do not compare a lone new midpoint to historical anchors and call that a new source-matched confirmation.

**Interpretation rule:** show all three paired ratios at every pressure point. A consistent direction requires all three valid pairs to agree; mixed/missing pairs are unresolved. This is a descriptive replication criterion, not a statistical-significance test. If anchors do not repeat, report non-replication before attempting to narrow a bracket. Do not interpolate an exact threshold or assume pressure effects are monotonic.

Report all listed percentiles even if the headline direction is inconvenient. At 50,000/s for 30 s, a complete fork has 1.5 million responses, only about 15 observations beyond p99.999. Those observations can share a pause; they are not 15 independent stall episodes. p99.999 remains secondary with explicit support counts, not the main evidence for a precise crossover.

### Bounded optional additions — not an automatic expansion

1. **One further midpoint, maximum 6 workload JVMs.** If Batch A reproduces opposite endpoint directions and 104 MiB has a consistent direction, select 52 MiB for a 0–104 bracket or 156 MiB for a 104–208 bracket. Three new pairs at the selected point are adaptive exploration, separately labelled. If 104 is mixed or anchors fail to repeat, do not keep bisecting until an attractive result appears.
2. **Two extra workload seeds, maximum 12 workload JVMs.** Prefer these over more pressure points if the main concern is repeatability: one pair per seed at each of 0/104/208 MiB. The current focused runner hardcodes the workload seed, so explicit seed plumbing, correctness review and a new source freeze are required before this batch. Analyse its cohort separately. One pair per seed provides limited robustness, not precise seed-level confidence bounds.
3. **Collection cap before preprint v1:** 18 required planned workload JVMs; at most 18 additional workload JVMs above, plus separately counted controls. No days-long campaign. Freeze optional choices before their collection and finish new collection by **14 November** unless a concrete correctness defect requires a revised plan. Do not make a favourable outcome a completion requirement.

No new 256 B sweep is required for the narrow 4 KiB midpoint objective. The existing 256 B evidence can describe payload-dependent tradeoffs, but does not establish how the same response crossover moves with payload. If that stronger RQ2 claim is essential, it needs a separate matched response design; otherwise state the limit in v1. Do not combine the 256 MiB-heap cliff diagnostic with 512 MiB-heap results as a payload-only comparison.

## 3. Targeted measurement and evidence work

Before launch, freeze source/runtime, complete schedule, endpoints, warning/rejection rules and an immutable output directory. Reuse source-matching controls where appropriate; run the existing floor and injected-stall controls for the new cohort. Verify trace/value correctness, histogram counts, request conservation, clock windows, analytics disabled and logged tiering policy. Retain raw histograms, GC logs, allocation, actual churn delivery, post-GC occupancy and host/power/thermal/filesystem metadata.

Pair backends at equal application ballast and offered allocation demand. Report resulting backend occupancy separately; do not equalise total heap occupancy and remove the retained-heap advantage. Pressure labels must be calibrated within payload/heap settings rather than treated as universal percentages.

Preserve completed slots on interruption and verify their hashes on resume. Record interrupted/rejected slots explicitly. A noisy fork does not erase an entire batch. Classify external host warnings separately from workload-caused behaviour; Full GC, evacuation failure, queue debt, throughput collapse or OOM may be outcomes, not inconvenient outliers. Never drop or silently replace them. OOM/timeouts cannot yield a complete latency distribution; report survival and censoring limits. Source corruption or failed correctness controls block affected claims.

Use warning-inclusive results and a separately disclosed clean-pair sensitivity view, with pair coverage visible. Do not pool rejected histograms, trim outliers, subtract timing floors or backfill historical cohorts into fresh slots. A fresh follow-up cannot retrospectively qualify the original unconditional protocol.

The [deferred research list](TAILCACHE_12_DEFERRED_RESEARCH.md) remains the broader roadmap. For v1, bound observer claims to the instrumented workload, quantify retained floor/observer evidence and disclose interference. A whole new joint-observer campaign is not required to describe this narrow instrumented result. If a claim depends on recorder neutrality, establish it or remove that claim. Use GC/allocation records to support mechanisms, without inventing operation-by-operation causal attribution from aggregate histograms.

## 4. Reconcile conflicting notes before drafting conclusions

The [cliff diagnostic synthesis](TAILCACHE_12_CLIFF_DIAGNOSTIC_AND_SYNTHESIS.md) contains useful discovery evidence, but is not the final claim authority. Preserve it as history and add a reconciliation in the paper/evidence map:

- Distinguish synthetic expected-interval correction in the diagnostic from the focused harness's directly measured scheduled response. Neither establishes externally generated production network latency.
- Do not promote the diagnostic's single-fork ordinary-service win to a replicated service crossover; later paired results must remain visible.
- Do not call an occupancy value an exact, universal G1 cliff. Heap size, allocation, collector ergonomics and host matter.
- Buffer reuse changes read ownership and allocation. Keep it a separate API contract; neither “reuse is mandatory” nor “ordinary Chronicle cannot win” follows generally.
- Remove unsupported claims that other implementation languages guarantee hard tail-latency SLAs. Avoid broad claims about research rarity without a literature review.
- Preserve original conditional acceptance, the stopping-policy amendment, warning-bearing cells, runtime differences and the post hoc status of exploratory extreme endpoints.

## 5. Live task audit and proposed new dates

Checked TickTick on 9 November. Raw selected task definitions are saved in [the task snapshot](TAILCACHE_PREPRINT_TASK_SNAPSHOT.json). Task status is the returned status field; stale completedTime/checklist fields are not treated as overriding it. This plan proposes dates; it does not change TickTick.

| Existing task | Live status / current date | Work remaining for v1 | Proposed target |
| --- | --- | --- | --- |
| Task 12: RQ1/RQ2 campaign | Completed in TickTick, 8 Nov; original protocol remains unqualified | Preserve conditional/exploratory scope; add new cohort separately | Midpoint collection 10–12 Nov; any bounded additions by 14 Nov |
| Task 13: Analysis and publication charts | Open / 14 Nov | Much analysis/explorer exists; produce static paper figures, fresh-cohort results, uncertainty and a claim-to-evidence table | 14–16 Nov |
| Task 14: 8–10-page technical report | Open / 21 Nov | Full manuscript, related work, methods, findings, threats and reproducibility appendix | Outline now; complete draft 17 Nov |
| Task 15: Repo and reproduction | Open / 28 Nov | Frozen source/dependencies, licences, small smoke command, offline figure regeneration and documented full-run command; test clean reproduction | 18–20 Nov |
| Task 16: Technical edit and evidence audit | Open / **5 Dec** | Check every headline number, source citation, exclusion, endpoint definition, unit, caption and claim | **20–22 Nov** |
| Task 17: Release and application artifact | Open / **12 Dec** | Versioned PDF/source/data release; public citation; 150-word abstract, CV bullet and SOP paragraph | Submission-ready 23 Nov; citable release target **26 Nov** |
| Master's: Application-ready TailCache evidence | Open / 2 Nov | Accurate contribution narrative and working repository/report/release/PR links | 26–28 Nov |
| Chronicle PR 01: Reproducer | Completed / 11 Oct | Reuse documented result; verify any status claimed in applications | No preprint dependency |
| Chronicle PR 02 / 03: Fix and submission | Open / 20 and 27 Dec | Focused upstream fix/tests, contribution rules and review; verify live upstream status before describing it | Parallel only if bounded; not a preprint blocker |
| Task 10 / 11: Secondary gate / persisted two-JVM sharing | Open / 13 Dec and undated deferred | Reconsider only with a separate hypothesis and protocol | After application v1 |

The parent project's old checklist uses RQ labels for backend ranking and sizing that differ from the current crossover RQs. Reconcile wording in application material; do not silently renumber questions in historical records. Task 10's live open status also differs from the local completed gate-review history; report that distinction rather than treating a local review as an upstream task closure.

Additional work in the repository roadmap: locality/read-write mix (RQ3), concurrency (RQ4), collector sensitivity, persisted-warm versus cold/open, sizing and eviction. These remain future work for v1. No full Cartesian matrix, two-JVM persistence, new collector or second host is required for a narrowly scoped paper. A second host could strengthen generalisation later.

## 6. Minimum manuscript and artifact

Aim for 8–10 main pages plus references/appendix as needed:

1. Abstract, motivation and explicit RQs.
2. Related work: on/off-heap caching, JVM GC/allocation, measurement interference and coordinated omission. Verify primary papers and official implementation documentation; establish the narrow contribution without claiming novelty before that review.
3. Semantics and method: ordinary get versus reuse, common ballast versus total heap, saturated service versus scheduled response, source cohorts, controls and acceptance amendments.
4. Results: original conditional/null evidence, replicated focused evidence, fresh midpoint cohort and optional clearly separated adaptive/seed follow-ups.
5. Mechanism evidence and limits; bounded practical conclusions.
6. Threats, reproducibility, contributor roles and appropriate tool-use disclosure.

Core figures: response p99.9 versus common ballast with each fork visible; service/response contrast; full-tail survival and threshold probabilities; allocation/GC/occupancy evidence; compact payload/contract comparison. Label range bars as ranges, not confidence intervals. Include counts, windows, warning coverage and cohort identity. Do not publish the interactive explorer alone as the paper's figure set.

Artifact: manuscript PDF and editable source, bibliography, versioned code, selected raw/derived data with checksums, offline regeneration instructions and a short reproduction path. Separate quick integrity/figure reproduction from expensive full measurement. The protected Vercel explorer can stay protected; it cannot be the only research artifact an admissions reader needs to access.

## 7. Citable release and application timeline

- **9–12 Nov:** freeze Batch A and begin manuscript/related-work outline; check author names, affiliations, contributor roles, mentor/reviewer availability and arXiv account/endorsement path.
- **13–16 Nov:** finish bounded collection if justified, freeze data and static figures, close the diagnostic-versus-focused claim reconciliation.
- **17 Nov:** complete manuscript draft. Negative or mixed midpoint results are written up, not grounds to restart the campaign.
- **18–22 Nov:** clean reproduction, substantive independent human review if available, number/citation audit and revisions. Do not label AI review as independent human peer review.
- **23 Nov:** prepare the approved submission/release package. Start submission early enough for possible endorsement or moderation delays; no guaranteed arXiv acceptance date.
- **26 Nov target:** stable public manuscript/citation and linked artifact. If arXiv is pending, an approved public repository deposit can provide a citable version; accurately identify its venue and review status.
- **27–30 Nov:** verify access while signed out, finalize abstract/CV/SOP wording, and check each programme's actual deadline/timezone with the user. The supplied 1 December date is the planning constraint, not verification of individual programmes.

Official guidance checked for this plan: [arXiv endorsement](https://info.arxiv.org/help/endorsement.html) requires endorsement for a first submission or new category; [submission guidance](https://info.arxiv.org/help/submit/index.html) includes moderation and expects author submission. Endorsement/moderation is not peer review. [Zenodo upload guidance](https://help.zenodo.org/docs/deposit/create-new-upload/) allows reserving a DOI, but the DOI is registered only when the record is published. A reserved DOI or private draft is not yet a public preprint.

Before publication, confirm the final authorship/affiliation, manuscript, licence and public contents with the user. Keep Vercel protection unchanged. For applications, use “preprint” or “technical report” with the actual public identifier once available; use “manuscript in preparation” before then. Verify submitted/reviewed/merged Chronicle contribution status separately. A preprint need not claim peer review or a universal win to document a meaningful systems investigation.

## Next implementation unit

Prepare Batch A's exact frozen manifest and controls, inspect native host/disk readiness and existing jobs, and make only the small runner/report changes needed for this cohort. Review correctness and resume handling before launch. No broader benchmark campaign is implied by this planning document.
