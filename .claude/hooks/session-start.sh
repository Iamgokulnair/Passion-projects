#!/bin/bash
set -euo pipefail

# Only run in Claude Code remote (web) sessions
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo '{"async": true, "asyncTimeout": 30000}'

# Log session start for audit trail
echo "[job-sweep] Session started at $(date '+%Y-%m-%d %H:%M IST') — sweep will run automatically"
