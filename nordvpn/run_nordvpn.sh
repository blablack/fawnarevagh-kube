#!/bin/bash

echo "Start NordVPN Service"
systemctl start nordvpn && 
sleep 2s && 

echo "Login to NordVPN"
nordvpn login --token $NORDVPN_TOKEN &&
    
echo "Configure NordVPN"
nordvpn set technology nordlynx && 
nordvpn whitelist add subnet 192.168.2.0/24 &&
nordvpn set dns 192.168.2.200 &&
    
echo "Connect to NordVPN"
nordvpn connect $COUNTRY && 

nordvpn status &&

while nordvpn status | grep -q 'Status: Connected' ; 
    do sleep 5m ; 
done