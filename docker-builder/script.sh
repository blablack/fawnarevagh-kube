#!/bin/bash

mkdir -p /docker_storage

dockerd&

(cd /opt/ ; git clone https://github.com/blablack/fawnarevagh-kube.git)

build_container () {
  (
    cd /opt/fawnarevagh-kube/$1
    echo "Build image $1 for platfrom $2"
    docker build --platform $2 -t $1 . 

    echo "Tag image"
    docker tag $1:latest nucio.nowhere:30038/$1:latest

    echo "Push image"
    docker push nucio.nowhere:30038/$1:latest
  )
}

build_container "docker-builder" "linux/amd64"
build_container "kublicity" "linux/amd64"
build_container "picsync" "linux/amd64"
build_container "nordvpn" "linux/amd64"
build_container "download-root-hints" "linux/arm64"
