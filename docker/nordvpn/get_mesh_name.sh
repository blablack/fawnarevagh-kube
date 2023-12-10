#!/bin/bash

output=$(nordvpn meshnet peer list)

# Extract the first hostname of the list
hostname=$(echo "$output" | awk '/Hostname/{print $2; exit}')

# Print the hostname
echo $hostname > /config/mesh_peer_name
