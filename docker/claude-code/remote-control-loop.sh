#!/bin/bash
# Usage: remote-control-loop.sh <project-name>   (run in the project's directory)

# Sessions are named after the project: the first one exactly, ones started later from the
# app as <project>-<generated words>
name="${1:-$(basename "$PWD")}"
export CLAUDE_REMOTE_CONTROL_SESSION_NAME_PREFIX="$name"

# claude remote-control exits when not logged in yet, or after ~10 minutes without network.
# Restarting it in the same directory brings back the sessions it was serving.
while true; do
  claude remote-control --permission-mode auto --spawn same-dir --name "$name" || true
  echo "claude remote-control exited, restarting in 30s (not logged in? run: claude auth login)"
  sleep 30
done
