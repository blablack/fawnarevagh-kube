# Fawnarevagh Cloud

The Kubernetes (k3s) cluster creation and deployments for my home cloud at Fawnarevagh!

## Nodes

Nodes are running Ubuntu Server.

## Prerequisites (first-time node setup)

Before running Ansible, each node needs your SSH key and passwordless sudo.

```bash
ssh-keygen -t ed25519 -C "blablack-ssh-key"

ssh-copy-id -i ~/.ssh/id_ed25519.pub blablack@192.168.2.2
ssh-copy-id -i ~/.ssh/id_ed25519.pub blablack@192.168.2.3
```

Then on each node, add passwordless sudo (`sudo visudo`):

```
blablack ALL=(ALL) NOPASSWD:ALL
```

## Ansible

Ansible is used to setup the two nodes:

```bash
cd ansible
ansible-playbook -i hosts --ask-become-pass -u MYUSER --ask-pass ./playbook.yml
```

### Upgrading k3s

k3s itself is upgraded by re-running the official install script on each node
(what used to be a manual `ssh` in and run `./install_k3s.sh` on Nucio, then
Quario). `ansible/upgrade_k3s.yml` does both in one go:

```bash
cd ansible
ansible-playbook -i hosts --ask-become-pass -u MYUSER --ask-pass ./upgrade_k3s.yml
```

The install script is safe to re-run — it fetches the latest stable release
and only reinstalls/restarts the service when the version or flags actually
change. Quario's `K3S_TOKEN` is never stored in this repo or on disk anywhere:
the playbook reads it live from Nucio's node-token file at run time, so
there's no secret to manage or `.gitignore`.

To upgrade a single node (e.g. to check Nucio came back healthy before
touching Quario):

```bash
ansible-playbook -i hosts --ask-become-pass -u MYUSER --ask-pass ./upgrade_k3s.yml -l nucio
```

## Deployments

### Cert
```bash
kubectl get secret blinky-root-ca-secret -n cert-manager -o json \
  | jq '.metadata.namespace = "immich" | del(.metadata.resourceVersion,.metadata.uid,.metadata.creationTimestamp)' \
  | kubectl apply -f -
```

### Secrets

```bash
kubectl -n kube-system create secret generic kubeconfig --from-file=kubeconfig=PATHTOKUBECONFIG
kubectl create secret generic pihole-webpassword --from-literal password=PIHOLEPASSWORD
kubectl create secret generic picsync-sshpassword --from-literal password=SSHPASSWORD
kubectl create secret generic nordvpn-token --from-literal password=NORDVPNTOKEN
kubectl create secret generic paperless-password --from-literal=password='MYPASSWORD' --from-literal=authentik='{"openid_connect":{"APPS":[{"provider_id":"authentik","name":"Authentik","client_id":"A6CKPWyJi20famWIoxzEZvZcHEcK2N2d8jtwNQMS","secret":"SECRETKEY","settings":{"server_url":"https://authentik.nowhere/application/o/paperless/.well-known/openid-configuration"}}]}}'
kubectl create secret generic grafana-password --from-literal=password='MYPASSWORD' --from-literal=oidc_secret='OIDCSECRET'
kubectl create secret generic warracker --from-literal=oidc_secret='OIDCSECRET'
kubectl create secret generic tailscale --from-literal=TS_AUTHKEY='TAILSCALEKEY'

# ArgoCD's own OIDC connector (dex.config in argocd/patches/argocd-dex-config.yaml) reads its
# client secret from a key on the argocd-secret Secret that the base ArgoCD install already
# creates — patch it in rather than creating a new Secret:
kubectl -n argocd patch secret argocd-secret --type merge -p '{"stringData": {"dex.authentik.clientSecret": "OIDCSECRET"}}'
```

### Deployments

The kubeconfig file can be found in `/etc/rancher/k3s/k3s.yaml`

```bash
./deploy_all.sh
```

## Debug

Ubuntu pod can be created to debug from inside the cluster.

For example:

```
kubectl apply -f ./debug_ubuntu_pod.yaml
kubectl exec --stdin --tty ubuntu -- /bin/bash
```
