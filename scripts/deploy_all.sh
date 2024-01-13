#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

kubectl apply -f $SCRIPT_DIR/../metallb/metallb-config.yaml
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.12/config/manifests/metallb-native.yaml

kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.5.3/deploy/longhorn.yaml
kubectl apply -f $SCRIPT_DIR/../longhorn/longhorn.yaml

kubectl apply -f $SCRIPT_DIR/../persistent-volumes/nasio-nfs.yaml
kubectl apply -f $SCRIPT_DIR/../persistent-volumes/longhorn.yaml

kubectl apply -f $SCRIPT_DIR/../registry/registry-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../registry/registry.yaml

kubectl apply -f $SCRIPT_DIR/../pihole/pihole.yaml

kubectl apply -f $SCRIPT_DIR/../dnsmasq/dnsmasq-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../dnsmasq/dnsmasq.yaml

kubectl apply -f $SCRIPT_DIR/../jenkins/jenkins-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../jenkins/jenkins.yaml

kubectl apply -f $SCRIPT_DIR/../syncthing/syncthing-aurelien-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../syncthing/syncthing-aurelien.yaml
kubectl apply -f $SCRIPT_DIR/../syncthing/syncthing-yvonne-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../syncthing/syncthing-yvonne.yaml

kubectl apply -f $SCRIPT_DIR/../immich/immich-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../immich/immich.yaml

kubectl apply -f $SCRIPT_DIR/../heimdall/heimdall-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../heimdall/heimdall.yaml

kubectl apply -f $SCRIPT_DIR/../homer/homer-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../homer/homer.yaml

kubectl apply -f $SCRIPT_DIR/../paperless/paperless-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../paperless/paperless.yaml

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
kubectl apply -f $SCRIPT_DIR/../nordvpn/nordvpn-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../nordvpn/nordvpn.yaml
kubectl apply -f $SCRIPT_DIR/../qbittorrent/qbittorrent-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../qbittorrent/qbittorrent.yaml
kubectl apply -f $SCRIPT_DIR/../prowlarr/prowlarr-pvc.yaml
kubectl apply -f $SCRIPT_DIR/../prowlarr/prowlarr.yaml

kubectl apply -f $SCRIPT_DIR/../picsync/picsync-immich.yaml
kubectl apply -f $SCRIPT_DIR/../picsync/picsync-legacy.yaml