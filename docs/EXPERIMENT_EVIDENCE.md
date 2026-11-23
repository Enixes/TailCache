# TailCache experiment evidence

Use the [experiment status](TAILCACHE_CURRENT_STATE.md) for the answers and
workload limits. The [claim map](preprint/CLAIMS.md) links each comparison to
its underlying measurements.

- [20 November results](second-host-20261120/) and [archive](second-host-20261120/archive/)
- [23 November results](nov23-popos-followup/) and [archive](nov23-popos-followup/archive/)
- [Interactive results](../output/html/tailcache-preprint-reader.html). Download
  the HTML and open it in a browser to filter paired measurements by workload,
  percentile, or timing boundary.

From the repository root, use Python 3.10+ to verify both archives without
launching a JVM or running new benchmarks.

```sh
python3 scripts/tailcache_verify_archive.py
python3 scripts/tailcache_verify_archive.py --popos-followup
```

Reproduce the [timing and G1 audit](preprint/timing-audit.json) and regenerate
the interactive results from the retained inputs.

```sh
python3 scripts/tailcache_preprint_timing_audit.py docs/second-host-20261120/archive \
  --followup-archive docs/nov23-popos-followup/archive > /tmp/tailcache-timing-audit.json
cmp docs/preprint/timing-audit.json /tmp/tailcache-timing-audit.json
python3 scripts/render_tailcache_preprint_reader.py
```

Use the [portable collection guide](PORTABLE_EXPERIMENT.md) to run a fresh workload.
