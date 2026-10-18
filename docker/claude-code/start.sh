#!/bin/bash
set -euo pipefail

# Keep Gradle + the Kotlin daemon inside the container's memory limit (8Gi). Lives in
# ~/.gradle on the PVC (alongside Gradle's caches), so only written if missing.
if [ ! -f "$HOME/.gradle/gradle.properties" ]; then
  mkdir -p "$HOME/.gradle"
  cat > "$HOME/.gradle/gradle.properties" <<EOF
org.gradle.jvmargs=-Xmx3g -XX:+UseParallelGC
org.gradle.workers.max=4
kotlin.daemon.jvmargs=-Xmx2g
EOF
fi

mkdir -p "$HOME/projects"

tmux new-session -d -s claude -c "$HOME/projects" /usr/local/bin/remote-control-loop.sh

# Container lives as long as the tmux session; on SIGTERM, stop tmux so claude gets SIGHUP
trap 'tmux kill-server; exit 0' TERM
while tmux has-session -t claude 2>/dev/null; do
  sleep 30 &
  wait $!
done
