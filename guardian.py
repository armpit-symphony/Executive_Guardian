"""
Executive Guardian v1.0
Execution membrane for OpenClaw.

- Uses REAL Executive Layer if importable (DecisionRecord/DecisionJournal/BudgetContext/Validator)
- Falls back to stubs for standalone mode
- Schema-adaptive: only passes kwargs supported by installed Executive Layer version
"""

from __future__ import annotations

import os
import json
import inspect
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

USING_EXECUTIVE_LAYER = False

# =========================================================
# Try REAL Executive Layer first; fallback to stubs
# =========================================================
try:
    from executive import DecisionRecord, DecisionJournal, BudgetContext, Validator  # type: ignore

    USING_EXECUTIVE_LAYER = True
except Exception:
    class Validator:
        SUCCESS = "success"
        FAIL = "fail"
        ACCEPTABLE = "acceptable"

    class DecisionRecord:
        def __init__(
            self,
            task_id: str,
            action_type: str,
            expected_outcome: str | None = None,
            confidence_pre: float | None = None,
            metadata: Dict[str, Any] | None = None,
            **_,
        ):
            self.task_id = task_id
            self.action_type = action_type
            self.expected_outcome = expected_outcome
            self.confidence_pre = confidence_pre
            self.metadata = metadata or {}
            self.timestamp = datetime.utcnow().isoformat()
            self.validation_tier = None
            self.validator_metadata = None
            self.error = None

        def complete(self, validation_tier: str | None = None, validator_metadata: Dict[str, Any] | None = None, **_):
            self.validation_tier = validation_tier
            self.validator_metadata = validator_metadata or {}

        def fail(self, error: str | None = None, **_):
            self.error = error

        def to_dict(self) -> Dict[str, Any]:
            return {
                "task_id": self.task_id,
                "action_type": self.action_type,
                "expected_outcome": self.expected_outcome,
                "confidence_pre": self.confidence_pre,
                "metadata": self.metadata,
                "timestamp": self.timestamp,
                "validation_tier": self.validation_tier,
                "validator_metadata": self.validator_metadata,
                "error": self.error,
                "using_executive_layer": False,
            }

    class DecisionJournal:
        def __init__(self, log_path: str | None = None):
            if log_path is None:
                log_path = os.path.expanduser("~/.openclaw/logs/guardian-journal.jsonl")
            self.log_path = Path(log_path)
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

        def log(self, decision: DecisionRecord):
            payload = decision.to_dict() if hasattr(decision, "to_dict") else {"decision": str(decision)}
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")

    class BudgetContext:
        def __init__(self, *_args, **_kwargs): ...
        def __enter__(self): return self
        def __exit__(self, *_): return False


# =========================================================
# Config
# =========================================================
EXEC_HOOK_ENABLED = os.getenv("EXEC_HOOK_ENABLED", "0") == "1"

HIGH_RISK_ALLOWLIST = {
    "file_write",
    "file_delete",
    "command_exec",
    "json_write",
    "http_request",
}

journal = DecisionJournal()
validator = Validator()


def _safe_kwargs(callable_obj, **kwargs) -> Dict[str, Any]:
    """Return only kwargs supported by callable_obj's signature."""
    try:
        sig = inspect.signature(callable_obj)
        allowed = set(sig.parameters.keys())
        allowed.discard("self")
        return {k: v for k, v in kwargs.items() if k in allowed}
    except Exception:
        return {}


def get_status() -> Dict[str, Any]:
    return {
        "exec_hook_enabled": EXEC_HOOK_ENABLED,
        "using_executive_layer": USING_EXECUTIVE_LAYER,
        "allowlist": sorted(HIGH_RISK_ALLOWLIST),
        "journal_type": type(journal).__name__,
    }


# =========================================================
# Core Membrane
# =========================================================
def exec_with_guard(
    *,
    task_id: str,
    lane: str,
    action_type: str,
    expected_outcome: str,
    confidence_pre: float,
    perform_fn: Callable[[], Any],
    validate_fn: Callable[[Any], Tuple[str, Dict[str, Any]]],
    metadata: Dict[str, Any] | None = None,
):
    if (not EXEC_HOOK_ENABLED) or (action_type not in HIGH_RISK_ALLOWLIST):
        return perform_fn()

    decision_kwargs = dict(
        task_id=task_id,
        action_type=action_type,
        expected_outcome=expected_outcome,
        confidence_pre=confidence_pre,
        policy_check={"executive_guardian": "pass"},
        metadata=metadata or {},
    )
    decision = DecisionRecord(**_safe_kwargs(DecisionRecord.__init__, **decision_kwargs))

    try:
        with BudgetContext(task_id, lane, action_type=action_type):
            result = perform_fn()

            tier, vmeta = validate_fn(result)

            decision.complete(**_safe_kwargs(decision.complete, validation_tier=tier, validator_metadata=vmeta))
            journal.log(decision)
            return result

    except Exception as e:
        # Schema-adaptive failure handling:
        # - Some Executive Layer DecisionRecord versions have no .fail()
        # - Prefer logging a FAIL tier via complete() if available
        try:
            if hasattr(decision, "complete"):
                decision.complete(**_safe_kwargs(
                    decision.complete,
                    validation_tier=getattr(validator, "FAIL", "fail"),
                    validator_metadata={"error": str(e)},
                ))
        except Exception:
            # If complete() can't accept these fields, ignore and just journal log.
            pass

        try:
            journal.log(decision)
        except Exception:
            # Absolute last resort: write minimal failure record if journal/logging fails
            try:
                import json as _json
                from pathlib import Path as _Path
                logp = _Path(os.path.expanduser("~/.openclaw/logs/guardian-journal.jsonl"))
                logp.parent.mkdir(parents=True, exist_ok=True)
                with open(logp, "a", encoding="utf-8") as f:
                    f.write(_json.dumps({
                        "task_id": task_id,
                        "lane": lane,
                        "action_type": action_type,
                        "expected_outcome": expected_outcome,
                        "confidence_pre": confidence_pre,
                        "error": str(e),
                        "using_executive_layer": USING_EXECUTIVE_LAYER,
                    }) + "
")
            except Exception:
                pass

        raise


# =========================================================
# Wrappers
# =========================================================
def wrap_file_write(task_id: str, lane: str, file_path: str, content: str, write_fn: Callable[[str, str], Any]):
    def perform():
        return write_fn(file_path, content)

    def validate(_):
        exists = os.path.exists(file_path)
        return (validator.SUCCESS if exists else validator.FAIL, {"exists": exists, "path": file_path})

    return exec_with_guard(
        task_id=task_id,
        lane=lane,
        action_type="file_write",
        expected_outcome=f"{file_path} exists",
        confidence_pre=0.80,
        perform_fn=perform,
        validate_fn=validate,
        metadata={"path": file_path, "bytes": len(content)},
    )


def wrap_file_delete(task_id: str, lane: str, file_path: str, delete_fn: Callable[[str], Any]):
    def perform():
        return delete_fn(file_path)

    def validate(_):
        exists_after = os.path.exists(file_path)
        return (validator.SUCCESS if not exists_after else validator.FAIL, {"exists_after": exists_after, "path": file_path})

    return exec_with_guard(
        task_id=task_id,
        lane=lane,
        action_type="file_delete",
        expected_outcome=f"{file_path} removed",
        confidence_pre=0.85,
        perform_fn=perform,
        validate_fn=validate,
        metadata={"path": file_path},
    )


def wrap_command_exec(task_id: str, lane: str, command: str):
    def perform():
        return subprocess.run(command, shell=True, capture_output=True, text=True)

    def validate(res):
        ok = (res.returncode == 0)
        return (
            validator.SUCCESS if ok else validator.FAIL,
            {
                "returncode": res.returncode,
                "stdout": (res.stdout or "")[:500],
                "stderr": (res.stderr or "")[:500],
            },
        )

    return exec_with_guard(
        task_id=task_id,
        lane=lane,
        action_type="command_exec",
        expected_outcome=f"{command} exit 0",
        confidence_pre=0.70,
        perform_fn=perform,
        validate_fn=validate,
        metadata={"command": command},
    )


def wrap_json_write(task_id: str, lane: str, file_path: str, data: Dict[str, Any], write_fn: Callable[[str, str], Any]):
    def perform():
        write_fn(file_path, json.dumps(data, indent=2))
        return file_path

    def validate(_):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                json.load(f)
            return (validator.SUCCESS, {"json_valid": True, "path": file_path})
        except Exception as e:
            return (validator.FAIL, {"json_valid": False, "path": file_path, "error": str(e)})

    return exec_with_guard(
        task_id=task_id,
        lane=lane,
        action_type="json_write",
        expected_outcome="JSON written and valid",
        confidence_pre=0.82,
        perform_fn=perform,
        validate_fn=validate,
        metadata={"path": file_path},
    )


def wrap_http_request(
    task_id: str,
    lane: str,
    request_fn: Callable[[], Any],
    expected_statuses=(200, 201, 202, 204),
):
    def perform():
        return request_fn()

    def validate(res):
        status = None
        if isinstance(res, dict):
            status = res.get("status_code")
        else:
            status = getattr(res, "status_code", None)
        ok = status in expected_statuses
        return (validator.SUCCESS if ok else validator.FAIL, {"status_code": status, "expected": list(expected_statuses)})

    return exec_with_guard(
        task_id=task_id,
        lane=lane,
        action_type="http_request",
        expected_outcome=f"HTTP status in {list(expected_statuses)}",
        confidence_pre=0.75,
        perform_fn=perform,
        validate_fn=validate,
        metadata={"expected_statuses": list(expected_statuses)},
    )
