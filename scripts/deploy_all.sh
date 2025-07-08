#!/bin/bash

set -e

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

kubectl apply -f $SCRIPT_DIR/../metallb/metallb-config.yaml
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.15.2/config/manifests/metallb-native.yaml

kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.9.0/deploy/longhorn.yaml
kubectl apply -f $SCRIPT_DIR/../longhorn/longhorn.yaml

kubectl apply -f $SCRIPT_DIR/../persistent-volumes/nasio-nfs.yaml
kubectl apply -f $SCRIPT_DIR/../persistent-volumes/longhorn.yaml

kubectl apply -f $SCRIPT_DIR/../registry/registry-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../registry/registry.yaml

(
    cd $SCRIPT_DIR/../intel-gpu-plugin
    wget -O intel-gpu-plugin.yaml https://raw.githubusercontent.com/intel/intel-device-plugins-for-kubernetes/refs/heads/main/deployments/gpu_plugin/base/intel-gpu-plugin.yaml
    sed -i 's/imagePullPolicy: IfNotPresent/imagePullPolicy: Always/g' intel-gpu-plugin.yaml
    sed -i '/imagePullPolicy: Always/a\
        args:\
          - "-shared-dev-num"\
          - "2"' ./intel-gpu-plugin.yaml
    kubectl apply -f intel-gpu-plugin.yaml
)

(
    cd $SCRIPT_DIR/../argocd

    kubectl apply -f argocd-namespace.yaml

    wget https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml -O argocd.yaml

    kubectl apply --force-conflicts --server-side --namespace argocd -f argocd.yaml
    kubectl apply --namespace argocd -f argocd-service.yaml
    kubectl apply --namespace argocd -f argocd-config.yaml
    kubectl apply --namespace argocd -f argocd-applicationset.yaml
)

(
    cd $SCRIPT_DIR/../prometheus

    kubectl apply -f namespace.yaml

    wget -O prometheus-crd.yaml https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/master/bundle.yaml
    sed -i 's/namespace: default/namespace: monitoring/g' prometheus-crd.yaml
    kubectl apply -f prometheus-crd.yaml --server-side --force-conflicts

    kubectl apply -f prometheus-rbac.yaml

    kubectl apply -f prometheus.yaml

    kubectl apply -f monitor-node-exporter.yaml
    kubectl apply -f monitor-longhorn.yaml
    kubectl apply -f monitor-kubelet.yaml
    kubectl apply -f monitor-snmp.yaml
)

