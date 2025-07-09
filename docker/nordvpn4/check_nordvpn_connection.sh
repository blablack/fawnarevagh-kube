#!/bin/bash

status_output=$(nordvpn status)

if echo "$status_output" | grep -q 'Status: Connected'; then
  exit 0
else
  exit 1
fi
