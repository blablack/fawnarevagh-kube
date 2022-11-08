#!/bin/bash

sleep 10s

while ! nordvpn status | grep -q 'Status: Connected' ; 
    do sleep 10s ; 
done

sleep 10s
