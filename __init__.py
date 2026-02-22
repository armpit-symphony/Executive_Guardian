"""
Executive Guardian - Execution Discipline Layer for OpenClaw
"""

from .guardian import (
    EXEC_HOOK_ENABLED,
    Validator,
    DecisionRecord,
    DecisionJournal,
    BudgetContext,
    exec_with_guard,
    wrap_file_write,
    wrap_file_delete,
    wrap_command_exec,
    wrap_json_write,
)

__version__ = "1.0.0"
