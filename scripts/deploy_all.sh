#!/bin/bash

set -e

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

kubectl apply -f $SCRIPT_DIR/../metallb/metallb-config.yaml
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.15.2/config/manifests/metallb-native.yaml

kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.9.1/deploy/longhorn.yaml
kubectl apply -f $SCRIPT_DIR/../longhorn/longhorn.yaml

kubectl apply -f $SCRIPT_DIR/../persistent-volumes/nasio-nfs.yaml
kubectl apply -f $SCRIPT_DIR/../persistent-volumes/longhorn.yaml

kubectl apply -f $SCRIPT_DIR/../registry/registry-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../registry/registry.yaml

(
    cd $SCRIPT_DIR/../intel-gpu-plugin
    kubectl apply -k .
)

(
    cd $SCRIPT_DIR/../argocd

    kubectl apply -f argocd-namespace.yaml

    kubectl apply -k .
    
    kubectl apply --namespace argocd -f argocd-service.yaml
    kubectl apply --namespace argocd -f argocd-config.yaml
    kubectl patch configmap argocd-cm -n argocd --patch-file argocd-dex-config.yaml
    kubectl apply --namespace argocd -f argocd-applicationset.yaml
)

(
    cd $SCRIPT_DIR/../prometheus

    kubectl apply -f namespace.yaml

    kubectl apply -k . --server-side --force-conflicts

    kubectl apply -f prometheus-rbac.yaml

    kubectl apply -f prometheus.yaml

    kubectl apply -f monitor-node-exporter.yaml
    kubectl apply -f monitor-longhorn.yaml
    kubectl apply -f monitor-kubelet.yaml
    kubectl apply -f monitor-snmp.yaml
)

