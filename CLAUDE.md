# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a home Kubernetes (k3s) cluster configuration repo ("Fawnarevagh Cloud"). It manages two nodes (`nucio` at 192.168.2.2 and `quario` at 192.168.2.3) running Ubuntu Server, plus custom Docker images and Tdarr media processing plugins.

## Cluster Architecture

**Two-node k3s cluster:**
- `nucio` — control plane (master)
- `quario` — worker (agent)
- NAS at 192.168.2.4 (`nasio`) provides NFS storage mounted as `nasio-nfs-pvc`
- Local Docker registry at `nucio.nowhere:30038` for custom images

**Deployment model — two layers:**
1. **Bootstrap** (`scripts/deploy_all.sh`): Run once to install infrastructure that ArgoCD itself cannot manage — MetalLB, Longhorn, cert-manager, persistent volumes, Intel GPU plugin, ArgoCD itself, and Prometheus.
2. **ArgoCD GitOps** (`argocd/argocd-applicationset.yaml`): After bootstrap, ArgoCD watches this repo and auto-syncs every top-level directory (except `argocd`, `ansible`, `docker`, `persistent-volumes`, `scripts`, `intel-gpu-plugin`, `prometheus`) as a separate Application, using `selfHeal: true` and `prune: false`.

**Storage:**
- Longhorn (replicated block storage) — used for most app PVCs
- NFS (`nasio-nfs-pvc`, ReadWriteMany) — shared media storage for Tdarr, Radarr, Sonarr, qBittorrent, etc.
- Each app typically has its own `<app>-pvc.yaml` alongside the main `<app>.yaml`

**Networking:**
- MetalLB for LoadBalancer IPs; Traefik gets 192.168.2.220
- External-DNS for DNS automation
- Pi-hole for local DNS
- Tailscale for remote access
- NordVPN pod runs as a sidecar/gateway for Prowlarr and qBittorrent (both run inside the `nordvpn` deployment pod)

## Key Commands

### Node setup (first time only)
```bash
cd ansible
ansible-playbook -i hosts --ask-become-pass -u MYUSER --ask-pass ./playbook.yml
```

### Bootstrap cluster (first time only)
```bash
./scripts/deploy_all.sh
```
After this, ArgoCD takes over syncing all other apps from git.

### Interact with pods
```bash
# Open a shell in a pod by app label
./scripts/bash_to_container.sh <app-name>
# With specific container
./scripts/bash_to_container.sh <app-name> <container-name>

# Debug pod inside the cluster
kubectl apply -f ./debug-ubuntu-pod.yaml
kubectl exec --stdin --tty ubuntu -- /bin/bash
```

### Registry management
```bash
# Delete an image and all its tags from the local registry
./scripts/delete_from_registry.sh <image-name>
```

## Custom Docker Images

Three custom images are built and pushed to `nucio.nowhere:30038`:

| Image | Directory | Purpose |
|---|---|---|
| `tdarr` | `docker/tdarr/` | Tdarr server with Jellyfin FFmpeg, dovi_tool, hdr10plus_tool, MP4Box, and local plugins baked in |
| `tdarr_node` | `docker/tdarr_node/` | Tdarr worker node (same tools) |
| `nordvpn` | `docker/nordvpn/` | NordVPN with Prowlarr + qBittorrent sidecar logic |

The tdarr deployment uses an **init container** to copy plugins from the image into the server's plugin directory on startup (so plugin updates take effect by restarting the pod).

## Tdarr Local Flow Plugins

Plugins live in `docker/tdarr/LocalFlowPlugins/` and are compiled JavaScript (TypeScript transpiled). They're organized by category:

- `DoVi/` — ~15 plugins for Dolby Vision processing (check profile, extract/inject RPU, package MP4, convert p5→p8, p7→p8, etc.)
- `DoVi_5_to_8/` — DoVi Profile 5 to Profile 8 conversion pipeline
- `Audio/` — Audio processing (e.g., `convertOpusAudio`)
- `shield_flow.json` — The main Tdarr flow definition wiring these plugins together

All plugins follow the same pattern: export `details()` (metadata) and `plugin()` (async function receiving `args`). They use shared helpers from `FlowHelpers/1.0.0/cliUtils` and `FlowHelpers/1.0.0/fileUtils` (provided by the base Tdarr image).

## Secrets

Secrets are created manually with `kubectl create secret` — they are not stored in git. Key secrets referenced by deployments:

- `kubeconfig` (kube-system) — kubeconfig file
- `pihole-webpassword`, `picsync-sshpassword`, `nordvpn-token`
- `paperless-password` — includes OIDC config JSON
- `grafana-password` — includes OIDC secret
- `warracker` — OIDC secret
- `tailscale` — Tailscale auth key
