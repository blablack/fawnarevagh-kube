#!/bin/bash

peer_list=$(nordvpn meshnet peer list)

for i in $(echo "$peer_list" | awk '/Hostname:/ && NR > 2 {print $2}'); do
    # print the hostname
    nordvpn meshnet peer routing allow $i
    nordvpn meshnet peer local allow $i
done