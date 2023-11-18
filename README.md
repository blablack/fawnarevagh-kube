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

Create the following file `/opt/k3dvol/resolv.conf` on each node.

```
nameserver 192.168.2.201
```

## Netplan

Our servers use Netplan for the network configuration.
Let's update it to override the DNS IP advertised by the router.

Here is an example of a configuration file found in `/etc/netplan/`

```
network:
  version: 2
  ethernets:
    eno1:
      dhcp4: yes
      dhcp4-overrides:
        use-dns: false
      nameservers:
        addresses: [ 192.168.2.1 ]
```

## Setup

### Install NFS

```bash
sudo apt install nfs-common
```

### Setup resolved.conf
Edit /etc/systemd/resolved.conf 
- change the DNS= value to 1.1.1.1
- change the value of the DNSStubListener= to no

then:
```
sudo ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
```

### Install k3s

Use this command to install/configure k3s Server.

```bash
curl -sfL https://get.k3s.io | K3S_RESOLV_CONF="/opt/k3dvol/resolv.conf" INSTALL_K3S_EXEC="--tls-san nucio.nowhere --disable servicelb --disable traefik --disable metrics-server" sh -s
```

Use this command to install/configure k3s Agent.
The token can be found on the server in this file: `/var/lib/rancher/k3s/server/node-token`

```bash
curl -sfL https://get.k3s.io | K3S_URL=https://nucio.nowhere:6443 K3S_RESOLV_CONF="/opt/k3dvol/resolv.conf" K3S_TOKEN=XXXTOKEN sh -s
```

### Label nodes

```bash
kubectl label nodes nucio cputype=x86
kubectl label nodes raspio cputype=arm
```

### Docker registry

Create/edit file `/etc/rancher/k3s/registries.yaml` for each node.

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

or

```bash
systemctl restart k3s-agent
```

## Deployments

### Intel GPU

```bash
kubectl apply -k 'https://github.com/intel/intel-device-plugins-for-kubernetes/deployments/gpu_plugin?ref=main'
```

To share the device between pods, use the `-shared-dev-nul` argument.

```
KUBE_EDITOR=nano kubectl edit ds/intel-gpu-plugin
```

and add `args: ["-shared-dev-num","5"]` to the container section.
Change the number '5' to the amount necessary.

### Secrets

```bash
kubectl create secret generic pihole-webpassword --from-literal password=PIHOLEPASSWORD
kubectl create secret generic picsync-sshpassword --from-literal password=SSHPASSWORD
kubectl create secret generic nordvpn-token --from-literal password=NORDVPNTOKEN
```

### Deployments

The kubeconfig file can be found in `/etc/rancher/k3s/k3s.yaml`

```bash
./deploy_all.sh
```

## Debug

Ubuntu and Podman pods can be created to debug from inside the cluster.

For example:

```
kubectl apply -f ./debug_ubuntu_pod.yaml
kubectl exec --stdin --tty ubuntu -- /bin/bash
```
