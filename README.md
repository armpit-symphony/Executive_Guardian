# Executive Guardian v1.0

Execution Discipline Layer for OpenClaw

## Overview

Executive Guardian is an execution membrane that wraps high-risk tools with:
- Budget locks (time, tokens, cost)
- Validation tiers (SUCCESS / FAIL)
- Decision logging with confidence calibration
- Feature flag gating (EXEC_HOOK_ENABLED)

## Quick Start

```bash
# Run tests
python3 -c "from executive_guardian import *; print('OK')"
```

## Feature Flags

| Flag | Default | Purpose |
|------|---------|---------|
| EXEC_HOOK_ENABLED | 0 | Activate execution hooks |
| GUARDIAN_LOG_LEVEL | INFO | Logging verbosity |

## Architecture

```
OpenClaw Tool Execution
        │
        ▼
┌───────────────────┐
│  Executive        │
│  Guardian         │
│  Membrane         │
└───────────────────┘
        │
   ┌────┴────┐
   ▼         ▼
Budget    Validation
Lock      Tier
   │         │
   └────┬────┘
        ▼
   Decision
   Journal
```

## Status

✅ Standalone v1.0 - Ready for integration
