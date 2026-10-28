"""Keep scheduled controller check-ins outside prospective benchmark blocks.

This optional launch schedule never changes measurement or host acceptance rules.
Waits happen before the block's host sampler starts and are retained separately.
"""
import math
import os
import time


def launch_delay(now, anchor, period, before, after):
    values = (now, anchor, period, before, after)
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Controller schedule requires finite values")
    if period <= 0 or before < 0 or after < 0 or before + after >= period:
        raise ValueError("Controller guard windows must leave a positive launch interval")
    phase = (now - anchor) % period
    if phase < after:
        return after - phase
    if phase >= period - before:
        return period - phase + after
    return 0.0


def wait_for_launch(properties, environ=None):
    environ = os.environ if environ is None else environ
    anchor = environ.get("TAILCACHE_CONTROLLER_ANCHOR_UNIX_SECONDS")
    if anchor is None:
        return None
    anchor = float(anchor)
    period = float(environ.get("TAILCACHE_CONTROLLER_PERIOD_SECONDS", "900"))
    # Budget startup/cleanup as well as every fork in a single Gradle invocation.
    # These are scheduling estimates only; actual host/worker windows still gate.
    backends = len(str(properties.get("Backends", properties.get("Backend", "one"))).split(","))
    payloads = len(str(properties.get("Payloads", properties.get("Payload", "one"))).split(","))
    forks = int(properties.get("Forks", 1)) * backends * payloads
    duration = forks * (int(properties.get("Warmups", 60)) + int(properties.get("Measurements", 8))) + 90
    before = max(float(environ.get("TAILCACHE_CONTROLLER_BEFORE_SECONDS", "180")), duration)
    after = float(environ.get("TAILCACHE_CONTROLLER_AFTER_SECONDS", "120"))
    started = time.monotonic()
    delay = launch_delay(time.time(), anchor, period, before, after)
    if delay:
        print(f"controller: waiting {delay:.1f}s outside benchmark block", flush=True)
    while delay:
        time.sleep(min(1.0, delay))
        delay = launch_delay(time.time(), anchor, period, before, after)
    return dict(anchorUnixSeconds=anchor, periodSeconds=period,
                beforeSeconds=before, afterSeconds=after,
                estimatedInvocationSeconds=duration,
                waitedSeconds=time.monotonic() - started,
                launchUnixSeconds=time.time(),
                limits="Prospective scheduling only; unchanged per-block host gates decide acceptance.")
