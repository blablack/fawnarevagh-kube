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
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.13.0/deploy/longhorn.yaml
kubectl apply -f $SCRIPT_DIR/../longhorn/longhorn.yaml

# Upstream's manifest defaults these to production-fleet HA counts (3 replicas each for the
# CSI sidecar controllers via leader election and for longhorn-global-manager, 2 for the UI) which don't fit a 2-node cluster -
# right-size down to 1 each. Re-run after every longhorn.yaml re-apply (e.g. a version bump)
# since that would otherwise silently reset these back to 3/2.
#
# The csi-* deployments aren't in the upstream manifest - longhorn-driver-deployer (re)creates
# them asynchronously once the new longhorn-manager is up, resetting them to 3 replicas. On a
# version bump the old csi-* deployments are still there and Available, so a plain `kubectl
# wait` passes immediately and the scale-down below gets undone a minute later. Instead, wait
# until each csi-* deployment runs the image the new driver-deployer wants (its CSI_*_IMAGE
# env vars), i.e. until the redeploy has actually happened.
kubectl rollout status --timeout=300s deployment -n longhorn-system longhorn-driver-deployer
for sidecar in attacher provisioner resizer snapshotter; do
    want=$(kubectl get deployment -n longhorn-system longhorn-driver-deployer \
        -o jsonpath="{.spec.template.spec.containers[0].env[?(@.name==\"CSI_${sidecar^^}_IMAGE\")].value}")
    echo "Waiting for csi-$sidecar to be redeployed with $want..."
    timeout 600 bash -c "until [ \"\$(kubectl get deployment -n longhorn-system csi-$sidecar \
        -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null)\" = '$want' ]; do sleep 5; done"
done
kubectl wait --for=condition=Available --timeout=120s deployment -n longhorn-system csi-attacher csi-provisioner csi-resizer csi-snapshotter longhorn-ui longhorn-global-manager
kubectl scale deployment -n longhorn-system csi-attacher csi-provisioner csi-resizer csi-snapshotter longhorn-ui longhorn-global-manager --replicas=1

# https://github.com/cert-manager/cert-manager
kubectl apply --server-side -f https://github.com/cert-manager/cert-manager/releases/download/v1.21.2/cert-manager.yaml
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
