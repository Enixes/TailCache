# Midpoint explorer QA inventory

The benchmark has finished; browser checks cannot perturb its collected timings. Use the available persistent Node REPL with installed Playwright core and a headless browser on this quiet/headless host. No package installation, browser account access or change to desktop services is needed.

Claims/controls to verify:

- New jump link reaches the fresh-cohort panel in the existing historical explorer; original study-data remains identical.
- Three cohort options retain separate seeds. Primary has three pairs; each seed check has one, without phantom pairs.
- Response/service/gap channel selectors and four percentile selectors change graph titles and per-point conclusions; switching away/back restores correct data.
- Every point shows fork ranges, individual ratios, mixed directions and warning-free coverage; no confidence intervals or interpolated thresholds.
- Ballast and pair selectors decode the matching two full distributions and threshold-count table. Rapidly changing selections must not display a stale curve.
- Resource disclosure expands and shows measured RSS, post-GC heap, GC exposure, B/op and warnings.
- All three downloads match their retained JSON/CSV content and hashes.
- Static graphs agree with the audited dataset. Desktop and 320/390 px layouts remain readable, scroll tables internally and do not overflow the page. Review screenshots separately from DOM checks.
- Historical graph/table controls still render; no console errors or unexpected network calls.

Off-happy-path checks: switch to a one-pair seed cohort after selecting pair3; rapidly change curve selections and return; compare warning-bearing primary104 with a clean104 seed observation; check empty/missing-pair handling via implementation/unit review without altering measured data.
