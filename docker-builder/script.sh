#!/bin/bash

# clone or pull repo
if [ -d "/data/fawnarevagh-kube" ] 
then
    (cd /data/fawnarevagh-kube ; git pull)
else
    (cd /data/ ; git clone https://github.com/blablack/fawnarevagh-kube.git)
fi

mkdir -p /data/podman

build_container () {
  (
    cd /data/fawnarevagh-kube/$1
    podman build --format docker -t $1 . 
    podman tag $1:latest nucio.nowhere:30038/$1:latest
    podman push nucio.nowhere:30038/$1:latest
  )
}

build_container "docker-builder"
build_container "kublicity"
build_container "picsync"
build_container "nordvpn"
