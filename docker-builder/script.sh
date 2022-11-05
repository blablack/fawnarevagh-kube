#!/bin/bash

# clone or pull repo
if [ -d "fawnarevagh-kube" ] 
then
    (cd fawnarevagh-kube ; git pull)
else
    git clone https://github.com/blablack/fawnarevagh-kube.git
fi

(
    cd fawnarevagh-kube/docker-builder 
    podman --root /data build -t kublicity . 
    podman tag docker-builder:latest nucio.nowhere:30038/docker-builder:latest
    podman push nucio.nowhere:30038/docker-builder:latest
)

(
    cd fawnarevagh-kube/kublicity 
    podman --root /data build -t kublicity . 
    podman tag kublicity:latest nucio.nowhere:30038/kublicity:latest
    podman push nucio.nowhere:30038/kublicity:latest
)

(
    cd fawnarevagh-kube/picsync 
    podman --root /data build -t picsync . 
    podman tag picsync:latest nucio.nowhere:30038/picsync:latest
    podman push nucio.nowhere:30038/picsync:latest
)

(
    cd nordvpn/nordvpn
    podman --root /data build -t nordvpn . 
    podman tag nordvpn:latest nucio.nowhere:30038/nordvpn:latest
    podman push nucio.nowhere:30038/nordvpn:latest
)
