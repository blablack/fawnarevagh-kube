#!/bin/bash

#status=$(curl --interface nordlynx -m 10 -s https://api.nordvpn.com/v1/helpers/ips/insights | jq -r '.["protected"]')
#if [ "$status" == "true" ]; then 
#    exit 0
#else 
#    exit 1
#fi

status_output=$(nordvpn status)

if echo "$status_output" | grep -q 'Status: Connected'; then
  exit 0
else
  exit 1
fi