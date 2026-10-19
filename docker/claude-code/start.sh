#!/bin/bash
set -euo pipefail

# Directories the deployment wants on PATH (toolchains installed on the PVC); the image knows
# nothing about them
export PATH="${EXTRA_PATH:+$EXTRA_PATH:}$PATH"

mkdir -p "$HOME/projects"

WORKDIR="${CLAUDE_WORKDIR:-$HOME/projects}"
mkdir -p "$WORKDIR"
tmux new-session -d -s claude -c "$WORKDIR" /usr/local/bin/remote-control-loop.sh

# Container lives as long as the tmux session; on SIGTERM, stop tmux so claude gets SIGHUP
trap 'tmux kill-server; exit 0' TERM
while tmux has-session -t claude 2>/dev/null; do
  sleep 30 &
  wait $!
done
