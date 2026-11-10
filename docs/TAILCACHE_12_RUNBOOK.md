# TailCache Task12 native research runbook

> **Update 8 November 2026:** Task12 is complete; see `TAILCACHE_12_FINAL_OUTCOME_REVIEW.md`. The accepted conditional final study did **not** use the warmup/conditioning counts listed below. It used 30 warmups, 8 conditioning and 8 analysed one-second intervals (`TAILCACHE_12_CONDITIONAL_FINAL_PROTOCOL_PLAN.md`; `original-protocol.json` in the final dataset). The rest of this runbook records the pre-final native controls. Any new run is a new protocol.

Use the local tailcache-12-crossover checkout. Check docs/TAILCACHE_12_STATUS.json, live processes, retained manifests and the latest researcher reviews first. A partial or launched job is never completion. Historical WSL/migration instructions are retained in [the legacy runbook](TAILCACHE_12_LEGACY_WSL_RUNBOOK.md); they do not authorize current native runs.

Current native controls are one worker, uniform periodic40001-operation trace,exactly38001 reads/2000 updates per period (rounded nominal95/5),seed24301,residents32768,fixed512MiBG1,common retained application inputs0/96/208/288MiB,payload256/4096 and independently offered32MiB/s churn. Normal warmup120×1s, fixed measurement-mode conditioning16×1s, analysed8×1s. Retain all24 physical measurement-mode intervals. Use result-transport-v2 and lifecycle-maintenance-v1. No percentile floor subtraction, post-hoc window movement or retained Chronicle payload bank. Both backends receive the same per-operation application demand; achieved throughput and intrinsic materialization allocation may differ.

Current Task12 JMH tasks use the explicitly modified generated sampler fixed-mixed-lcg-mask15-v1 with stock JMH core1.37. The mixed LCG selector uses a fixed mask15 (one in16) and retains every selected observation without adaptive buffer halving. Actual-library controls reproduced singleton-bin retention bias in the earlier adaptive pipeline. This is deterministic mixed selection, not independent Bernoulli sampling. Only the two Task12 generated sample stubs are overlaid. Each worker verifies and retains actual loaded class bytes/origin/hashes and exact original/overlay sources; stale or missing overlays fail. Other benchmark task classpaths and installed JMH jars are unchanged. Historical stock/adaptive data retain their original versions and are not corrected or pooled. Source-matched qualification, floors and pilot coherence must be repeated after this repair; previous passing prerequisites do not authorize current collection. See TAILCACHE_12_BUFFER_DECIMATION_PLAN.md and TAILCACHE_12_FIXED_BUFFER_IMPLEMENTATION_REVIEW.md.

## Host and source prerequisites

Java21 (including javac/jcmd),Python3,Git,systemd user scopes and cgroup-v2 are required. On nacht the pinned JDK is /usr/lib/jvm/java-21-openjdk, exact VM21.0.12.1+1. Finish builds/downloads before collection. Keep AC/governor/resource controls stable and inspect host metadata, temperatures, PSI and paging. The native wrapper changes no affinity, quota or priority; it locks out competing Task12 controllers and accounts actual worker descendants. Rebooting changes the qualified environment: collect fresh qualification on the new boot.

Commands below are templates: replace NEW with a unique identifier and never reuse an existing attempt or preflight. Use RTK prefixes on this checkout. Set JAVA_HOME to the reviewed Java21 installation (examples show nacht's path). Do not run tests, builds, archives or analysis during timed collection.

```sh
rtk proxy env JAVA_HOME=/usr/lib/jvm/java-21-openjdk ./gradlew --offline test compileTailCache12SampleOverlay resultToolsClasses
rtk proxy python3 -m unittest discover -s scripts -p 'test_tailcache12*.py'
```

Every new benchmark preparation requires at least3GiB free RAM and zero residual swap, followed by a fresh120-second quiet proof (300-second timeout,360-second first-JVM deadline). Release only clean task-file cache through the reviewed preparation helper; never disable swap or change policy during a campaign. If residual swap needs recovery, use a separately retained reviewed receipt and verify unchanged configuration. Do not repeat a privileged action that requires unavailable local authentication. Existing per-block host/compiler/GC/heap/churn/integrity gates remain mandatory.

## Qualification and calibration

```sh
rtk proxy env JAVA_HOME=/usr/lib/jvm/java-21-openjdk python3 scripts/tailcache12_native.py qualification-NEW scripts/tailcache12_sequence.py native-final-qualification-NEW --warmups 120 --conditioning 16 --transport-warmup --maintenance-warmup
```

Prepare clean task-file cache and verify zero swap before this source-frozen sequence. It collects controlled CPU-observer proof, quiet, functional14 blocks,pause2,JMH8 complete forks,actual unprofiled recorder8,pressure96two and independent floors10. XML/profiled diagnostics cannot replace the actual recorder qualification. Raw-replay all sources/environment/contracts and independently review before calibration. Complete screens may be referenced only as whole source/control/boot-matched units; incomplete/rejected screens are excluded.

```sh
rtk proxy env JAVA_HOME=/usr/lib/jvm/java-21-openjdk python3 scripts/tailcache12_native.py calibration-NEW scripts/tailcache12_calibration_start.py native-final-calibration-NEW native-final-calibrationquiet-NEW --qualification-prefix native-final-qualification-NEW --conditioning 16
rtk proxy python3 scripts/tailcache12_calibrate.py audit native-final-calibration-NEW
```

The chained launcher verifies matching qualification, prepares task cache/empty swap, binds fresh quiet evidence and starts the64-slot grid: two reversed orders, both recorders, common inputs and distinct resulting backend/channel occupancy bands. Calibration is diagnostic, never primary latency evidence. Require independent raw GC/worker-window reconciliation, occupancy replication, monotone pressure and sustainable high coverage before the pilot. Post-GC used space is not an exact live-object census; GC/safepoint totals overlap and must not be added.

Native replacement policy is prospectively frozen: only sole competing-CPU/power failures may receive at most2 extra attempts per logical slot and8 total per grid, after retained120-second quiet proofs. Select the first quality pass without endpoint rankings. All rejected candidates stay retained. JIT,paging,churn,integrity,missing exposure or variance failures cannot be replaced as outliers. Never resume a terminal rejected grid or import its passed forks into another cohort. A whole-grid repeat needs a separate bounded researcher declaration; there is no run-until-pass policy. Historical Windows retry semantics remain separate.

## Pilot and coherence

```sh
rtk proxy env JAVA_HOME=/usr/lib/jvm/java-21-openjdk python3 scripts/tailcache12_native.py pilot-NEW scripts/tailcache12_pilot_start.py native-final-pilot-NEW native-final-pilotquiet-NEW --qualification-prefix native-final-qualification-NEW --calibration native-final-calibration-NEW --conditioning 16
rtk proxy python3 scripts/tailcache12_pilot.py audit native-final-pilot-NEW
rtk proxy python3 scripts/tailcache12_observer.py coherence native-final-qualification-NEW-floors --pilot native-final-pilot-NEW
```

Pilot schedules160 slots:96 primary (unprofiled SampleTime/every-operation) plus64 supporting throughput,allocation/GC,logged SampleTime and compiler forks. Eight low/high backend/payload conditions have two counterbalanced passes and three independent primary forks per pass. Floor ratios, direction coherence, pause capture, exposure and predeclared p99/p99.9 variation must pass raw review before campaign freeze. Timing channels need not have equal absolute percentiles. Pilot observations never enter confirmatory statistics.

## Frozen campaign and separate robustness

Generate deterministic fingerprints for primary and predeclared robustness seeds before collection, using compiled matching main classes. Save output to a new file outside source paths and retain its source/runtime provenance:

```sh
rtk proxy /usr/lib/jvm/java-21-openjdk/bin/java -cp build/classes/java/main scripts/TailCache12Trace.java 32768
```

After complete raw-replayed pilot/coherence/variance and researcher protocol review, use the chained campaign controller so freeze/run share a native scope and fresh initial quiet/cache proof:

```sh
rtk proxy env JAVA_HOME=/usr/lib/jvm/java-21-openjdk python3 scripts/tailcache12_native.py campaign-NEW scripts/tailcache12_campaign_start.py native-final-campaign-NEW native-final-campaignquiet-NEW --pilot native-final-pilot-NEW --floors native-final-qualification-NEW-floors --traces /absolute/path/to/retained-traces.json
rtk proxy python3 scripts/tailcache12_campaign.py audit native-final-campaign-NEW
rtk proxy env JAVA_HOME=/usr/lib/jvm/java-21-openjdk python3 scripts/tailcache12_native.py robustness-NEW scripts/tailcache12_campaign_start.py native-final-robustness-NEW native-final-robustnessquiet-NEW --pilot native-final-pilot-NEW --floors native-final-qualification-NEW-floors --traces /absolute/path/to/retained-traces.json --primary native-final-campaign-NEW
```

Campaign-v2 requires16 conditioning intervals. Primary schedule has320 slots (192 primary plus128 supporting),16 backend/payload/pressure conditions,2 passes and3 primary forks per pass. Robustness uses the separately frozen seeds0xC0FFEE/0xBADC0DE and its declared endpoint/crossing-neighbor selection; never pool seeds, pilot or rejected candidates. Retain valid noisy forks. Unresolved/unstable/missing comparisons cannot support a resolved or global no-crossover claim. Paired fork/pass bootstrap uses50000 resamples with descriptive95% and nominal32-family Bonferroni intervals; only two outer passes give coarse conditional uncertainty.

## Preservation and final acceptance

```sh
rtk proxy python3 scripts/tailcache12_archive.py native-final-checkpoint-NEW.tar.gz
rtk proxy python3 scripts/tailcache12_dataset.py --primary native-final-campaign-NEW --robustness native-final-robustness-NEW --output /absolute/path/outside/build/task12-dataset-NEW
```

Archive only while collection is stopped. Both tools refuse existing outputs, use the exclusive benchmark lock and bounded1MiB hashing, and read back every archived member. The native checkpoint stores all available native evidence under evidence-archives; the final export includes all available report-tree files, sources, protocols, quiet/helper data and historical raw siblings once. Historical/rejected data is retained as context and excluded from primary/robustness statistics. Keep older external archives and hashes separately; do not clean build before preservation. Final export remains taskComplete=false until a separate researcher acceptance review verifies coverage, source/protocol hashes, uncertainty, RQ1/RQ2 claim limits and all rejection dispositions. Stop tailcache12-recovery.timer only after true task completion.
