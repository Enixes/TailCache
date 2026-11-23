# Deep review and correction plan — 15 November 2026

Review scope: manuscript, claim map, figure/export code, retained source and archived evidence. Agent research/software review, not independent human peer review. No new workload run is authorised by this plan; the measured Java runtime and frozen paper input remain unchanged.

## Findings before changes

| ID / priority | Reproduced problem or research concern | Planned correction |
| --- | --- | --- |
| R01 / high | `verify()` returns 18 curves/72 checks after removing every curve. Counts are constants, not measured coverage. | Require the exact unique primary curve identity set, calculate coverage and check all plotted thresholds against curves. |
| R02 / high | `direction([])` returns “Chronicle lower”; integrity assertions disappear under optimized Python. | Reject empty/non-finite comparisons; use explicit validation exceptions for evidence checks and test optimized execution. |
| R03 / high | Pair identity omits offered rate; verification does not fully validate the fixed fresh schedule, all-channel counts or exceedance-rate consistency. | Include offered rate in pairing; enforce expected seed/block/pressure coverage, protocol values and count/rate conservation. |
| R04 / high | Manuscript broadly calls different payload regimes “payload-dependent” although the focused payloads have different ballast ranges. | Distinguish conditional same-pressure original evidence from disjoint focused regimes; explicitly leave the scheduled-response threshold shift unanswered. |
| R05 / medium | Service excludes recording and inter-operation delay; explanation can imply a pause necessarily falls inside a timed operation. The drain bound does not preempt an in-flight operation. | Document exact boundaries and cooperative drain condition; keep observer effects and gap/response distinction explicit. |
| R06 / medium | Original campaign outcomes are narrated but lack a compact table. Discussion/conclusion contain editorial instructions rather than paper prose. | Add original acceptance/outcome context and an explicit RQ answer table; finish bounded discussion and conclusion. |
| R07 / medium | Figure renderer uses default path simplification for very long survival steps and captions lack direct plotted primary p99.9 values. | Disable path simplification for empirical steps and put pair identity/values into reviewable tables; retain per-fork support and warning coverage. |
| R08 / medium | Offline receipt describes an older verifier; “raw evidence audited” and selected derived checks must stay distinct. | Perform fresh source-to-export reconciliation on the host, separately record portable/optimized verification, tests, exact regeneration and remaining artifact limits. |

## Execution order and completion checks

1. Freeze baseline hashes and source identities; inspect source-to-data consistency and primary citation records.
2. Repair validation and add adversarial tests for missing/duplicate curves, mismatched rates, corrupt counts/bins, empty comparisons and optimized execution.
3. Reconcile every exported observation/curve with its original audited input; do not modify those inputs. Regenerate only the derived package outputs.
4. Revise manuscript/methods/RQ language and complete discussion; add a dated primary-source citation follow-up.
5. Run bounded verification and isolated offline regeneration, visually inspect regenerated figures and record disposition of every finding.
6. Commit and push the corrections on `codex/tailcache-preprint` so PR #10 remains the review surface. No merge, new campaign or formal preprint deposit.

Authorship, independent human domain feedback, raw-evidence off-host release/licensing and clean Java harness reproduction remain explicit prepublication work. The original unconditional Task 12 protocol stays unqualified; fixes to paper tooling cannot retroactively qualify it.

## Disposition after implementation

| Finding | Correction and verification |
| --- | --- |
| R01 | Exact one-to-one curve identity coverage is mandatory. Counters now derive from actual work: 18 distributions, 72 quantile checks and 54 histogram threshold-bound checks. Missing/duplicate curves are rejected. |
| R02 | Empty/non-finite/nonpositive ratio sets are rejected. All 29 production assertions were replaced with explicit validation exceptions; valid and corrupt inputs were tested under optimized Python. |
| R03 | Offered rate is part of pairing. Validate the fixed 30-fork schedule, every fresh channel's conservation, percentile ranges and all 270 threshold/count/probability combinations. Reconcile response counts and rates directly with full histogram bins. |
| R04 | RQ2 now separates the original same-pressure conditional observation from the focused sweeps' disjoint pressure ranges. Scheduled-response threshold movement with payload remains explicitly unanswered. |
| R05 | Methods now place recording/bookkeeping outside the individual service boundary and describe inter-operation pauses. The drain limit is correctly described as cooperative rather than a hard deadline for an in-flight operation. Ballast labels count payload, not object/container overhead. |
| R06 | Added a compact original result table, all 16 original classifications as a separate artifact, fresh primary numeric table, explicit RQ answer table and complete discussion/conclusion prose. |
| R07 | Disabled Matplotlib path simplification. Regenerated all seven figures without changing numerical data; inspected the images. Generated figure/data diffs are marked generated so prose and claim review stay visible in GitHub. |
| R08 | New host-only reconciliation matches 162 observations (2,976 retained fields), 18 complete distributions and four original acceptance references. New portable checks and isolated reproduction are recorded separately from the retained 11 November receipts. |

### Verification result

- **18 targeted tests pass**, including the previously demonstrated missing-curves/empty-comparison failures, cross-rate pairing, strict threshold-straddling bounds, count/probability corruption and optimized execution.
- Portable verification reports **72 quantile checks**, **54 independent-from-summary histogram threshold calculations**, and **270 channel/rate consistency checks**. The histogram calculations and metadata checks are selected derived-evidence checks, not independent raw-event audits.
- Isolated offline regeneration from only the renderer and unchanged paper data matches **28 generated files exactly**. No raw archives, Java process or network request is needed for rendering.
- `paper-data.json` remains SHA-256 `a733eee906a863be68e7fd09ef9e6d3b51cf148ae69f5401c4a0706912ea50b7`. All six source provenance hashes and the original acceptance references reconcile. No measured Java code or retained raw/source evidence was edited.
- Primary reference follow-up confirms the pinned HDR rank semantics. Eight citation keys remain resolved; no numerical claim is sourced to a search snippet.

The current result remains an **exploratory, instrumented, one-host empirical study**. A successful source/figure audit does not prove observer neutrality, independent pause replication or generalisation to other loads/machines. No new benchmark was run to obtain a more convenient answer, and the mixed 104 MiB observations remain intact.

## Publication-readiness assessment

The manuscript now has a complete narrative draft and a more defensible RQ/result boundary. It is suitable for substantive author/domain review, not yet an author-approved deposit or a promise of journal acceptance. The remaining risks are contribution novelty/transferability, known measurement limitations and the final artifact/publication work listed above. A broader campaign is not required to write up these scoped findings honestly.
