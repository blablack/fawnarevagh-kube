#!/bin/bash

export DOCKER_BUILDKIT=1

dockerd&

docker buildx create --use --config /etc/buildkitd.toml

(cd /opt/ ; git clone https://github.com/blablack/fawnarevagh-kube.git)

echo "Build image $1 for platfrom $2"

(
  cd /opt/fawnarevagh-kube/$1
  echo "Build image $1 for platfrom $2"
  docker buildx build --platform $2 --push --tag nucio.nowhere:30038/$1:latest .
)
