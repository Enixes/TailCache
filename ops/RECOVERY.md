# TailCache chat recovery

Requested by the user on 5 November 2026 for chat `01a1032c-87df-72d1-93cb-cd6f076451a0`.

The CLI exposes no automation scheduling tool in this session. A local user systemd timer therefore checks the existing Codex daemon every 15 minutes. It queues a continuation in this same chat only when:

- the selected research follow-up is unfinished and recovery is not paused;
- no TailCache benchmark driver/JVM is running;
- the chat is inactive and its latest turn failed/interrupted specifically for `usageLimitExceeded` or `rateLimitExceeded`;
- the backend explicitly reports ordinary usage allowed and no active Codex spend/quota block;
- this failure has not already received a continuation.

It never infers permission from a reset timestamp or percentage, changes model/permissions, consumes reset credits, launches a second benchmark or wakes an intentionally completed/interrupted non-usage turn. Local checks make no model calls. Only state changes are logged; no chat history, account identifiers, balances or credentials are stored. A file lock and failed-turn ID suppress duplicate recovery messages. The historical Task 12 status remains complete. On 17 November the user renewed recovery for the service/RQ follow-up. The installed service now selects `docs/TAILCACHE_SERVICE_STATUS.json` with `--status-file`; it disables itself when that file has `taskComplete=true`. It never resets the historical task completion.

The host, user systemd manager and local Codex daemon must remain running. This timer does not wake a powered-off/suspended machine, bypass limits, or guarantee model availability. CLI queue/resume warnings require inspection of the local recovery state/journal.

Files: `tailcache12-recovery.service`, `tailcache12-recovery.timer`, `tailcache12_recovery.py`; state is under ignored `build/reports/tailcache12/recovery/`.

Read-only check (does not queue a turn):

```sh
rtk proxy python3 /home/y/TailCache/ops/tailcache12_recovery.py --thread 01a1032c-87df-72d1-93cb-cd6f076451a0 --socket /home/y/.codex/app-server-control/app-server-control.sock --status-file docs/TAILCACHE_SERVICE_STATUS.json --inspect
```

Stop recovery:

```sh
rtk proxy systemctl --user disable --now tailcache12-recovery.timer
```

The recovery code is outside the measurement source tree and does not alter the frozen benchmark sources. Its protocol follows the installed CLI schema (live permission/socket check repeated on 17 November with CLI 0.169.0) and the [official App Server documentation](https://learn.chatgpt.com/docs/app-server).
