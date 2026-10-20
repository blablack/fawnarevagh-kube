#!/bin/bash
set -euo pipefail

# Directories the deployment wants on PATH (toolchains installed on the PVC); the image knows
# nothing about them
export PATH="${EXTRA_PATH:+$EXTRA_PATH:}$PATH"

mkdir -p "$HOME/projects"

# Pre-answer the two one-time prompts Claude Code asks on first start in a new home:
#   1. "Allow remote control?" — set hasAcknowledgedRemoteControlWarning so it never blocks startup
#   2. git safe.directory — pre-trust all directories so repo ownership checks don't prompt
# Both are idempotent: jq only sets the key if absent; gitconfig line is deduplicated by git itself.

CLAUDE_JSON="$HOME/.claude.json"
if [ ! -f "$CLAUDE_JSON" ]; then
  echo '{}' > "$CLAUDE_JSON"
fi
if ! jq -e '.hasAcknowledgedRemoteControlWarning == true' "$CLAUDE_JSON" > /dev/null 2>&1; then
  tmp=$(mktemp)
  jq '. + {"hasAcknowledgedRemoteControlWarning": true}' "$CLAUDE_JSON" > "$tmp" && mv "$tmp" "$CLAUDE_JSON"
fi

git config --global --get-all safe.directory | grep -qxF '*' || \
  git config --global --add safe.directory '*'

WORKDIR="${CLAUDE_WORKDIR:-$HOME/projects}"
mkdir -p "$WORKDIR"
tmux new-session -d -s claude -c "$WORKDIR" /usr/local/bin/remote-control-loop.sh

# Container lives as long as the tmux session; on SIGTERM, stop tmux so claude gets SIGHUP
trap 'tmux kill-server; exit 0' TERM
while tmux has-session -t claude 2>/dev/null; do
  sleep 30 &
  wait $!
done
