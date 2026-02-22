# Executive Guardian v1.0

Execution Discipline Layer for OpenClaw.

Executive Guardian wraps high-risk side-effect actions with:

- Budget enforcement (via Executive Layer when available)
- Structured decision logging
- Validation tiers
- Confidence post-calibration
- Schema-adaptive completion logic

This layer is non-invasive and safe to enable behind a feature flag.

---

## Architecture

Executive Guardian acts as a membrane around execution:

1. Create DecisionRecord
2. Acquire BudgetContext
3. Perform action
4. Validate result
5. Complete decision (schema-adaptive)
6. Log via DecisionJournal

It does NOT:

- Modify Memory Guardian
- Modify session JSONL files
- Require Agent Guardian
- Require Token Guardian

---

## Compatibility

Designed to adapt to multiple Executive Layer schema versions:

- Supports positional `DecisionRecord.complete(...)`
- Supports keyword-based complete() variants
- Supports BudgetContext constructor variations
- Exposes SUCCESS/FAIL constants

If Executive Layer is unavailable, falls back to lightweight standalone logging.

---

## Enable / Disable

```bash
export EXEC_HOOK_ENABLED=1 # enable
export EXEC_HOOK_ENABLED=0 # disable (default)
```

---

## Allowlist

Only these action types are routed through the membrane:

- command_exec
- file_write
- file_delete
- json_write
- http_request

Modify HIGH_RISK_ALLOWLIST in guardian.py to adjust scope.

---

## Example

```python
from executive_guardian import wrap_command_exec

wrap_command_exec("task_123", "main", "echo HELLO")
```

Creates a fully completed decision entry under:
`workspace/executive/decisions/YYYY-MM-DD.jsonl`

---

## Operational Behavior

Executive Guardian:

- Creates decision records
- Completes decisions (no "pending" left behind)
- Logs observed outcomes
- Stamps validator metadata
- Updates confidence.post
- Logs failures even if validation errors occur

Pending decisions only appear if an exception interrupts execution before validation.

---

## Recommended Rollout

1. Enable behind feature flag
2. Wrap high-risk tools only
3. Observe decision log stability
4. Promote to router-level integration

---

Executive Guardian provides execution discipline without architectural disruption.
