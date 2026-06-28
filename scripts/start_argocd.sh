#!/bin/bash

###########################################################################
## Start ArgoCD again after ./stop_argocd.sh by scaling its workloads in
## the argocd namespace back to 1 replica each (the default for this
## single-instance install). ArgoCD will resume syncing from git.
###########################################################################

set -e

kubectl scale -n argocd statefulset --all --replicas=1
kubectl scale -n argocd deployment --all --replicas=1

echo "ArgoCD started (all argocd workloads scaled to 1)."
