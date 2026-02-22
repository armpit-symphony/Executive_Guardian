# Executive Guardian v1.0

Execution Discipline Layer for OpenClaw.

Executive Guardian is a thin execution membrane that wraps high-risk side-effect actions with:

- **Decision logging** (via Executive Layer when available)
- **Budget locks** (via Executive Layer when available)
- **Validation tiers** (SUCCESS / FAIL; ACCEPTABLE supported if your Validator supports it)
- **Confidence calibration** (pre-action confidence recorded; Executive Layer can calibrate)

It is designed to be Memory Guardian compatible: it does not write to Memory Guardian stores or alter session logs.

---

## Modes

### With Executive Layer installed

If Executive Layer is importable (e.g. via PYTHONPATH), Executive Guardian uses the real:

- DecisionRecord
- DecisionJournal
- BudgetContext
- Validator

Logging goes to Executive Layer storage (e.g. `executive/decisions/`), as defined by that layer.

### Standalone fallback

If Executive Layer is not available, Executive Guardian falls back to stub implementations and logs to:

- `~/.openclaw/logs/guardian-journal.jsonl`

---

## Enable / Disable

Gated by environment flag:

```bash
export EXEC_HOOK_ENABLED=1  # enable
export EXEC_HOOK_ENABLED=0  # disable (default)
```

---

## High-Risk Allowlist

Allowlisted action types:

- file_write
- file_delete
- command_exec
- json_write
- http_request

---

## Usage

### Status / Smoke test

```bash
PYTHONPATH=/home/sparky/.openclaw/workspace:. python3 -c "from executive_guardian import get_status; print(get_status())"
```

### Generic membrane

```python
from executive_guardian import exec_with_guard

result = exec_with_guard(
    task_id="task_123",
    lane="main",
    action_type="file_write",
    expected_outcome="File created at /tmp/test.txt",
    confidence_pre=0.75,
    perform_fn=lambda: write("/tmp/test.txt", "content"),
    validate_fn=lambda r: ("success", {"exists": True}),
)
```

### Wrappers

```python
from executive_guardian import wrap_command_exec

wrap_command_exec("task_smoke", "main", "echo EG_OK")
```

---

## Notes

- Executive Guardian does not install Agent Guardian.
- Executive Guardian does not depend on Token Guardian.
- It can run today, even if those layers are missing.
