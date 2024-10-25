#!/bin/bash

for resolv_file in $(find /var/lib/rancher/k3s/agent/containerd/io.containerd.grpc.v1.cri/sandboxes/ -name resolv.conf); do
  chattr -i -e ${resolv_file}
done