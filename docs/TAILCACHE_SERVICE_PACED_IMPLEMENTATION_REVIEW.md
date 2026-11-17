# Matched-arrival implementation review — 17 November 2026

The fixed 24-JVM design follows the prospectively recorded paced protocol. It reuses the screen runtime byte-for-byte, requires four successful matched controls, conserves all 1,500,000 intended/completed requests and paired write counts, and preserves saturated/paced cohort identities. Primary service p99.9 and scheduled-response p99.9 are labelled separately. The independent raw auditor now validates response counts against scheduled arrivals; closed-loop response remains empty.

The controller source archive includes the prospective paced and observer protocols. Runtime override support is preparatory for a separate JMH cohort; the paced controller does not use it. Metadata records zero new cache-functional qualification JVMs because the unchanged runtime reuses the retained two-JVM receipt. Thirteen focused design tests pass; the historical screen is re-audited with the updated auditor before collection.

No exact threshold, causal heap-placement or significance claim follows from two pairs. Full GC, dropped allocation demand and external CPU warnings remain visible. No exclusions/replacements are permitted without explicit retained adjudication. Collection completion and research completion remain distinct.
