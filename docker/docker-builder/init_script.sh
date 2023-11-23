#!/bin/bash

apt-get update 
apt-get -y dist-upgrade 

apt-get install -y ca-certificates curl gnupg lsb-release

mkdir -m 0755 -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get remove -y ca-certificates curl gnupg lsb-release
apt-get autoremove -y 
apt-get autoclean -y 

apt-get update 

apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin git 
apt-get autoremove -y 
apt-get autoclean -y 
rm -rf /tmp/* /var/cache/apt/archives/* /var/lib/apt/lists/* /var/tmp/*

(cd /opt/ ; git clone https://github.com/blablack/fawnarevagh-kube.git)

cp /opt/fawnarevagh-kube/docker/docker-builder/buildkitd.toml /etc/buildkitd.toml

export DOCKER_BUILDKIT=1

dockerd&

docker buildx create --use --config /etc/buildkitd.toml

(
  cd /opt/fawnarevagh-kube/docker/docker-builder
  docker buildx build --platform linux/amd64 --push --tag nucio.nowhere:30038/docker-builder:latest .
)