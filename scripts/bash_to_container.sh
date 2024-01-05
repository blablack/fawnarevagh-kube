#!/bin/bash

POD=`kubectl get pods -l=app=$1 | tail -n 1 | cut -d ' ' -f1`

if [ -z "$2" ]
  then
    kubectl exec --stdin --tty $POD -- /bin/bash
  else
	kubectl exec --stdin --tty $POD -c $2 -- /bin/bash
fi
