#!/bin/bash

/usr/sbin/nordvpnd &

sleep 15s

nordvpn login --token $NORDVPN_TOKEN ; 
nordvpn set technology nordlynx ; 
nordvpn connect $COUNTRY