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

1. Create a DecisionRecord
2. Acquire a BudgetContext
3. Perform the action
4. Validate the result
5. Complete the decision (schema-adaptive)
6. Log via DecisionJournal

It does NOT:

- Modify Memory Guardian
- Modify session JSONL files
- Require Agent Guardian
- Require Token Guardian

---

## Compatibility

Executive Guardian adapts to multiple Executive Layer schema versions:

- Supports positional `DecisionRecord.complete(...)`
- Supports other complete signatures via adapters
- Adapts to BudgetContext constructor variations
- Does not rely on Validator constants

In standalone mode (Executive Layer missing), it falls back to lightweight logging.

---

## Enable / Disable

```bash
export EXEC_HOOK_ENABLED=1 # enable
export EXEC_HOOK_ENABLED=0 # disable (default)
```

## Allowlist

Actions that are routed via the membrane:

- command_exec
- file_write
- file_delete
- json_write
- http_request

Modify HIGH_RISK_ALLOWLIST in guardian.py to adjust this list.

---

## Example

```python
from executive_guardian import wrap_command_exec

wrap_command_exec("task_123", "main", "echo HELLO")
```

This produces a completed decision in:
`workspace/executive/decisions/YYYY-MM-DD.jsonl`

---

## Operational Behavior

Executive Guardian:

- Creates decision records
- Completes decisions
- Logs observed outcomes
- Stamps validator metadata
- Sets post-confidence

Failures are logged; pending only occurs if execution aborts before validation.

---

## Rollout Plan

1. Enable behind feature flag
2. Wrap high-risk tools only
3. Observe decision log stability
4. Integrate into the agent's global tool router
