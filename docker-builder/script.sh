#!/bin/bash

dockerd&

# clone or pull repo
if [ -d "/data/fawnarevagh-kube" ] 
then
    (cd /data/fawnarevagh-kube ; git pull)
else
    (cd /data/ ; git clone https://github.com/blablack/fawnarevagh-kube.git)
fi

#mkdir -p /data/podman

build_container () {
  (
    cd /data/fawnarevagh-kube/$1
    echo "Build image $1"
    docker build -t $1 . 

    echo "Tag image"
    docker tag $1:latest nucio.nowhere:30038/$1:latest

    echo "Push image"
    docker push nucio.nowhere:30038/$1:latest
  )
}

build_container "docker-builder"
build_container "kublicity"
build_container "picsync"
build_container "nordvpn"
