#!/usr/bin/env python3
"""Resume this user's existing TailCache chat only after an actual usage-limit failure.

No model call is made by polling. The backend must explicitly allow ordinary
usage; percentages/reset timestamps are not treated as permission. A running
benchmark or active chat always suppresses a wakeup.
"""
import argparse
import base64
import fcntl
import hashlib
import json
import os
import pathlib
import socket
import struct
import subprocess
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "build/reports/tailcache12/recovery"
PROMPT = (
    "Automatic recovery requested by the user: continue unfinished TailCache Task 12 in /home/y/TailCache. "
    "Read docs/TAILCACHE_12_STATUS.json, docs/TAILCACHE_12_FINISH_PLAN.md and the researcher reviews. "
    "The previous turn hit a usage limit and ordinary usage is now allowed. Inspect live processes and retained "
    "manifests first; never duplicate a benchmark, overwrite evidence, pool rejected forks, or bypass gates. "
    "Finish implementation, source-matched qualification, floors/coherence, calibration, pilot, frozen campaign, "
    "robustness and final dataset/review. A launched or partial job is not completion. Preserve historical evidence. "
    "Stay quiet while existing work runs; notify only meaningful failure, completion or needed user action. "
    "Stop tailcache12-recovery.timer when taskComplete=true."
)


class LocalRpc:
    """Small dependency-free WebSocket client for the local private Unix socket."""
    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        self.sock.connect(str(path))
        self.buffer = b""
        self.identifier = 0
        key = base64.b64encode(os.urandom(16)).decode()
        request = ("GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                   "Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: " + key + "\r\n\r\n")
        self.sock.sendall(request.encode())
        while b"\r\n\r\n" not in self.buffer:
            chunk = self.sock.recv(4096)
            if not chunk or len(self.buffer) > 16384:
                raise ConnectionError("Invalid local daemon WebSocket handshake")
            self.buffer += chunk
        headers, self.buffer = self.buffer.split(b"\r\n\r\n", 1)
        lines = headers.decode().split("\r\n")
        fields = dict(line.split(":", 1) for line in lines[1:] if ":" in line)
        fields = {k.lower(): v.strip() for k, v in fields.items()}
        expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        if " 101 " not in lines[0] or fields.get("sec-websocket-accept") != expected:
            raise ConnectionError("Local daemon refused WebSocket upgrade")
        self.request("initialize", dict(clientInfo=dict(name="tailcache-recovery", version="1"),
                                        capabilities=dict(experimentalApi=True)))
        self.send(dict(method="initialized", params={}))

    def close(self):
        self.sock.close()

    def read(self, count):
        while len(self.buffer) < count:
            chunk = self.sock.recv(max(4096, count-len(self.buffer)))
            if not chunk:
                raise ConnectionError("Local daemon disconnected")
            self.buffer += chunk
        value, self.buffer = self.buffer[:count], self.buffer[count:]
        return value

    def frame(self, opcode, payload):
        mask = os.urandom(4)
        count = len(payload)
        header = bytes((0x80 | opcode, 0x80 | count)) if count < 126 else (
            bytes((0x80 | opcode, 0x80 | 126)) + struct.pack("!H", count) if count <= 65535 else
            bytes((0x80 | opcode, 0x80 | 127)) + struct.pack("!Q", count))
        self.sock.sendall(header + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(payload)))

    def send(self, value):
        self.frame(1, json.dumps(value).encode())

    def receive(self):
        fragments = b""
        while True:
            first, second = self.read(2)
            if first & 0x70 or second & 0x80:
                raise ConnectionError("Unsupported local daemon WebSocket frame")
            opcode, length = first & 15, second & 127
            if length == 126:
                length = struct.unpack("!H", self.read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self.read(8))[0]
            if length > 4*1024**2 or len(fragments)+length > 4*1024**2:
                raise ConnectionError("Oversized local daemon response")
            payload = self.read(length)
            if opcode == 8:
                raise ConnectionError("Local daemon closed connection")
            if opcode == 9:
                self.frame(10, payload)
                continue
            if opcode == 10:
                continue
            if opcode not in (0, 1):
                raise ConnectionError("Unexpected local daemon frame type")
            fragments += payload
            if first & 0x80:
                return json.loads(fragments)

    def request(self, method, params):
        self.identifier += 1
        identifier = self.identifier
        self.send(dict(id=identifier, method=method, params=params))
        deadline = time.monotonic()+15
        while time.monotonic() < deadline:
            message = self.receive()
            if message.get("id") == identifier:
                if "error" in message:
                    # Store the method/error code, never account data or conversation text.
                    raise RuntimeError(f"Local RPC {method} failed: {message['error'].get('code')}")
                return message["result"]
        raise TimeoutError(method)


def benchmark_pids():
    drivers = {"tailcache12.py": {"validate", "pause", "jit"},
               "tailcache12_calibrate.py": {"probe", "calibrate"},
               "tailcache12_everyop_jit.py": {"run"}, "tailcache12_observer.py": {"floors"},
               "tailcache12_pilot.py": {"pilot"}, "tailcache12_campaign.py": {"run", "robustness"}}
    found = []
    for path in pathlib.Path("/proc").glob("[0-9]*"):
        try:
            args = [part.decode(errors="replace") for part in (path/"cmdline").read_bytes().split(b"\0") if part]
            if not args:
                continue
            if pathlib.Path(args[0]).name.startswith("python") and len(args) >= 3:
                name = pathlib.Path(args[1]).name
                if args[2] in drivers.get(name, set()) or name in {
                        "tailcache12_finish.py", "tailcache12_sequence.py", "tailcache12_preparation.py",
                        "tailcache12_quiet.py", "tailcache12_native_probe.py", "tailcache12_calibration_start.py",
                        "tailcache12_jit_events.py", "tailcache12_pilot_start.py",
                        "tailcache12_complete_qualification.py", "tailcache12_archive.py",
                        "tailcache12_swap_prepare.py", "tailcache12_campaign_start.py", "tailcache12_dataset.py", "tailcache12_sampling_probe.py", "tailcache12_profile_probe.py", "tailcache12_profile_sites.py", "tailcache12_common_observer_probe.py", "tailcache12_exploratory.py", "tailcache12_conditional.py", "tailcache12_conditional_completion.py"}:
                    found.append(int(path.name))
            elif pathlib.Path(args[0]).name == "java" and any(
                    "tailcache12." in arg or "io.github.enixes.tailcache" in arg for arg in args[1:]):
                found.append(int(path.name))
        except (OSError, ValueError):
            continue
    return found


def decision(task, thread, turn, limits, state, busy):
    if task.get("taskComplete") is True:
        return "complete"
    if task.get("recoveryPaused") is True:
        return "paused"
    if busy:
        return "benchmark_running"
    if thread.get("status", {}).get("type") == "active":
        return "thread_active"
    error = (turn.get("error") or {}).get("codexErrorInfo")
    code = error if isinstance(error, str) else next(iter(error), None) if isinstance(error, dict) else None
    if turn.get("status") not in ("failed", "interrupted") or code not in ("usageLimitExceeded", "rateLimitExceeded"):
        return "no_usage_interruption"
    if state.get("queuedForTurnId") == turn.get("id"):
        return "already_queued"
    if limits.get("ordinaryUsageAllowed") is not True:
        return "waiting_for_usage_permission"
    bucket = (limits.get("rateLimitsByLimitId") or {}).get("codex") or limits.get("rateLimits") or {}
    if bucket.get("spendControlReached") is True or bucket.get("rateLimitReachedType") is not None:
        return "waiting_for_usage_permission"
    return "wake"


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2)+"\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thread", required=True)
    parser.add_argument("--socket", required=True)
    parser.add_argument("--codex", default="/home/y/.local/bin/codex")
    parser.add_argument("--inspect", action="store_true", help="Read status without queuing a message")
    args = parser.parse_args()
    uuid.UUID(args.thread)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with (STATE_DIR/"watcher.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        state_path = STATE_DIR/"state.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        task = json.loads((ROOT/"docs/TAILCACHE_12_STATUS.json").read_text())
        busy = benchmark_pids()
        action, thread, turn, limits = "", {}, {}, {}
        if (ROOT/"ops/tailcache12-recovery.disabled").exists():
            action = "paused"
        elif task.get("taskComplete") is True:
            action = "complete"
        elif busy and not args.inspect:
            action = "benchmark_running"
        else:
            rpc = LocalRpc(args.socket)
            try:
                thread = rpc.request("thread/read", dict(threadId=args.thread, includeTurns=False))["thread"]
                if thread["id"] != args.thread or pathlib.Path(thread["cwd"]).resolve() != ROOT:
                    raise ValueError("Recovery target differs from the authorized chat/checkout")
                if thread["status"]["type"] == "active" and not args.inspect:
                    action = "thread_active"
                else:
                    turns = rpc.request("thread/turns/list", dict(threadId=args.thread, limit=1,
                        itemsView="notLoaded", sortDirection="desc"))["data"]
                    turn = turns[0] if turns else {}
                    preliminary = decision(task, thread, turn, {}, state, busy)
                    if preliminary == "waiting_for_usage_permission" or args.inspect:
                        limits = rpc.request("account/rateLimits/read", {})
                    action = decision(task, thread, turn, limits, state, busy)
            finally:
                rpc.close()
        if args.inspect:
            print(json.dumps(dict(action=action, threadId=args.thread, status=thread.get("status"),
                latestTurnId=turn.get("id"), latestTurnStatus=turn.get("status"),
                ordinaryUsageAllowed=limits.get("ordinaryUsageAllowed"), benchmarkPids=busy), indent=2))
            return 0
        if action == "wake":
            # Recheck immediately before mutation; one local watcher holds the lock.
            if benchmark_pids():
                action = "benchmark_running"
            else:
                result = subprocess.run([args.codex, "queue", "--thread", args.thread,
                    "--message", PROMPT, "--resume", "-C", str(ROOT)], capture_output=True, text=True, timeout=30)
                if result.returncode:
                    raise RuntimeError("Codex recovery queue command failed")
                state["queuedForTurnId"] = turn["id"]
                state["lastWakeAt"] = time.time()
                action = "queued_resume_warning" if "warning" in result.stderr.lower() else "resume_queued"
        if action == "complete":
            subprocess.run(["systemctl", "--user", "disable", "--now", "tailcache12-recovery.timer"],
                           capture_output=True, timeout=10)
        if state.get("action") != action:
            print("TailCache recovery: " + action)
        state.update(action=action, checkedAt=time.time(), threadId=args.thread)
        save(state_path, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
