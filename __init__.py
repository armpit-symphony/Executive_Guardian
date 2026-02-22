"""
Executive Guardian - Execution Discipline Layer for OpenClaw

Uses Executive Layer when available; falls back to stubs for standalone testing.
"""

from .guardian import (
    EXEC_HOOK_ENABLED,
    GUARDIAN_LOG_LEVEL,
    HIGH_RISK_ALLOWLIST,
    Validator,
    DecisionRecord,
    DecisionJournal,
    BudgetContext,
    exec_with_guard,
    wrap_file_write,
    wrap_file_delete,
    wrap_command_exec,
    wrap_json_write,
    wrap_http_request,
    get_status,
)

__version__ = "1.0.0"
