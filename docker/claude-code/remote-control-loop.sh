#!/bin/bash
# Usage: remote-control-loop.sh <project-name>   (run in the project's directory)

# Each project is its own entry in the Claude app: <prefix>-<project>
export CLAUDE_REMOTE_CONTROL_SESSION_NAME_PREFIX="${CLAUDE_SESSION_PREFIX:-claude}-${1:-$(basename "$PWD")}"

# claude remote-control exits when not logged in yet, or after ~10 minutes without network.
# Restarting it in the same directory brings back the sessions it was serving.
while true; do
  claude remote-control --permission-mode auto || true
  echo "claude remote-control exited, restarting in 30s (not logged in? run: claude auth login)"
  sleep 30
done
