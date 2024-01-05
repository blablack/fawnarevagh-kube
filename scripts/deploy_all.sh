#!/bin/bash

kubectl apply -f ../metallb/metallb-config.yaml
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.12/config/manifests/metallb-native.yaml

kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.5.3/deploy/longhorn.yaml
kubectl apply -f ../longhorn/longhorn.yaml

kubectl apply -f ../persistent-volumes/nasio-nfs.yaml
kubectl apply -f ../persistent-volumes/longhorn.yaml

kubectl apply -f ../registry/registry-pvc.yaml
kubectl apply -f ../registry/registry.yaml

kubectl apply -f ../download-root-hints/download-root-hints.yaml
kubectl apply -f ../pihole/pihole.yaml

kubectl apply -f ../dnsmasq/dnsmasq-pvc.yaml
kubectl apply -f ../dnsmasq/dnsmasq.yaml

kubectl apply -f ../jenkins/jenkins-pvc.yaml
kubectl apply -f ../jenkins/jenkins.yaml

kubectl apply -f ../syncthing/syncthing-aurelien-pvc.yaml
kubectl apply -f ../syncthing/syncthing-aurelien.yaml
kubectl apply -f ../syncthing/syncthing-yvonne-pvc.yaml
kubectl apply -f ../syncthing/syncthing-yvonne.yaml

kubectl apply -f ../immich/immich-pvc.yaml
kubectl apply -f ../immich/immich.yaml

kubectl apply -f ../heimdall/heimdall-pvc.yaml
kubectl apply -f ../heimdall/heimdall.yaml

kubectl apply -f ../home-assistant/home-assistant-pvc.yaml
kubectl apply -f ../home-assistant/home-assistant.yaml
kubectl apply -f ../node-red/node-red-pvc.yaml
kubectl apply -f ../node-red/node-red.yaml

kubectl apply -f ../plex/plex-pvc.yaml
kubectl apply -f ../plex/plex.yaml
kubectl apply -f ../sonarr/sonarr-pvc.yaml
kubectl apply -f ../sonarr/sonarr.yaml
kubectl apply -f ../radarr/radarr-pvc.yaml
kubectl apply -f ../radarr/radarr.yaml
kubectl apply -f ../nordvpn/nordvpn-pvc.yaml
kubectl apply -f ../nordvpn/nordvpn.yaml
kubectl apply -f ../qbittorrent/qbittorrent-pvc.yaml
kubectl apply -f ../qbittorrent/qbittorrent.yaml
kubectl apply -f ../prowlarr/prowlarr-pvc.yaml
kubectl apply -f ../prowlarr/prowlarr.yaml

kubectl apply -f ../picsync/picsync.yaml
