#!/bin/bash

mkdir -p /docker_storage

dockerd&

(cd /opt/ ; git clone https://github.com/blablack/fawnarevagh-kube.git)

build_container () {
  (
    cd /opt/fawnarevagh-kube/$1
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
