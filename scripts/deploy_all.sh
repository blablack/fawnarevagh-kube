#!/bin/bash

###########################################################################
## DEPLOYMENTS WITH LOCKED VERSIONS
## - authentik
##   https://github.com/goauthentik/authentik
##
## - external-dns
##   https://github.com/kubernetes-sigs/external-dns
##
## - intel-gpu-plugin
##   https://github.com/intel/intel-device-plugins-for-kubernetes/releases/
###########################################################################

set -e

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

# https://github.com/metallb/metallb
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.16.1/config/manifests/metallb-native.yaml
kubectl apply -f $SCRIPT_DIR/../metallb/metallb-config.yaml

# https://github.com/longhorn/longhorn
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.12.1/deploy/longhorn.yaml
kubectl apply -f $SCRIPT_DIR/../longhorn/longhorn.yaml

# Upstream's manifest defaults these to production-fleet HA counts (3 replicas each for the
# CSI sidecar controllers via leader election, 2 for the UI) which don't fit a 2-node cluster -
# right-size down to 1 each. Re-run after every longhorn.yaml re-apply (e.g. a version bump)
# since that would otherwise silently reset these back to 3/2.
kubectl wait --for=condition=Available --timeout=120s deployment -n longhorn-system csi-attacher csi-provisioner csi-resizer csi-snapshotter longhorn-ui
kubectl scale deployment -n longhorn-system csi-attacher csi-provisioner csi-resizer csi-snapshotter longhorn-ui --replicas=1

# https://github.com/cert-manager/cert-manager
kubectl apply --server-side -f https://github.com/cert-manager/cert-manager/releases/download/v1.21.1/cert-manager.yaml
kubectl apply -f $SCRIPT_DIR/../cert-manager/cert-manager.yaml

kubectl apply -f $SCRIPT_DIR/../persistent-volumes/nasio-nfs.yaml
kubectl apply -f $SCRIPT_DIR/../persistent-volumes/longhorn.yaml

kubectl annotate svc traefik -n kube-system metallb.io/loadBalancerIPs=192.168.2.220

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
