#!/bin/bash

###########################################################################
## DEPLOYMENTS WITH LOCKED VERSIONS
## - authentik
## - external-dns
## - intel-gpu-plugin
###########################################################################

set -e

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.15.3/config/manifests/metallb-native.yaml
kubectl apply -f $SCRIPT_DIR/../metallb/metallb-config.yaml

kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.11.0/deploy/longhorn.yaml
kubectl apply -f $SCRIPT_DIR/../longhorn/longhorn.yaml

kubectl apply --server-side -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
kubectl apply -f $SCRIPT_DIR/../cert-manager/cert-manager.yaml

kubectl apply -f $SCRIPT_DIR/../persistent-volumes/nasio-nfs.yaml
kubectl apply -f $SCRIPT_DIR/../persistent-volumes/longhorn.yaml

kubectl annotate svc traefik -n kube-system metallb.io/loadBalancerIPs=192.168.2.226

(
    cd $SCRIPT_DIR/../intel-gpu-plugin
    kubectl apply -k .
)

(
    cd $SCRIPT_DIR/../argocd
    kubectl apply --server-side --force-conflicts -k .
)

(
    cd $SCRIPT_DIR/../prometheus
    kubectl apply --server-side --force-conflicts -k .
)
