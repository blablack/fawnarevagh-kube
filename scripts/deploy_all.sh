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

    kubectl apply --namespace argocd -f argocd-config.yaml
    kubectl apply --namespace argocd -f argocd.yaml
    kubectl apply --namespace argocd -f argocd-service.yaml
)

(
    cd $SCRIPT_DIR/../prometheus

    kubectl apply -f namespace.yaml

    wget -O prometheus-crd.yaml https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/master/bundle.yaml
    sed -i 's/namespace: default/namespace: monitoring/g' prometheus-crd.yaml
    kubectl apply -f prometheus-crd.yaml --server-side

    kubectl apply -f prometheus-rbac.yaml

    kubectl apply -f prometheus.yaml

    kubectl apply -f monitor-node-exporter.yaml
    kubectl apply -f monitor-longhorn.yaml
    kubectl apply -f monitor-kubelet.yaml
    kubectl apply -f monitor-snmp.yaml
)

kubectl apply -f $SCRIPT_DIR/../grafana/configmap-dash-cadvisor.yaml --server-side
kubectl apply -f $SCRIPT_DIR/../grafana/configmap-dash-home.yaml --server-side
kubectl apply -f $SCRIPT_DIR/../grafana/configmap-dash-longhorn.yaml --server-side
kubectl apply -f $SCRIPT_DIR/../grafana/configmap-dash-nodes.yaml --server-side
kubectl apply -f $SCRIPT_DIR/../grafana/configmap-dashboards.yaml --server-side
kubectl apply -f $SCRIPT_DIR/../grafana/configmap-datasources.yaml --server-side
kubectl apply -f $SCRIPT_DIR/../grafana/grafana.yaml

kubectl apply -f $SCRIPT_DIR/../k8s-pod-resolver/k8s-pod-resolver.yaml
kubectl apply -f $SCRIPT_DIR/../pihole/pihole-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../pihole/pihole.yaml

kubectl apply -f $SCRIPT_DIR/../dnsmasq/dnsmasq-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../dnsmasq/dnsmasq.yaml
kubectl apply -f $SCRIPT_DIR/../dnsmasq/dnsmasq-ui.yaml

kubectl apply -f $SCRIPT_DIR/../jenkins/jenkins-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../jenkins/jenkins.yaml

kubectl apply -f $SCRIPT_DIR/../ntfy/ntfy-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../ntfy/ntfy.yaml

kubectl apply -f $SCRIPT_DIR/../gatus/gatus.yaml

kubectl apply -f $SCRIPT_DIR/../syncthing/syncthing-aurelien-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../syncthing/syncthing-aurelien.yaml
kubectl apply -f $SCRIPT_DIR/../syncthing/syncthing-yvonne-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../syncthing/syncthing-yvonne.yaml

kubectl apply -f $SCRIPT_DIR/../immich/immich-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../immich/immich.yaml

kubectl apply -f $SCRIPT_DIR/../homer/homer.yaml

kubectl apply -f $SCRIPT_DIR/../paperless/paperless-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../paperless/paperless.yaml

kubectl apply -f $SCRIPT_DIR/../warracker/warracker-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../warracker/warracker.yaml

kubectl apply -f $SCRIPT_DIR/../home-assistant/home-assistant-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../home-assistant/home-assistant.yaml
kubectl apply -f $SCRIPT_DIR/../node-red/node-red-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../node-red/node-red.yaml

kubectl apply -f $SCRIPT_DIR/../plex/plex-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../plex/plex.yaml

kubectl apply -f $SCRIPT_DIR/../sonarr/sonarr-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../sonarr/sonarr.yaml
kubectl apply -f $SCRIPT_DIR/../radarr/radarr-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../radarr/radarr.yaml
kubectl apply -f $SCRIPT_DIR/../cleanuparr/cleanuparr-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../cleanuparr/cleanuparr.yaml

kubectl apply -f $SCRIPT_DIR/../flaresolverr/flaresolverr.yaml
kubectl apply -f $SCRIPT_DIR/../nordvpn/nordvpn-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../nordvpn/qbittorrent-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../nordvpn/prowlarr-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../nordvpn/nordvpn.yaml

kubectl apply -f $SCRIPT_DIR/../picsync/picsync-immich.yaml
kubectl apply -f $SCRIPT_DIR/../picsync/picsync-legacy.yaml
