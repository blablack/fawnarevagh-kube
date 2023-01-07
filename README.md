# Fawnarevagh Cloud

The Kubernetes (k3s) cluster creation and deployments for my home cloud at Fawnarevagh!

## Notes on DNS and Pi-Hole

Pi-Hole being used as the DNS can be a problem for Kubernetes to pull Pi-Hole docker images.

### Network architecture

The router will be setup with external DNS as upstream (ISP, Cloudflare, Google, etc.).
It will as well advertise Pi-Hole IP as the DNS for client getting their IP address through DHCP.

Pi-Hole's upstream Unbound IP address.
In addition it will conditionally forward to the router's IP for local queries.

All clients (DHCP and fixed IP) should be configured to have Pi-Hole as DNS.
This should resolve public internet and local network hostnames.

Kubernetes host should be configured to use router as DNS.
This setup should only be used by Kubernetes host to resolve when pulling container images.

### Host configuration

Our server will use Netplan for network configuration.
Netplan will be configured to not use the DNS server advertised by the router but PiHole instead.

### CoreDNS configuration

CoreDNS in k3s will be configured to use PiHole as the DNS server.

Create the following file `/opt/k3dvol/resolv.conf`

```
nameserver 192.168.2.201
```

## Netplan

Our server will use ethernet and wifi as a backup network.
In addition, it will override the DNS IP advertised by the router.

Update the configuration file in `/etc/netplan/`

```
network:
  version: 2
  ethernets:
    eno1:
      dhcp4: no
  wifis:
    wlp2s0:
      dhcp4: no
      access-points:
        "MYSSID":
          password: "MYWIFIPASSORD"
  bonds:
    bond0:
      dhcp4: yes
      interfaces: [ eno1, wlp2s0 ]
      dhcp4-overrides:
        use-dns: false
      nameservers:
        addresses: [ 192.168.2.1 ]
      parameters:
        primary: eno1
        mode: active-backup
        transmit-hash-policy: layer3+4
        mii-monitor-interval: 1

```

## Setup

### Install NFS

```bash
sudo apt install nfs-common
```

### Install k3s

Use this command to install/configure k3s.

```bash
curl -sfL https://get.k3s.io | K3S_RESOLV_CONF="/opt/k3dvol/resolv.conf" INSTALL_K3S_EXEC="--tls-san nucio.nowhere --disable servicelb --disable traefik --disable metrics-server" sh -s
```

### Docker registry

Create/edit file `/etc/rancher/k3s/registries.yaml`

```yaml
mirrors:
  "nucio.nowhere:30038":
    endpoint:
      - "http://nucio.nowhere:30038"
```

And restart k3s after this change.

```bash
systemctl restart k3s
```

### Deployments

## Secrets for PiHole

```bash
echo -n '[MYPASSWORD]' > pihole_password.txt
echo -n '[MYOTHERPASSWORD]' > ssh_password.txt
echo -n '[NORDVPNTOKEN]' > nordvpn_token.txt

kubectl create secret generic pihole-webpassword --from-file=password=pihole_password.txt
kubectl create secret generic picsync-sshpassword --from-file=password=ssh_password.txt
kubectl create secret generic nordvpn-token --from-file=password=nordvpn_token.txt
```

## Deployments

The kubeconfig file can be found in `/etc/rancher/k3s/k3s.yaml`

```bash
kubectl apply -f ./metallb/metallb.yaml
kubectl apply -f ./registry/registry.yaml

kubectl apply -f ./persistent-volumes/nfs-persistent-volume.yaml
kubectl apply -f ./persistent-volumes/config-persistent-volume.yaml

kubectl apply -f ./unbound/unbound.yaml
kubectl apply -f ./pihole/pihole.yaml

kubectl apply -f ./docker-builder/docker-builder.yaml

kubectl apply -f ./home-assistant/home-assistant.yaml
kubectl apply -f ./node-red/node-red.yaml

kubectl apply -f ./plex/plex.yaml
kubectl apply -f ./sonarr/sonarr.yaml
kubectl apply -f ./prowlarr/prowlarr.yaml
kubectl apply -f ./tdarr/tdarr.yaml
kubectl apply -f ./qbittorrent-nordvpn/qbittorrent-nordvpn.yaml

kubectl apply -f ./kublicity/kublicity.yaml
kubectl apply -f ./picsync/picsync.yaml
```

## Debug

Ubuntu and Podman pods can be created to debug from inside the cluster.

For example:

```
kubectl apply -f ./debug_ubuntu_pod.yaml
kubectl exec --stdin --tty ubuntu -- /bin/bash
```
