#!/bin/bash

echo "Start NordVPN"
systemctl start nordvpn &

echo "Login to NordVPN"
nordvpn login --token $NORDVPN_TOKEN 

echo "Configure NordVPN"
nordvpn set technology nordlynx 

echo "Connect to VPN"
nordvpn connect $COUNTRY

sleep 365d