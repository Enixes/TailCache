"""Prospective, bounded native CPU/power replacements; never endpoint selection."""
import csv
import datetime
import hashlib
import json
import pathlib
import time

VERSION = "tailcache12-native-host-retry-v1"
ELIGIBLE = ("Native CPU outside benchmark scope exceeded 10% upper bound",
            "externalPower changed during block", "external power is disconnected")


def declare_policy(retries, budget=8, stage="calibrate"):
    if type(retries) is not int or not 0 <= retries <= 2:
        raise ValueError("Native stages allow zero to two extra candidates per slot")
    if retries == 0:
        return None
    if stage not in ("calibrate", "pilot", "campaign", "robustness", "observer-floor"):
        raise ValueError("Native replacement policy does not apply to this stage")
    if type(budget) is not int or not 1 <= budget <= 8:
        raise ValueError("Native stages allow at most eight extra candidates in total")
    return dict(version=VERSION, stage=stage, maxRetriesPerSlot=retries, maxExtraJvms=budget,
        eligibleHostReasons=list(ELIGIBLE), nativeObserverVersion=2,
        hostRuleVersion="tailcache12-host-v4-native-cpu", quietSeconds=120,
        quietTimeoutSeconds=300, maxQuietToBlockSeconds=360,
        selection="first-quality-pass", latencyEndpointsUsed=False)


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def initial_quiet_reference(path, manifest, policy, current_host):
    """Freeze a fresh initial prerequisite before a new calibration's first JVM."""
    import tailcache12 as evidence
    with (path/"host.csv").open(newline="") as stream:
        samples=[evidence.decode_host_row(r) for r in csv.DictReader(stream)]
    target=evidence.native_host.environment_declaration(samples[-1])
    checked=verify_quiet(path,dict(sourceSha256=manifest["sourceSha256"],nativeHostRetryPolicy=policy,
                                  nativeEnvironmentDeclaration=target))
    if (not checked["quietPass"] or evidence.native_host.normalized_environment(target) !=
            evidence.native_host.normalized_environment(evidence.native_host.environment_declaration(current_host))):
        raise ValueError("Initial quiet prerequisite rejected or native target environment changed")
    age=(time.monotonic_ns()-checked["lastMonotonicNs"])/1e9
    if not 0 <= age <= policy["maxQuietToBlockSeconds"]:
        raise ValueError("Initial quiet prerequisite expired before declaration")
    result=dict(version=1,attempt=path.name,maxQuietToFirstBlockSeconds=360,
                sha256={name:sha(path/name) for name in ("quiet.json","host.csv")})
    if (path/'host-preparation.json').exists():
        result['hostPreparationSha256']=sha(path/'host-preparation.json')
    return result


def verify_initial_quiet(attempt, manifest, rows=(), before_launch=False):
    import tailcache12 as evidence
    ref=manifest.get("initialQuietRef")
    if ref is None:
        return None
    if (ref.get("version") != 1 or ref.get("maxQuietToFirstBlockSeconds") != 360
            or not evidence.re.fullmatch(r"[A-Za-z0-9._-]+",ref.get("attempt",""))
            or set(ref["sha256"]) != {"quiet.json","host.csv"}):
        raise ValueError("Invalid initial quiet declaration")
    path=attempt.parent/ref["attempt"]
    requires_empty_swap=False
    if any(sha(path/name)!=digest for name,digest in ref["sha256"].items()):
        raise ValueError("Changed initial quiet prerequisite")
    if 'hostPreparationSha256' in ref:
        prep=path/'host-preparation.json'
        if sha(prep)!=ref['hostPreparationSha256']:
            raise ValueError('Changed host cache preparation evidence')
        cache=json.loads(prep.read_text())
        if (cache.get('version') not in (1,2,3,4) or cache.get('sourceSha256')!=manifest['sourceSha256']
                or cache.get('method')!='fsync-and-posix-fadvise-dontneed-task-files'
                or cache.get('minimumFreeKiB')!=3*1024**2 or cache.get('errors')
                or cache.get('preparationPass') is not True
                or cache['after']['MemFreeKiB']<cache['minimumFreeKiB']):
            raise ValueError('Invalid task-local host preparation')
        if cache['version'] in (3,4) and cache.get('roots')!=['build','evidence-archives','.gradle']:
            raise ValueError('Private build-cache preparation roots differ from the declaration')
        if cache['version']==4:
            from tailcache12_calibration_start import verify_cache_inventory
            verify_cache_inventory(attempt.parent,cache)
        if cache['version'] in (2,3,4) and (cache.get('requiresEmptySwap') is not True
                or cache['after'].get('SwapUsedKiB')!=0):
            raise ValueError('New benchmark preparation requires zero residual swap')
        requires_empty_swap=cache['version'] in (2,3,4)
        if cache.get('toolCachePreparationSha256'):
            from tailcache12_tool_cache import verify as verify_tool_cache
            tool=path/'tool-cache-preparation.json'
            if sha(tool)!=cache['toolCachePreparationSha256']:
                raise ValueError('Changed task-tooling cache preparation evidence')
            verify_tool_cache(json.loads(tool.read_text()),manifest['sourceSha256'])
        if cache.get('swapPreparationSha256'):
            from tailcache12_swap_prepare import configuration
            reset=path/'swap-preparation.json'
            if sha(reset)!=cache['swapPreparationSha256']:
                raise ValueError('Changed residual swap recovery evidence')
            record=json.loads(reset.read_text())
            if (not record.get('preparationPass') or not record.get('configurationRestored')
                    or record.get('measurementSourceSha256')!=manifest['measurementSourceSha256']
                    or configuration(record['before'])!=configuration(record['after'])
                    or record['after']['memory']['SwapUsedKiB']!=0):
                raise ValueError('Residual-page recovery did not preserve the declared swap policy')
    with (path/"host.csv").open(newline="") as stream:
        samples=[evidence.decode_host_row(r) for r in csv.DictReader(stream)]
    if requires_empty_swap:
        if any(r.get('swapUsedKiB')!=0 for r in samples):
            raise ValueError('Residual swap present in new initial quiet evidence')
        if before_launch and evidence.host_snapshot().get('swapUsedKiB')!=0:
            raise ValueError('Residual swap reappeared before first benchmark launch')
        if rows:
            with (attempt/rows[0]['label']/'host.csv').open(newline='') as stream:
                if evidence.decode_host_row(next(csv.DictReader(stream))).get('swapUsedKiB')!=0:
                    raise ValueError('Residual swap present at the first benchmark block')
    target=evidence.native_host.environment_declaration(samples[-1])
    checked=verify_quiet(path,dict(manifest,nativeEnvironmentDeclaration=target))
    if (not checked["quietPass"] or evidence.native_host.normalized_environment(target) !=
            evidence.native_host.normalized_environment(manifest["nativeEnvironmentDeclaration"])):
        raise ValueError("Initial quiet prerequisite environment differs from the frozen calibration")
    if rows or before_launch:
        first=rows[0]["hostWindowStartNs"] if rows else time.monotonic_ns()
        if not 0 <= (first-checked["lastMonotonicNs"])/1e9 <= ref["maxQuietToFirstBlockSeconds"]:
            raise ValueError("Initial quiet prerequisite expired or overlaps the first block")
    return checked


def label_for(slot, ordinal):
    return slot if ordinal == 1 else f"{slot}-n{ordinal}"


def initialize(attempt, manifest, grid, policy, initial_host):
    if policy is None:
        return
    import tailcache12 as evidence
    from tailcache12_provenance import measurement_source_hash
    if (manifest["invocations"] or manifest.get("calibrationHostCpuRetryPolicy")
            or initial_host.get("nativeObserverVersion") != 2 or initial_host.get("nativeScopeQualified") != 1
            or manifest["hostRuleVersion"] != policy["hostRuleVersion"]):
        raise ValueError("Native retry declaration requires a new native-v4 scoped attempt")
    manifest.update(nativeRetrySchema=VERSION, nativeHostRetryPolicy=policy,
        nativeLogicalSlots=[dict(label=label, properties=props) for label, props in grid],
        nativeRetryPreflights={}, measurementSourceSha256=measurement_source_hash(evidence.ROOT),
        nativeEnvironmentVersion=1,
        nativeEnvironmentDeclaration=evidence.native_host.environment_declaration(initial_host))
    declaration = {key: manifest[key] for key in ("nativeRetrySchema", "nativeHostRetryPolicy",
        "nativeLogicalSlots", "measurementSourceSha256", "sourceSha256", "nativeEnvironmentDeclaration")}
    declaration["declaredUtc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if "initialQuietRef" in manifest:
        declaration["initialQuietRef"]=manifest["initialQuietRef"]
    if "qualificationRefs" in manifest:
        declaration["qualificationRefs"]=manifest["qualificationRefs"]
    evidence.save(attempt / "native-retry-policy.json", declaration)
    manifest["nativeRetryPolicySha256"] = sha(attempt / "native-retry-policy.json")


def verify_declaration(attempt, manifest, canonical=None):
    policy = manifest.get("nativeHostRetryPolicy")
    if not policy:
        if manifest.get("nativeRetrySchema"):
            raise ValueError("Missing declared native replacement policy")
        return None
    if (manifest.get("nativeRetrySchema") != VERSION
            or policy != declare_policy(policy.get("maxRetriesPerSlot"), policy.get("maxExtraJvms"), manifest["stage"])
            or manifest["hostRuleVersion"] != policy["hostRuleVersion"]
            or sha(attempt / "native-retry-policy.json") != manifest["nativeRetryPolicySha256"]):
        raise ValueError("Changed native replacement policy")
    declaration = json.loads((attempt / "native-retry-policy.json").read_text())
    if declaration.get("initialQuietRef") != manifest.get("initialQuietRef"):
        raise ValueError("Changed frozen initial quiet prerequisite reference")
    if declaration.get("qualificationRefs") != manifest.get("qualificationRefs"):
        raise ValueError("Changed frozen qualification bindings")
    for key in ("nativeRetrySchema", "nativeHostRetryPolicy", "nativeLogicalSlots",
                "measurementSourceSha256", "sourceSha256", "nativeEnvironmentDeclaration"):
        if declaration[key] != manifest[key]:
            raise ValueError("Native declaration disagrees with manifest")
    if canonical is not None and manifest["nativeLogicalSlots"] != [dict(label=k, properties=v) for k, v in canonical]:
        raise ValueError("Native logical schedule or controls changed")
    slots = manifest["nativeLogicalSlots"]
    if (not slots or len({s["label"] for s in slots}) != len(slots)
            or [s["label"] for s in slots] != manifest["expectedBlocks"]):
        raise ValueError("Invalid native logical slots")
    return policy


def select(manifest, rows):
    policy, slots = manifest["nativeHostRetryPolicy"], manifest["nativeLogicalSlots"]
    if policy != declare_policy(policy.get("maxRetriesPerSlot"), policy.get("maxExtraJvms"), manifest["stage"]):
        raise ValueError("Unknown native replacement policy")
    if (not slots or [s["label"] for s in slots] != manifest["expectedBlocks"]
            or len({s["label"] for s in slots}) != len(slots)):
        raise ValueError("Invalid native logical schedule")
    selected, excluded, statuses, errors = [], [], {}, []
    index, ordinal, extras = 0, 1, 0
    for row in rows:
        if errors or index >= len(slots):
            raise ValueError("Candidate after terminal failure or completed native dataset")
        slot = slots[index]
        if row["label"] != label_for(slot["label"], ordinal) or row["inputs"] != slot["properties"]:
            raise ValueError("Native candidate order or frozen inputs changed")
        if ordinal > 1:
            extras += 1
            if extras > policy["maxExtraJvms"]:
                raise ValueError("Native total retry budget exceeded")
        reasons = list(dict.fromkeys(row["rejectionReasons"] + row.get("hostRejectionReasons", [])))
        observed = row.get("nativeObserverVersions") == [2]
        passed = not reasons and row.get("hostPass") is True and observed
        eligible = (observed and row.get("hostPass") is False and bool(reasons)
                    and set(reasons).issubset(policy["eligibleHostReasons"]))
        statuses[row["label"]] = dict(slotLabel=slot["label"], ordinal=ordinal,
            selectedForCalibration=passed, selectedForAnalysis=passed,
            outcome="pass" if passed else "retryable-native-host" if eligible else "fatal")
        if passed:
            selected.append(row["label"])
            index, ordinal = index+1, 1
        else:
            excluded.append(row["label"])
            if not eligible:
                errors.extend(row["label"] + ": " + reason for reason in reasons or ["Invalid native host acceptance evidence"])
            elif ordinal >= policy["maxRetriesPerSlot"]+1:
                errors.append(slot["label"] + ": native per-slot retry budget exhausted")
            elif extras >= policy["maxExtraJvms"]:
                errors.append("Native total retry budget exhausted")
            else:
                ordinal += 1
    candidate = None
    if not errors and index < len(slots):
        slot = slots[index]
        candidate = dict(label=label_for(slot["label"], ordinal), slotLabel=slot["label"], ordinal=ordinal,
                         properties=slot["properties"], requiresQuietPreflight=ordinal > 1)
    return dict(selectedLabels=selected, excludedLabels=excluded, attemptStatuses=statuses,
        missingSlots=[s["label"] for s in slots[index:]], complete=index == len(slots) and not errors,
        terminalRejectionReasons=errors, nextCandidate=candidate, extraJvms=extras)


def verify_quiet(path, manifest):
    import tailcache12 as evidence
    policy = manifest["nativeHostRetryPolicy"]
    result = json.loads((path / "quiet.json").read_text())
    if (result.get("stage") != "quiet-preflight" or result.get("sourceSha256") != manifest["sourceSha256"]
            or result.get("hostRuleVersion") != policy["hostRuleVersion"]
            or result.get("requiredQuietSeconds") != policy["quietSeconds"]
            or result.get("timeoutSeconds") != policy["quietTimeoutSeconds"]):
        raise ValueError("Native quiet prerequisite source/rules changed")
    with (path / "host.csv").open(newline="") as stream:
        rows = [evidence.decode_host_row(r) for r in csv.DictReader(stream)]
    if len(rows) != result["sampleCount"] or len(rows) < 2:
        raise ValueError("Missing native quiet samples")
    quiet, passed, pass_index = [], False, None
    for index, row in enumerate(rows):
        if quiet and row["monotonicNs"] - quiet[-1]["monotonicNs"] > 5e9:
            quiet = []
        if index and row["monotonicNs"] <= rows[index-1]["monotonicNs"]:
            raise ValueError("Nonadvancing native quiet clock")
        quiet.append(row)
        if len(quiet) >= 2:
            reasons, _ = evidence.host_gate(quiet, native_required=True, native_version=2)
            if reasons:
                quiet = [row]
            elif quiet[-1]["monotonicNs"] - quiet[0]["monotonicNs"] >= policy["quietSeconds"]*1e9:
                if evidence.native_host.environment_reasons(quiet, manifest["nativeEnvironmentDeclaration"]):
                    raise ValueError("Native quiet target environment differs from the declaration")
                passed, pass_index = True, index
                break
    span = (rows[-1]["monotonicNs"] - rows[0]["monotonicNs"])/1e9
    if (passed != result.get("quietPass") or (passed and pass_index != len(rows)-1)
            or not span <= result["elapsedSeconds"]+1 <= policy["quietTimeoutSeconds"]+6):
        raise ValueError("Native quiet summary disagrees with raw intervals")
    return dict(quietPass=passed and result.get("monitorFailure") is None,
                firstMonotonicNs=rows[0]["monotonicNs"], lastMonotonicNs=rows[-1]["monotonicNs"])


def verify_preflights(attempt, manifest, rows, state):
    table = manifest["nativeRetryPreflights"]
    previous, checks, errors = None, {}, []
    permitted = {label_for(s["label"], ordinal) for s in manifest["nativeLogicalSlots"]
                 for ordinal in range(2, manifest["nativeHostRetryPolicy"]["maxRetriesPerSlot"]+2)}
    used = {r["label"] for r in rows}
    pending = state["nextCandidate"]
    if pending:
        used.add(pending["label"])
    for label, record in table.items():
        if label not in permitted or label not in used or set(record) != {"quiet.json", "host.csv"}:
            raise ValueError("Unexpected native quiet prerequisite")
        path = attempt / "native-retry-preflights" / label
        if any(sha(path/name) != digest for name, digest in record.items()):
            raise ValueError("Changed native quiet prerequisite")
        checks[label] = verify_quiet(path, manifest)
        if not checks[label]["quietPass"]:
            errors.append(label + ": native quiet preflight rejected")
    for row in rows:
        status = state["attemptStatuses"][row["label"]]
        if status["ordinal"] > 1:
            checked = checks.get(row["label"])
            if not checked or not checked["quietPass"] or previous is None:
                raise ValueError("Native replacement lacks passing raw quiet evidence")
            if checked["firstMonotonicNs"] < previous["hostWindowEndNs"]:
                raise ValueError("Native replacement preparation overlaps preceding JVM")
            age = (row["hostWindowStartNs"] - checked["lastMonotonicNs"])/1e9
            if not 0 <= age <= manifest["nativeHostRetryPolicy"]["maxQuietToBlockSeconds"]:
                raise ValueError("Native replacement preparation overlaps or expired")
        previous = row
    return checks, errors


def run_grid(attempt, manifest, replay, task_for):
    import tailcache12 as evidence
    from tailcache12_quiet import run_preflight
    try:
        while True:
            result = replay(attempt)
            state = result["nativeHostRetryState"]
            candidate = state["nextCandidate"]
            if not candidate or result.get("nativeRetryPreflightRejectionReasons") or manifest.get("terminalDriverFailure"):
                return result
            label = candidate["label"]
            if not manifest["invocations"]:
                verify_initial_quiet(attempt,manifest,before_launch=True)
            if candidate["requiresQuietPreflight"]:
                path = attempt / "native-retry-preflights" / label
                if label not in manifest["nativeRetryPreflights"]:
                    policy = manifest["nativeHostRetryPolicy"]
                    run_preflight(path, policy["quietSeconds"], policy["quietTimeoutSeconds"])
                    manifest["nativeRetryPreflights"][label] = {name: sha(path/name) for name in ("quiet.json", "host.csv")}
                    evidence.save(attempt / "manifest.json", manifest)
                checked = verify_quiet(path, manifest)
                if not checked["quietPass"]:
                    return replay(attempt)
                age = (time.monotonic_ns() - checked["lastMonotonicNs"])/1e9
                if not 0 <= age <= manifest["nativeHostRetryPolicy"]["maxQuietToBlockSeconds"]:
                    raise ValueError("Native replacement quiet prerequisite expired")
            evidence.invoke(attempt, manifest, label, task_for(candidate["properties"]), candidate["properties"])
    except Exception as error:
        manifest["terminalDriverFailure"] = dict(reason=f"{type(error).__name__}: {error}",
                                                 utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        evidence.save(attempt / "manifest.json", manifest)
        raise
