#!/bin/bash

POD=`kubectl get pods -l=app=$1 | tail -n 1 | cut -d ' ' -f1`

if [ -z "$2" ]
  then
    kubectl logs $POD 
  else
	kubectl logs $POD -c $2 
fi
