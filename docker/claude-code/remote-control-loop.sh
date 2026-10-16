#!/bin/bash

# claude remote-control exits when not logged in yet, or after ~10 minutes without network.
# Restarting it in the same directory brings back the sessions it was serving.
while true; do
  claude remote-control --permission-mode auto || true
  echo "claude remote-control exited, restarting in 30s (not logged in? run: claude auth login)"
  sleep 30
done
