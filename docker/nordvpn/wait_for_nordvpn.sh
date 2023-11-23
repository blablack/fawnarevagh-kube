#!/bin/bash

sleep 10s

while ! nordvpn status | grep -q 'Status: Connected' ; 
    do sleep 10s ; 
done

echo `date`
echo "NordVPN is connected"

sleep 1m

nordvpn status

echo "NordVPN is initialized"
echo `date`
