# Fawnarevagh Cloud

The Kubernetes (k3s) cluster creation and deployments for my home cloud at Fawnarevagh!

## Nodes

Nodes are running Ubuntu Server.

## Ansible

Ansible is used to setup the two nodes:

```bash
cd ansible
ansible-playbook -i hosts --ask-become-pass -u MYUSER --ask-pass ./playbook.yml
```

### Ansible Lumio
```bash
cd ansible
ansible-playbook --limit lumio.nowhere -i hosts --ask-become-pass -u MYUSER --ask-pass ./lumio.yml --extra-vars "wifi_ssid=MYWIFISSID wifi_password=MYWIFIPASSWORD"
```

## Deployments

### Secrets

```bash
kubectl -n kube-system create secret generic kubeconfig --from-file=kubeconfig=PATHTOKUBECONFIG
kubectl create secret generic pihole-webpassword --from-literal password=PIHOLEPASSWORD
kubectl create secret generic picsync-sshpassword --from-literal password=SSHPASSWORD
kubectl create secret generic nordvpn-token --from-literal password=NORDVPNTOKEN
kubectl create secret generic paperless-password --from-literal password=PAPERLESSPASSWORD
kubectl create secret generic uptime-kuma-credentials --from-literal=username=USERNAME --from-literal=password=PASSWORD
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
