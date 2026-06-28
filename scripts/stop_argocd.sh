#!/bin/bash

###########################################################################
## Stop ArgoCD by scaling all its workloads in the argocd namespace to 0.
## Use this before doing manual maintenance (e.g. scaling an app to 0 or
## recovering a database) so ArgoCD's selfHeal does not revert your changes.
## Run ./start_argocd.sh to bring it back.
###########################################################################

set -e

kubectl scale -n argocd statefulset --all --replicas=0
kubectl scale -n argocd deployment --all --replicas=0

echo "ArgoCD stopped (all argocd workloads scaled to 0)."
