"""
Executive Guardian v1.0
Execution membrane for OpenClaw.

Behavior:
- If Executive Layer is installed (workspace/executive), uses REAL:
  DecisionRecord, DecisionJournal, BudgetContext, Validator
- Otherwise falls back to lightweight stubs for standalone operation.

Feature flag: EXEC_HOOK_ENABLED=1 enables membrane routing (allowlist-based)
"""

from __future__ import annotations

import os
import inspect
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

# ========================================================
# Try REAL Executive Layer first, fallback to stubs
# ========================================================

USING_EXECUTIVE_LAYER = False

try:
    from executive import DecisionRecord, DecisionJournal, BudgetContext, Validator  # type: ignore
    USING_EXECUTIVE_LAYER = True

except Exception:
    # ---------------------------
    # STUBS (standalone fallback)
    # ---------------------------

    class Validator:
        SUCCESS = "success"
        FAIL = "fail"
        ACCEPTABLE = "acceptable"


    class DecisionRecord:
        def __init__(
            self,
            task_id: str,
            action_type: str,
            expected_outcome: str,
            confidence_pre: float,
            policy_check: Dict[str, Any] | None = None,
            metadata: Dict[str, Any] | None = None,
        ):
            self.task_id = task_id
            self.action_type = action_type
            self.expected_outcome = expected_outcome
            self.confidence_pre = confidence_pre
            self.policy_check = policy_check or {}
            self.metadata = metadata or {}
            self.timestamp = datetime.utcnow().isoformat()
            self.result = None
            self.error = None
            self.validation_tier = None
            self.confidence_post = None
            self.validator_metadata = None

        def complete(
            self,
            validation_tier: str,
            validator_metadata: Dict[str, Any] | None = None,
            **_,
        ):
            self.result = "success"
            self.validation_tier = validation_tier
            self.confidence_post = self.confidence_pre
            self.validator_metadata = validator_metadata or {}

        def fail(self, error: str, **_) -> None:
            self.result = "fail"
            self.error = error
            self.confidence_post = self.confidence_pre * 0.5

        def to_dict(self) -> Dict[str, Any]:
            return {
                "task_id": self.task_id,
                "action_type": self.action_type,
                "expected_outcome": self.expected_outcome,
                "confidence_pre": self.confidence_pre,
                "confidence_post": self.confidence_post,
                "result": self.result,
                "validation_tier": self.validation_tier,
                "error": self.error,
                "timestamp": self.timestamp,
                "policy_check": self.policy_check,
                "metadata": self.metadata,
                "validator_metadata": self.validator_metadata,
                "using_executive_layer": False,
            }


    class DecisionJournal:
        def __init__(self, log_path: str | None = None):
            if log_path is None:
                log_path = os.path.expanduser("~/.openclaw/logs/guardian-journal.jsonl")
            self.log_path = Path(log_path)
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

        def log(self, decision: DecisionRecord) -> None:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(decision.to_dict()) + "\n")


    class BudgetContext:
        def __init__(
            self,
            task_id: str,
            lane: str,
            action_type: str | None = None,
            **_,
        ):
            self.task_id = task_id
            self.lane = lane
            self.action_type = action_type
            self.start_time = datetime.utcnow()

        def __enter__(self):
            return self

        def __exit__(self, *args) -> bool:
            return False


# ========================================================
# Configuration
# ========================================================

EXEC_HOOK_ENABLED = os.getenv("EXEC_HOOK_ENABLED", "0") == "1"

# Allowlist of action types routed through the membrane
HIGH_RISK_ALLOWLIST = {
    "file_write",
    "file_delete",
    "command_exec",
    "json_write",
    "http_request",
}

# If using Executive Layer, its DecisionJournal will write to executive/decisions
# Otherwise fallback journal writes to ~/.openclaw/logs/guardian-journal.jsonl
journal = DecisionJournal()
validator = Validator()



def _safe_decision_kwargs(**kwargs):
    """
    Only pass kwargs that the current DecisionRecord.__init__ supports.
    This makes Executive Guardian compatible across Executive Layer schema versions.
    """
    try:
        sig = inspect.signature(DecisionRecord.__init__)
        allowed = set(sig.parameters.keys())
        # remove self
        allowed.discard("self")
        return {k: v for k, v in kwargs.items() if k in allowed}
    except Exception:
        # If anything weird happens, be conservative and pass the essentials only.
        essentials = {"task_id", "action_type", "expected_outcome", "confidence_pre"}
        return {k: v for k, v in kwargs.items() if k in essentials}



def _safe_kwargs_for(callable_obj, **kwargs):
    """
    Only pass kwargs supported by callable_obj's signature.
    Works across Executive Layer schema versions.
    """
    try:
        sig = inspect.signature(callable_obj)
        allowed = set(sig.parameters.keys())
        allowed.discard("self")
        return {k: v for k, v in kwargs.items() if k in allowed}
    except Exception:
        return {}

def get_status() -> Dict[str, Any]:
    """Quick status for smoke tests."""
    return {
        "exec_hook_enabled": EXEC_HOOK_ENABLED,
        "using_executive_layer": USING_EXECUTIVE_LAYER,
        "allowlist": sorted(HIGH_RISK_ALLOWLIST),
        "journal_type": type(journal).__name__,
    }


# ========================================================
# Core Membrane
# ========================================================

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
) -> Any:
    """
    Wrap execution with:
    - Budget locks (real when Executive Layer is present)
    - Validation tier assignment
    - Decision logging
    """
    if (not EXEC_HOOK_ENABLED) or (action_type not in HIGH_RISK_ALLOWLIST):
        return perform_fn()

    decision = DecisionRecord(**_safe_kwargs_for(DecisionRecord.__init__,
        task_id=task_id,
        action_type=action_type,
        expected_outcome=expected_outcome,
        confidence_pre=confidence_pre,
        policy_check={"executive_guardian": "pass"},
        metadata=metadata or {},
    ))
)

    try:
        with BudgetContext(task_id, lane, action_type=action_type):
            result = perform_fn()

        tier, vmeta = validate_fn(result)
        # Executive Layer signature supports more fields; stubs ignore extras.
        decision.complete(**_safe_kwargs_for(decision.complete,
                validation_tier=tier,
                validator_metadata=vmeta,
                confidence_post=confidence_pre,
            ))
journal.log(decision)
        return result

    except Exception as e:
        decision.fail(**_safe_kwargs_for(decision.fail, error=str(e)))
)
        journal.log(decision)
        raise


# ========================================================
# High-Risk Wrappers
# ========================================================


def wrap_file_write(
    task_id: str,
    lane: str,
    file_path: str,
    content: str,
    write_fn: Callable[[str, str], Any],
) -> Any:
    def perform():
        return write_fn(file_path, content)

    def validate(_):
        exists = os.path.exists(file_path)
        return (
            validator.SUCCESS if exists else validator.FAIL,
            {"exists": exists, "path": file_path, "bytes": len(content)},
        )

    return exec_with_guard(
        task_id=task_id,
        lane=lane,
        action_type="file_write",
        expected_outcome=f"{file_path} exists",
        confidence_pre=0.80,
        perform_fn=perform,
        validate_fn=validate,
        metadata={"path": file_path},
    )


def wrap_file_delete(
    task_id: str,
    lane: str,
    file_path: str,
    delete_fn: Callable[[str], Any],
) -> Any:
    def perform():
        return delete_fn(file_path)

    def validate(_):
        exists_after = os.path.exists(file_path)
        return (
            validator.SUCCESS if not exists_after else validator.FAIL,
            {"exists_after": exists_after, "path": file_path},
        )

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


def wrap_command_exec(task_id: str, lane: str, command: str) -> Any:
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


def wrap_json_write(
    task_id: str,
    lane: str,
    file_path: str,
    data: Dict[str, Any],
    write_fn: Callable[[str, str], Any],
) -> Any:
    def perform():
        write_fn(file_path, json.dumps(data, indent=2))
        return file_path

    def validate(_):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                json.load(f)
            return validator.SUCCESS, {"json_valid": True, "path": file_path}
        except Exception as e:
            return validator.FAIL, {"json_valid": False, "path": file_path, "error": str(e)}

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
    expected_statuses: Tuple[int, ...] = (200, 201, 202, 204),
) -> Any:
    """
    Generic HTTP wrapper.
    request_fn should return an object with at least:
    - status_code (int) OR a dict {"status_code": int}
    """

    def perform():
        return request_fn()

    def validate(res):
        status = None
        if isinstance(res, dict):
            status = res.get("status_code")
        else:
            status = getattr(res, "status_code", None)
        ok = status in expected_statuses
        return (
            validator.SUCCESS if ok else validator.FAIL,
            {"status_code": status, "expected": list(expected_statuses)},
        )

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
