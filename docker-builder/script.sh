#!/bin/bash

# clone or pull repo
if [ -d "/data/fawnarevagh-kube" ] 
then
    (cd /data/fawnarevagh-kube ; git pull)
else
    (cd /data/ ; git clone https://github.com/blablack/fawnarevagh-kube.git)
fi

mkdir -p /data/podman

(
    cd /data/fawnarevagh-kube/docker-builder 
    podman build -t docker-builder . 
    podman tag docker-builder:latest nucio.nowhere:30038/docker-builder:latest
    podman push nucio.nowhere:30038/docker-builder:latest
)

(
    cd /data/fawnarevagh-kube/kublicity 
    podman build -t kublicity . 
    podman tag kublicity:latest nucio.nowhere:30038/kublicity:latest
    podman push nucio.nowhere:30038/kublicity:latest
)

(
    cd /data/fawnarevagh-kube/picsync 
    podman build -t picsync . 
    podman tag picsync:latest nucio.nowhere:30038/picsync:latest
    podman push nucio.nowhere:30038/picsync:latest
)

(
    cd /data/fawnarevagh-kube/nordvpn
    podman build -t nordvpn . 
    podman tag nordvpn:latest nucio.nowhere:30038/nordvpn:latest
    podman push nucio.nowhere:30038/nordvpn:latest
)
