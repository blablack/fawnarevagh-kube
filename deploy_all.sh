#!/bin/bash

kubectl apply -f ./persistent-volumes/nasio-nfs.yaml
kubectl apply -f ./persistent-volumes/storage-local-path.yaml

kubectl apply -f ./metallb/metallb.yaml
kubectl apply -f ./metallb/metallb-config.yaml
kubectl apply -f ./registry/registry.yaml

kubectl apply -f ./docker-builder-init-jobs/build-first-docker-builder.yaml
kubectl wait --timeout=-1s --for=condition=Complete job/build-first-docker-builder

kubectl apply -f ./download-root-hints/download-root-hints.yaml
kubectl apply -f ./pihole/pihole.yaml

kubectl apply -f ./docker-builder-jobs/build-docker-builder.yaml
kubectl apply -f ./docker-builder-jobs/build-download-root-hints.yaml
kubectl apply -f ./docker-builder-jobs/build-kublicity.yaml
kubectl apply -f ./docker-builder-jobs/build-nordvpn.yaml
kubectl apply -f ./docker-builder-jobs/build-picsync.yaml

kubectl apply -f ./deployment-restarter/deployment-restarter-rbac.yaml
kubectl apply -f ./deployment-restarter/deployment-restarter-torrent-vpn.yaml
kubectl apply -f ./deployment-restarter/deployment-restarter-nordvpn-meshnet.yaml
kubectl apply -f ./deployment-restarter/deployment-restarter-pihole.yaml
kubectl apply -f ./deployment-restarter/deployment-restarter-plex.yaml
kubectl apply -f ./deployment-restarter/deployment-restarter-sonarr.yaml
kubectl apply -f ./deployment-restarter/deployment-restarter-radarr.yaml
kubectl apply -f ./deployment-restarter/deployment-restarter-home-assistant.yaml

kubectl apply -f ./nordvpn-meshnet/nordvpn-meshnet.yaml

kubectl apply -f ./home-assistant/home-assistant.yaml
kubectl apply -f ./node-red/node-red.yaml

kubectl apply -f ./plex/plex.yaml
kubectl apply -f ./sonarr/sonarr.yaml
kubectl apply -f ./radarr/radarr.yaml
kubectl apply -f ./torrent-vpn/torrent-vpn.yaml

kubectl apply -f ./kublicity/kublicity_full_nucio.yaml
kubectl apply -f ./kublicity/kublicity_clean_nucio.yaml
kubectl apply -f ./kublicity/kublicity_incr_nucio.yaml
kubectl apply -f ./kublicity/kublicity_full_raspio.yaml
kubectl apply -f ./kublicity/kublicity_clean_raspio.yaml
kubectl apply -f ./kublicity/kublicity_incr_raspio.yaml
kubectl apply -f ./picsync/picsync.yaml
