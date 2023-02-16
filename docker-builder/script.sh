#!/bin/bash

export DOCKER_BUILDKIT=1

#mkdir -p /docker_storage

dockerd&

docker buildx create --use --config /etc/buildkitd.toml

(cd /opt/ ; git clone https://github.com/blablack/fawnarevagh-kube.git)

build_container () {
  (
    cd /opt/fawnarevagh-kube/$1
    echo "Build image $1 for platfrom $2"
    docker buildx build --platform $2 --push --tag nucio.nowhere:30038/$1:latest .
  )
}

build_container "docker-builder" "linux/amd64"
build_container "kublicity" "linux/amd64"
build_container "picsync" "linux/amd64"
build_container "nordvpn" "linux/amd64"
build_container "download-root-hints" "linux/arm64"
