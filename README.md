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
kubectl create secret generic paperless-password --from-literal=password='MYPASSWORD' --from-literal=authentik='{"openid_connect":{"APPS":[{"provider_id":"authentik","name":"Authentik","client_id":"A6CKPWyJi20famWIoxzEZvZcHEcK2N2d8jtwNQMS","secret":"SECRETKEY","settings":{"server_url":"http://192.168.2.221:9000/application/o/paperless/.well-known/openid-configuration"}}]}}'
kubectl create secret generic grafana-password --from-literal=password='MYPASSWORD' --from-literal=oidc_secret='OIDCSECRET'
kubectl create secret generic warracker --from-literal=oidc_secret='OIDCSECRET'
kubectl create secret generic tailscale --from-literal=TS_AUTHKEY='TAILSCALEKEY'
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
