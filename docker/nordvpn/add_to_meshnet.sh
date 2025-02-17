#!/bin/bash

# Function to check if "Allow Routing" and "Allow Local Network Access" are enabled
check_peer_status() {
    local output="$1"
    local peer_name="$2"

    allow_routing=$(echo "$output" | grep -A10 "Hostname: $peer_name" | grep "Allow Routing")
    allow_local_network_access=$(echo "$output" | grep -A10 "Hostname: $peer_name" | grep "Allow Local Network Access")

    echo $allow_routing
    echo $allow_local_network_access

    if [[ "$allow_routing" != "Allow Routing: enabled" ]]; then
        nordvpn meshnet peer routing allow $peer_name
    fi

    if [[ "$allow_local_network_access" != "Allow Local Network Access: enabled" ]]; then
        nordvpn meshnet peer local allow $peer_name
    fi
}

# Get the output of the command
output=$(nordvpn meshnet peer list)

# Check the status for each local peer
peer_names=$(echo "$output" | grep "Local Peers:" -A1000 | grep "Hostname:" | awk '{print $2}')
for peer_name in $peer_names; do
    echo $peer_name
    check_peer_status "$output" "$peer_name"
    echo
done
