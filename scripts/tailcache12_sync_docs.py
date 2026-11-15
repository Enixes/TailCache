#!/usr/bin/env python3
"""Generate the current research overview and index without rewriting history."""
import json
import pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
ACTIVE={'README.md','docs/SCOPE.md','docs/METHODOLOGY.md','docs/PLAN.md',
        'docs/TAILCACHE_CURRENT_STATE.md','docs/DOCUMENTATION_INDEX.md',
        'docs/TAILCACHE_PREPRINT_PLAN.md','docs/TAILCACHE_12_DEFERRED_RESEARCH.md'}


def main():
    state=json.loads((ROOT/'docs/TAILCACHE_PREPRINT_STATUS.json').read_text())
    lines=['# TailCache current research and manuscript state', '',
           '**Updated 15 November 2026.** This page is the current entry point. [All documentation](DOCUMENTATION_INDEX.md) distinguishes active guidance from dated experiment records.', '',
           '## Research answers', '',
           '| Question / metric | Current conclusion | Limit |',
           '| --- | --- | --- |',
           '| Ordinary service p99/p99.9 | No qualified 4 KiB forward crossover was established in tested conditions; some 256 B regimes differ or reverse. | Original unconditional protocol remains NO_GO. |',
           '| Scheduled response p99.9, 4 KiB | Fresh endpoint directions repeat: Caffeine lower at 0 MiB, Chronicle at 208 MiB; 104 MiB is mixed. | Observed reversal, not a population-threshold interval or exact threshold. |',
           '| Response p99.99/p99.999 | Chronicle is lower in every fresh pair, including baseline. | Baseline advantage, not pressure-emergent crossover; rare responses can share pauses. |',
           '| Payload effect / RQ2 | Original same-ballast conditional comparisons differ by payload. | Focused payload sweeps use different ballast ranges; scheduled-response threshold movement remains unanswered. |',
           '| Memory | Chronicle lowers retained Java heap but has higher sampled RSS in the fresh cohort. | Equal heap/application demand is not equal total process memory. |',
           '| getUsing | Separate borrowed-buffer sensitivity. | No contemporaneous ordinary-Chronicle arm in those sensitivity batches. |', '',
           '## Evidence and review', '',
           '- [Original campaign acceptance](TAILCACHE_12_FINAL_ACCEPTANCE.json): 402 invocations attempted, 191 conditionally usable campaign forks, one hard rejection; no retrospective qualification.',
           '- [Focused exploration](TAILCACHE_FOCUSED_RESULTS.md): 132 workload JVMs plus 36 controls, two runtime groups kept separate.',
           '- [Fresh midpoint/seed follow-up](TAILCACHE_MIDPOINT_RESULTS.md): 30 workload JVMs plus nine controls; no replacements; five compiler warnings retained; adaptive bisection skipped.',
           '- [Deep review](preprint/DEEP_REVIEW_20261115.md): 18 tests, 72 quantile checks, 54 histogram threshold calculations, 270 channel/rate consistency checks and exact offline reproduction.',
           '- [Source reconciliation](preprint/source-audit-20261115.json): all 162 exported observations and 18 primary distributions match their retained audited inputs.', '',
           '## Manuscript and explorer', '',
           '- [Working manuscript](preprint/MANUSCRIPT.md), [14 reviewed claims](preprint/CLAIMS.md), [seven paper figures](preprint/FIGURES.md), [original conditional comparisons](preprint/ORIGINAL_CAMPAIGN.md).',
           '- [Interactive explorer](TAILCACHE_RESULTS_EXPLORER.html#review-update), [standalone midpoint explorer](TAILCACHE_MIDPOINT_EXPLORER.html#review-update).',
           '- [Protected hosted explorer](https://tailcache-results.vercel.app/#review-update); [deployment receipt](interactive/deployment.json).',
           '- Manuscript branch `codex/tailcache-preprint`; [draft PR #10](https://github.com/Enixes/TailCache/pull/10), stacked on [research PR #9](https://github.com/Enixes/TailCache/pull/9).', '',
           'The narrative draft is complete for author/domain review. It is not author-approved, submitted or formally deposited. The technical review is agent-assisted, not independent human peer review.', '',
           '## Remaining before release', '',
           '1. Independent domain/contribution feedback and author revision.',
           '2. Final figure selection, typesetting and final numerical/citation/layout audit.',
           '3. Clean Java harness build/smoke reproduction; selected raw-evidence backup and release/licensing.',
           '4. Author names, affiliations, contributions, acknowledgements and tool-use disclosure; author-approved deposit.', '',
           'No further benchmark is planned for this scoped v1. Application deadline supplied: **1 December**; target citable release: **26 November**, subject to author approval and repository processing. These are planning dates, not submission or acceptance claims.', '',
           '## Historical records', '',
           'Old plans, gates, dated reviews and immutable acceptance records remain intact. Their “next run” or “not launched” language describes the date of that record. Use this page and the current preprint status for present decisions. Raw archives remain git-ignored; hosted HTML and derived data do not replace them.', '']
    (ROOT/'docs/TAILCACHE_CURRENT_STATE.md').write_text('\n'.join(lines))
    files=sorted(set([ROOT/'README.md',ROOT/'docs/DOCUMENTATION_INDEX.md',* (ROOT/'docs').rglob('*.md')]))
    index=['# Documentation index', '', '**Updated 15 November 2026.** Start with [current state](TAILCACHE_CURRENT_STATE.md). Every Markdown document is listed below. Dated plans/reviews are historical context and do not override the current reviewed claims. Hash-bound acceptance/research records are preserved byte-for-byte.', '',
           '| Document | Role |','| --- | --- |']
    for path in files:
        rel=str(path.relative_to(ROOT))
        role='Current manuscript/reproduction package' if rel.startswith('docs/preprint/') else 'Current guidance / entry point' if rel in ACTIVE else 'Dated plan, experiment record or historical review; read with current-state summary'
        link='../README.md' if rel=='README.md' else rel.removeprefix('docs/')
        index.append(f'| [{rel}]({link}) | {role} |')
    (ROOT/'docs/DOCUMENTATION_INDEX.md').write_text('\n'.join(index)+'\n')
    print(json.dumps(dict(documentsIndexed=len(files),phase=state['phase'])))


if __name__=='__main__':main()
