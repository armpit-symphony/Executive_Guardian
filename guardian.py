"""
Executive Guardian v1.0
Execution membrane for OpenClaw

Uses Executive Layer when available; falls back to stubs for standalone testing.
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable, Any

# ========================================================
# Try real Executive Layer imports, fallback to stubs
# ========================================================

_EXECUTIVE_AVAILABLE = False

try:
    # Add executive layer to path
    exec_path = Path("/home/sparky/.openclaw/workspace/executive")
    if exec_path.exists() and str(exec_path) not in sys.path:
        sys.path.insert(0, str(exec_path))
    
    from executive import (
        DecisionRecord,
        DecisionJournal,
        BudgetContext,
        Validator,
    )
    _EXECUTIVE_AVAILABLE = True
    
except ImportError:
    # Stub implementations for standalone testing
    class Validator:
        """Validation tier constants."""
        SUCCESS = "success"
        FAIL = "fail"
        WARNING = "warning"


    class DecisionRecord:
        """Record of a single decision."""
        
        def __init__(
            self,
            task_id: str,
            action_type: str,
            expected_outcome: str,
            confidence_pre: float,
            policy_check: dict = None,
            metadata: dict = None,
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
        
        def complete(self, validation_tier: str, validator_metadata: dict = None):
            self.result = "success"
            self.validation_tier = validation_tier
            self.confidence_post = self.confidence_pre
            if validator_metadata:
                self.metadata.update(validator_metadata)
        
        def fail(self, error: str):
            self.result = "fail"
            self.error = error
            self.confidence_post = self.confidence_pre * 0.5
        
        def to_dict(self) -> dict:
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
                "metadata": self.metadata,
            }


    class DecisionJournal:
        """Log decisions to file."""
        
        def __init__(self, log_path: str = None):
            if log_path is None:
                # Fallback to guardian-specific log
                log_path = os.path.expanduser("~/.openclaw/logs/guardian-journal.jsonl")
            self.log_path = Path(log_path)
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        def log(self, decision: DecisionRecord):
            with open(self.log_path, "a") as f:
                f.write(json.dumps(decision.to_dict()) + "\n")


    class BudgetContext:
        """Budget context manager (stub)."""
        
        def __init__(self, task_id: str, lane: str, action_type: str = None):
            self.task_id = task_id
            self.lane = lane
            self.action_type = action_type
            self.start_time = datetime.utcnow()
        
        def __enter__(self):
            return self
        
        def __exit__(self, *args):
            duration = (datetime.utcnow() - self.start_time).total_seconds()


# ========================================================
# Configuration
# ========================================================

EXEC_HOOK_ENABLED = os.getenv("EXEC_HOOK_ENABLED", "0") == "1"
GUARDIAN_LOG_LEVEL = os.getenv("GUARDIAN_LOG_LEVEL", "INFO")

# Note: http_request removed from allowlist until wrap_http_request is implemented
HIGH_RISK_ALLOWLIST = {
    "file_write",
    "file_delete",
    "command_exec",
    "json_write",
}

# Initialize journal
journal = DecisionJournal()
validator = Validator()


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
    validate_fn: Callable[[Any], tuple],
    metadata: dict | None = None,
):
    """
    Wrap execution with:
    - Budget locks
    - Validation tiers
    - Decision logging
    - Confidence calibration
    """
    if not EXEC_HOOK_ENABLED or action_type not in HIGH_RISK_ALLOWLIST:
        return perform_fn()
    
    decision = DecisionRecord(
        task_id=task_id,
        action_type=action_type,
        expected_outcome=expected_outcome,
        confidence_pre=confidence_pre,
        policy_check={"executive_guardian": "pass"},
        metadata=metadata or {},
    )
    
    try:
        with BudgetContext(task_id, lane, action_type=action_type):
            result = perform_fn()
        
        tier, vmeta = validate_fn(result)
        decision.complete(validation_tier=tier, validator_metadata=vmeta)
        journal.log(decision)
        return result
    
    except Exception as e:
        decision.fail(error=str(e))
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
    write_fn: Callable,
):
    """Wrap file write with validation."""
    
    def perform():
        return write_fn(file_path, content)
    
    def validate(_):
        exists = os.path.exists(file_path)
        return (
            Validator.SUCCESS if exists else Validator.FAIL,
            {"exists": exists, "path": file_path},
        )
    
    return exec_with_guard(
        task_id=task_id,
        lane=lane,
        action_type="file_write",
        expected_outcome=f"{file_path} exists",
        confidence_pre=0.8,
        perform_fn=perform,
        validate_fn=validate,
        metadata={"path": file_path, "bytes": len(content)},
    )


def wrap_file_delete(
    task_id: str,
    lane: str,
    file_path: str,
    delete_fn: Callable,
):
    """Wrap file delete with validation."""
    
    def perform():
        return delete_fn(file_path)
    
    def validate(_):
        exists = os.path.exists(file_path)
        return (
            Validator.SUCCESS if not exists else Validator.FAIL,
            {"exists_after": exists, "path": file_path},
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


def wrap_command_exec(task_id: str, lane: str, command: str):
    """Wrap command execution with validation."""
    
    def perform():
        return subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
        )
    
    def validate(result):
        success = result.returncode == 0
        return (
            Validator.SUCCESS if success else Validator.FAIL,
            {
                "returncode": result.returncode,
                "stdout": result.stdout[:500],
                "stderr": result.stderr[:500],
            },
        )
    
    return exec_with_guard(
        task_id=task_id,
        lane=lane,
        action_type="command_exec",
        expected_outcome=f"{command} exit 0",
        confidence_pre=0.7,
        perform_fn=perform,
        validate_fn=validate,
        metadata={"command": command},
    )


def wrap_json_write(
    task_id: str,
    lane: str,
    file_path: str,
    data: dict,
    write_fn: Callable,
):
    """Wrap JSON write with validation."""
    
    def perform():
        write_fn(file_path, json.dumps(data, indent=2))
        return file_path
    
    def validate(_):
        try:
            with open(file_path, "r") as f:
                json.load(f)
            return Validator.SUCCESS, {"json_valid": True}
        except Exception as e:
            return Validator.FAIL, {"json_valid": False, "error": str(e)}
    
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
    method: str,
    url: str,
    headers: dict = None,
    body: str = None,
    request_fn: Callable = None,
):
    """
    Wrap HTTP request with validation.
    
    Note: Requires request_fn to be provided. If not, uses stub that always succeeds.
    """
    
    def perform():
        if request_fn:
            return request_fn(method, url, headers=headers, body=body)
        # Stub: just return success
        return {"status": "stub", "method": method, "url": url}
    
    def validate(response):
        # Check for HTTP success status
        if isinstance(response, dict):
            status = response.get("status", 200)
            success = 200 <= status < 400
        else:
            success = True
        
        return (
            Validator.SUCCESS if success else Validator.FAIL,
            {"response": str(response)[:200]},
        )
    
    return exec_with_guard(
        task_id=task_id,
        lane=lane,
        action_type="http_request",
        expected_outcome=f"{method} {url} returns 2xx",
        confidence_pre=0.75,
        perform_fn=perform,
        validate_fn=validate,
        metadata={"method": method, "url": url},
    )


# ========================================================
# Status
# ========================================================

def get_status() -> dict:
    """Get Executive Guardian status."""
    log_path = getattr(journal, 'log_path', None) or getattr(journal, 'base_dir', None) or "unknown"
    return {
        "exec_hook_enabled": EXEC_HOOK_ENABLED,
        "executive_layer_available": _EXECUTIVE_AVAILABLE,
        "high_risk_allowlist": list(HIGH_RISK_ALLOWLIST),
        "log_path": str(log_path),
    }
