# Fawnarevagh Cloud

The Kubernetes (k3s) cluster creation and deployments for my home cloud at Fawnarevagh!

## Notes on DNS and Pi-Hole

Pi-Hole being used as the DNS can be a problem for Kubernetes to pull Pi-Hole docker images.

### Network architecture

The router will be setup with external DNS as upstream (ISP, Cloudflare, Google, etc.).
It will as well advertise Pi-Hole IP as the DNS for client getting their IP address through DHCP.

Pi-Hole's upstream will be other external DNS (ISP, Cloudflare, Google, etc.).
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
nameserver 192.168.2.200
```

and modify the service env file (`/etc/systemd/system/k3s.service.env`)

```
K3S_RESOLV_CONF=/opt/k3dvol/resolv.conf
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

### Docker registry

Create/edit file `/etc/rancher/k3s/registries.yaml`

```yaml
mirrors:
  "nucio.nowhere:30038":
    endpoint:
      - "http://nucio.nowhere:30038"
```

### k3s service

Modify the SystemD k3s service file (`/etc/systemd/system/k3s.service`) and change the ExecStart to read:

```
ExecStart=/usr/local/bin/k3s \
    server \
    --disable servicelb \
    --disable traefik \
    --disable metrics-server \
```

### Deployments

## Secrets for PiHole

```bash
echo -n '[MYPASSWORD]' > pihole_password.txt
echo -n '[MYOTHERPASSWORD]' > ssh_password.txt
echo -n '[ANOTHERPASSWORD]' > vikunja_password.txt

kubectl create secret generic pihole-webpassword --from-file=password=pihole_password.txt
kubectl create secret generic picsync-sshpassword --from-file=password=ssh_password.txt
kubectl create secret generic vikunja-password --from-file=password=vikunja_password.txt
```

## Deployments

The kubeconfig file can be found in `/etc/rancher/k3s/k3s.yaml`

```bash
kubectl apply -f ./coredns-custom/coredns-custom.yaml
kubectl apply -f ./metallb/metallb.yaml
kubectl apply -f ./registry/registry.yaml

kubectl apply -f ./pihole/pihole.yaml

kubectl apply -f ./home-assistant/home-assistant.yaml
kubectl apply -f ./node-red/node-red.yaml

kubectl apply -f ./plex/plex.yaml
kubectl apply -f ./sonarr/sonarr.yaml
kubectl apply -f ./prowlarr/prowlarr.yaml

kubectl apply -f ./kublicity/kublicity.yaml
kubectl apply -f ./picsync/picsync.yaml
```

## Debug

A Ubuntu pod can be created to debug from inside the cluster

```
kubectl apply -f ./debug_ubuntu_pod.yaml
```
