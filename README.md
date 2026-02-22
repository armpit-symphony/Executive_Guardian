# Executive Guardian v1.0

Execution Discipline Layer for OpenClaw

Executive Guardian is a thin **execution membrane** that wraps high-risk side-effect actions with:

- **Decision logging** (per-task + per-lane, via `DecisionJournal`)
- **Budget locks** (per-task + per-lane, via `BudgetContext`)
- **Validation tiers** (SUCCESS / FAIL tiers, via `Validator`)
- **Confidence calibration** (pre-action confidence recorded; calibration handled by Executive Layer)

It is designed to be **non-invasive** — it does not write to Memory Guardian stores or alter session logs.

---

## What It Does

For allowlisted action types (high-risk tools), when enabled, Executive Guardian:

1. Creates a decision record (task_id, action_type, expected_outcome, confidence_pre, metadata)
2. Acquires a budget lock (task + lane)
3. Executes the action
4. Validates the outcome (SUCCESS / FAIL + validator metadata)
5. Logs the decision artifact

For non-allowlisted actions, or when disabled, it simply runs the original action.

---

## Install

This module lives at: `/home/sparky/.openclaw/workspace/executive_guardian/`

Files:
- `guardian.py` — core membrane + wrappers
- `__init__.py` — exports

### Integration

Executive Guardian integrates with **Executive Layer** when available:

- **With Executive Layer:** `/home/sparky/.openclaw/workspace/executive/`
  - Logs to `executive/decisions/`
  - Uses real BudgetContext, DecisionJournal, Validator

- **Standalone (fallback):** No dependency required
  - Logs to `~/.openclaw/logs/guardian-journal.jsonl`
  - Uses stub implementations

---

## Enable / Disable

Executive Guardian is gated by an environment flag.

### Enable
```bash
export EXEC_HOOK_ENABLED=1
```

### Disable (default)
```bash
export EXEC_HOOK_ENABLED=0
```

With `EXEC_HOOK_ENABLED=0`, no behavior changes occur.

---

## High-Risk Allowlist

Only allowlisted action types are routed through the membrane:

- `file_write`
- `file_delete`
- `command_exec`
- `json_write`

Note: `http_request` was removed from allowlist until `wrap_http_request` is fully integrated.

You can expand or reduce this list in:
`executive_guardian/guardian.py` → `HIGH_RISK_ALLOWLIST = {...}`

---

## Usage

### 1) Generic membrane

Use this when you already have a perform_fn and a validate_fn.

```python
from executive_guardian import exec_with_guard

result = exec_with_guard(
    task_id="task_123",
    lane="main",
    action_type="file_write",
    expected_outcome="File created at /tmp/test.txt",
    confidence_pre=0.75,
    perform_fn=lambda: write("/tmp/test.txt", "content"),
    validate_fn=lambda r: (ValidationTier.SUCCESS, {"exists": True}),
    metadata={"path": "/tmp/test.txt"},
)
```

### 2) Pre-built wrappers

Use wrappers for common high-risk operations.

**file_write**
```python
from executive_guardian import wrap_file_write

wrap_file_write(
    task_id="task_123",
    lane="main",
    file_path="/tmp/test.txt",
    content="Hello World",
    write_fn=lambda p, c: write(p, c),
)
```

**file_delete**
```python
from executive_guardian import wrap_file_delete

wrap_file_delete(
    task_id="task_123",
    lane="main",
    file_path="/tmp/test.txt",
    delete_fn=lambda p: delete(p),
)
```

**command_exec**
```python
from executive_guardian import wrap_command_exec

res = wrap_command_exec(
    task_id="task_123",
    lane="main",
    command="ls -la",
)
```

**json_write**
```python
from executive_guardian import wrap_json_write

wrap_json_write(
    task_id="task_123",
    lane="main",
    file_path="/tmp/config.json",
    data={"a": 1, "b": True},
    write_fn=lambda p, txt: write(p, txt),
)
```

---

## Decision Artifacts (Where Logs Go)

Executive Guardian logs into the Executive Layer storage layout:

- Hot decisions (TTL-managed): `executive/decisions/`
- Archive: `executive/archive/`
- Locks: `executive/locks/`
- Validations: `executive/validations/`
- Checkpoints: `executive/checkpoints/` (policy-based)

---

## Design Notes

### Non-invasive by default
- Disabled unless `EXEC_HOOK_ENABLED=1`
- Allowlist-based routing
- Does not change tool logic; only wraps execution

### Memory Guardian compatibility
- Does not write to Memory Guardian directories
- Does not mutate session JSONL format
- Produces decision artifacts in Executive Layer folders only

---

## Known Limitations

- `http_request` wrapper is not included by default in v1.0 (recommended to add if your agent performs external calls frequently).
- Validation is intentionally lightweight. For complex outcomes, create custom validate_fn rules.

---

## Roadmap (Safe Next Steps)

1. Add `wrap_http_request` with response status validation
2. Promote to global router behind allowlist (still gated by EXEC_HOOK_ENABLED)
3. Add ACCEPTABLE tier routing for "best-effort" validations (optional)

---

## Quick Smoke Test

```bash
export EXEC_HOOK_ENABLED=1
python -c "from executive_guardian import wrap_command_exec; wrap_command_exec('task_smoke','main','echo EG_OK')"
ls -la /home/sparky/.openclaw/workspace/executive/decisions | tail -n 5
```

If you see a new decision file, Executive Guardian is working.
