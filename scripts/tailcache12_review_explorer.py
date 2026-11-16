#!/usr/bin/env python3
"""Self-contained reviewed-paper section for both retained-results explorers."""
import base64
import hashlib
import html
import json
import pathlib
import re
import tailcache12_preprint as paper

ROOT=pathlib.Path(__file__).resolve().parents[1]
START='<!-- TAILCACHE_REVIEW_START -->'
END='<!-- TAILCACHE_REVIEW_END -->'


def render_component():
    base=ROOT/'docs/preprint'
    package=json.loads((base/'paper-data.json').read_text());checks=paper.verify(package)
    claims=json.loads((base/'claims.json').read_text())
    figures=json.loads((base/'figure-index.json').read_text())
    manifest=json.loads((base/'render-manifest.json').read_text())
    esc=html.escape
    def download(path,label):
        content=path.read_bytes();encoded=base64.b64encode(content).decode()
        mime='application/json' if path.suffix=='.json' else 'text/markdown'
        return f'<a class="rv-download" href="data:{mime};base64,{encoded}" download="{esc(path.name)}" data-sha256="{hashlib.sha256(content).hexdigest()}">{esc(label)}</a>'
    css='''<style>#review-update{margin:24px 0;padding:24px;border:1px solid #b7c9da;border-radius:10px;background:#fff;color:#182c43;font:15px/1.55 system-ui,sans-serif;overflow-wrap:anywhere}#review-update *{box-sizing:border-box}#review-update h2{font-size:25px;margin:0 0 10px}#review-update h3{font-size:17px;margin:16px 0 6px}#review-update p{margin:8px 0}#review-update .rv-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:18px 0}#review-update .rv-card{border:1px solid #d7e0eb;background:#f5f9fc;border-radius:7px;padding:14px}#review-update .rv-note{border-left:4px solid #176b91;padding:10px 15px;background:#edf6fb}#review-update .rv-muted{color:#506179;font-size:13px}#review-update .rv-actions{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}#review-update a{color:#0369a1}#review-update .rv-download{display:inline-block;padding:8px 12px;border:1px solid #a8bfd1;border-radius:5px;text-decoration:none;background:#fff;min-height:40px}#review-update summary{font-weight:650;cursor:pointer;padding:12px 0}#review-update .rv-table{overflow:auto}#review-update table{border-collapse:collapse;min-width:750px;width:100%;font-size:13px}#review-update th,#review-update td{padding:10px;border-bottom:1px solid #dce4ee;text-align:left;vertical-align:top}#review-update th{background:#edf3f8}#review-update figure{margin:20px 0;padding:12px;border:1px solid #d7e0eb;border-radius:7px}#review-update img{display:block;width:100%;height:auto}#review-update figcaption{font-size:13px;color:#506179;margin-top:10px}#review-update :focus-visible{outline:3px solid #1286b7;outline-offset:3px}@media(max-width:760px){#review-update{padding:15px}#review-update .rv-cards{grid-template-columns:1fr}#review-update h2{font-size:22px}}</style>'''
    parts=[START,css,'''<section id="review-update" aria-labelledby="rv-title"><p class="rv-muted">Reviewed state · 16 November 2026</p><h2 id="rv-title">What the evidence supports now</h2><p>The endpoint response ranking change repeats, but the middle point remains mixed. The manuscript now separates that result from service latency, payload effects and memory savings.</p><div class="rv-cards"><div class="rv-card"><h3>0 MiB: Caffeine lower</h3><p>Response p99.9: <strong>23.8–33.2 µs</strong> versus Chronicle’s 281.9–325.1 µs.</p><p class="rv-muted">Three clean primary pairs.</p></div><div class="rv-card"><h3>104 MiB: mixed</h3><p>Paired Chronicle/Caffeine ratios: <strong>0.427, 0.447, 8.500</strong>.</p><p class="rv-muted">One clean primary pair; clean additional seeds disagree. No further bisection.</p></div><div class="rv-card"><h3>208 MiB: Chronicle lower</h3><p>Response p99.9: <strong>239.2–334.3 µs</strong> versus Caffeine’s 921.1–1,188.9 µs.</p><p class="rv-muted">Three clean primary pairs.</p></div></div><p class="rv-muted">Fresh 4 KiB ordinary get · 512 MiB G1 · 50,000 intended arrivals/s · 30-second offered windows. Ranges span individual forks, not confidence intervals. An observed 0–208 MiB reversal does not locate a precise or universal threshold.</p><div class="rv-note"><strong>Keep the research questions separate.</strong><ul><li>Ordinary service p99/p99.9: no qualified 4 KiB forward crossover was established in the tested conditions.</li><li>Response p99.99/p99.999: Chronicle’s advantage already exists at baseline; it is not a pressure-emergent crossover.</li><li>Payload/RQ2: the focused payload sweeps use different pressure ranges. Movement of a common scheduled-response threshold was not estimated.</li><li>Memory: lower retained Java heap coexists with higher sampled Chronicle RSS. Equal heap limits are not equal total-memory budgets.</li><li>Reuse is a separate borrowed-buffer contract. Its sensitivity batches lack a contemporaneous ordinary-Chronicle arm.</li><li>The primary periodic trace touches 23,169 of 32,768 residents and updates 1,939 distinct keys. Uniform generation is not an unbounded random stream.</li><li>This compares complete library configurations; the ranking cannot be attributed solely to heap placement.</li><li>All nine one-second controls lack native CPU coverage; one also has a compiler warning. Their accounting checks do not establish workload host qualification.</li></ul></div><h3>Manuscript and review</h3><p><strong>Working draft, not an author-approved or submitted preprint.</strong> The review is agent-assisted, not independent human peer review. The original unconditional Task 12 protocol remains NO_GO.</p><p><a href="https://github.com/Enixes/TailCache/pull/10" target="_blank" rel="noopener">Review draft PR #10</a> · <a href="https://github.com/Enixes/TailCache/blob/codex/tailcache-preprint/docs/TAILCACHE_CURRENT_STATE.md" target="_blank" rel="noopener">Current research state</a> · <a href="https://github.com/Enixes/TailCache/blob/codex/tailcache-preprint/docs/DOCUMENTATION_INDEX.md" target="_blank" rel="noopener">All documentation</a></p><div class="rv-actions">''']
    for path,label in [(base/'MANUSCRIPT.md','Download manuscript'),(base/'RE_REVIEW_20261116.md','Download systems re-review'),(base/'claims.json','Download reviewed claims'),(ROOT/'docs/TAILCACHE_CURRENT_STATE.md','Download current state')]:
        parts.append(download(path,label))
    parts.append('</div><details id="rv-claims"><summary>Read all 14 reviewed claims and their limits</summary><div class="rv-table"><table><thead><tr><th>Claim</th><th>What is supported</th><th>Evidence scope / limit</th></tr></thead><tbody>')
    for c in claims:
        parts.append(f'<tr><th>{esc(c["id"])}</th><td>{esc(c["claim"])}</td><td>{esc(c["endpoint"])}<br>{esc(c["limit"])}</td></tr>')
    parts.append('</tbody></table></div></details><details id="rv-figures"><summary>View seven reviewed paper figures</summary>')
    for i,f in enumerate(figures,1):
        path=base/'figures'/(f['id']+'.png');raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=manifest['outputs']['figures/'+path.name]:raise ValueError('Figure hash mismatch')
        parts.append(f'<figure><img loading="lazy" src="data:image/png;base64,{base64.b64encode(raw).decode()}" alt="{esc(f["title"])}"><figcaption><strong>Figure {i}.</strong> {esc(f["caption"])}</figcaption></figure>')
    parts.append(f'''</details><details id="rv-checks"><summary>What the technical review checked</summary><p>All 162 focused/follow-up observations and 18 primary distributions match their retained audited source inputs. The corrected verifier rejects missing histograms and empty comparisons, checks offered-rate pairing, and remains active under optimized Python.</p><p>{checks['histogramPercentileChecks']} quantile checks · {checks['primaryHistogramThresholdChecks']} histogram threshold calculations · {checks['freshChannelThresholdConsistencyChecks']} channel/rate consistency checks · 24 targeted regression tests in the current review; 28 exactly matching offline regenerated outputs were verified in the prior review.</p><p>The 16 November host-only pass decoded all 621 focused/follow-up workload and control histograms, reconciled 486 published curves, 4,632 raw-file hashes, 207 GC summaries and all 30 fresh RSS summaries. The original auditor also reproduced its raw-window, GC, bootstrap and 19,782-member archive checks. These remain reproducibility checks, not proof of observer neutrality or event-level causal attribution. Frozen paper data SHA-256: <code>{hashlib.sha256((base/'paper-data.json').read_bytes()).hexdigest()}</code>.</p></details><h3>Before a formal release</h3><p>Independent domain feedback, final typesetting/author revision, clean Java harness reproduction, selected raw-evidence backup/release, and authorship/licensing/disclosure decisions remain open. No additional benchmark is planned for this scoped draft.</p><p><a href="#midpoint-followup">Explore the fresh midpoint and seed results ↓</a></p><p class="rv-muted">The historical explorer below keeps its original 132 forks and runtime/contract distinctions; the fresh follow-up contains 30 separate workload forks. No measurements are pooled or reclassified by this presentation update.</p></section>''')
    parts.append(END)
    return ''.join(parts)


def attach(page,component=None):
    page=re.sub(re.escape(START)+'.*?'+re.escape(END),'',page,flags=re.S)
    component=render_component() if component is None else component
    marker='<main class="wrap">'
    if marker in page:return page.replace(marker,marker+component,1)
    return page.replace('</body>',component+'</body>',1)
