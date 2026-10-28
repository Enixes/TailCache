"""Prospective, bounded host-CPU retries for exploratory calibration only.

Selection uses gate outcomes and declared slot order, never latency endpoints.
Legacy attempts without this policy retain their original rejection semantics.
"""
VERSION = "tailcache12-calibration-hostcpu-retry-v1"
CPU_REASON = "Windows CPU outside the guest exceeded 10% in settling/measurement interval"


def declare_policy(retries, budget=8):
    if type(retries) is not int or not 0 <= retries <= 2:
        raise ValueError("Allow zero to two extra JVMs per calibration slot")
    if retries == 0:
        return None
    if type(budget) is not int or not 1 <= budget <= 8:
        raise ValueError("Calibration permits at most eight extra JVMs in total")
    return dict(version=VERSION, scope="exploratory-calibration-only",
                maxRetriesPerSlot=retries, maxExtraJvms=budget,
                eligibleHostReason=CPU_REASON, requiredNativeMonitorVersion=5,
                quietSeconds=60, quietTimeoutSeconds=300, maxQuietToBlockSeconds=360,
                selection="first-quality-pass", schedule="same-slot-immediate-after-quiet",
                latencyEndpointsUsed=False, primaryCampaignPolicy=False)


def candidate_label(slot, ordinal):
    return f"{slot}-q{ordinal}"


def outcome(row):
    if row.get("nativeHostVersions") != [5]:
        return "fatal", ["calibration retry policy requires native observer v5 throughout the block"]
    reasons = row["rejectionReasons"]
    host = row["hostRejectionReasons"]
    if not reasons and not host and row["hostPass"] is True:
        return "pass", []
    if not reasons and host == [CPU_REASON] and row["hostPass"] is False:
        return "retryable-host-cpu", host
    return "fatal", reasons + host or ["inconsistent host acceptance evidence"]


def select(manifest, rows):
    """Replay the only permitted candidate sequence and first valid slot choice."""
    policy = manifest["calibrationHostCpuRetryPolicy"]
    if (manifest["stage"] != "calibrate"
            or policy != declare_policy(policy.get("maxRetriesPerSlot"), policy.get("maxExtraJvms"))):
        raise ValueError("Unknown or changed calibration-only retry policy")
    slots = manifest["logicalSlots"]
    if (not slots or [s["label"] for s in slots] != manifest["expectedBlocks"]
            or len({s["label"] for s in slots}) != len(slots)):
        raise ValueError("Missing, duplicated or changed logical calibration slots")
    selected, excluded, statuses, errors = [], [], {}, []
    slot_index, ordinal, extras = 0, 1, 0
    for row in rows:
        if errors or slot_index == len(slots):
            raise ValueError("Candidate appeared after acceptance completion or a terminal failure")
        slot = slots[slot_index]
        label = candidate_label(slot["label"], ordinal)
        if row["label"] != label or row["inputs"] != slot["properties"]:
            raise ValueError("Candidate order, ordinal or declared controls changed")
        if ordinal > 1:
            extras += 1
            if extras > policy["maxExtraJvms"]:
                raise ValueError("Candidate exceeds the declared total retry budget")
        status, reasons = outcome(row)
        statuses[label] = dict(slotLabel=slot["label"], ordinal=ordinal,
                               outcome=status, selectedForCalibration=status == "pass")
        if status == "pass":
            selected.append(label)
            slot_index += 1
            ordinal = 1
        else:
            excluded.append(label)
            if status == "fatal":
                errors.extend(f"{label}: {reason}" for reason in reasons)
            elif ordinal >= policy["maxRetriesPerSlot"] + 1:
                errors.append(f"{slot['label']}: per-slot host-CPU retry limit exhausted")
            elif extras >= policy["maxExtraJvms"]:
                errors.append("total calibration host-CPU retry budget exhausted")
            else:
                ordinal += 1
    next_candidate = None
    if not errors and slot_index < len(slots):
        slot = slots[slot_index]
        next_candidate = dict(label=candidate_label(slot["label"], ordinal),
                              slotLabel=slot["label"], slotIndex=slot_index, ordinal=ordinal,
                              properties=slot["properties"], requiresQuietPreflight=ordinal > 1)
    return dict(selectedLabels=selected, excludedLabels=excluded, attemptStatuses=statuses,
                completedLogicalSlots=len(selected), expectedLogicalSlots=len(slots), extraJvms=extras,
                missingSlots=[s["label"] for s in slots[slot_index:]],
                terminalRejectionReasons=errors, nextCandidate=next_candidate,
                complete=slot_index == len(slots) and not errors)
