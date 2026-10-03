---
name: check-pinned-versions
description: Check whether the 7 hardcoded/pinned upstream versions in this repo (authentik, external-dns, intel-gpu-plugin, the pod-cleanup kubectl image, and the metallb/longhorn/cert-manager URLs in scripts/deploy_all.sh) are current, and update any that are behind. Use when the user asks to check for updates, check pinned versions, or update authentik/external-dns/intel-gpu-plugin/kubectl/metallb/longhorn/cert-manager.
---

# Check pinned versions

Everything else in this repo tracks `:latest` with `imagePullPolicy: Always` (see
CLAUDE.md). These 7 are the deliberate exceptions — pinned because they're either
core cluster infra (bootstrap script), apps where an unreviewed auto-upgrade would
be risky (auth provider, DNS automation, GPU driver plugin), or images that don't
publish a `:latest` tag at all (kubectl). Nothing else auto-updates
them, so they drift silently until someone checks.

## The 7 pinned versions

| # | Component | File | Current version pattern | Upstream repo |
|---|---|---|---|---|
| 1 | authentik | `authentik/authentik.yaml` | `image: ghcr.io/goauthentik/server:X.Y.Z` (appears **twice** — server + worker container, always kept identical) | `goauthentik/authentik` |
| 2 | external-dns | `external-dns/external-dns.yaml` | `image: registry.k8s.io/external-dns/external-dns:vX.Y.Z` | `kubernetes-sigs/external-dns` |
| 3 | intel-gpu-plugin | `intel-gpu-plugin/kustomization.yaml` | `?ref=vX.Y.Z` (single kustomize remote base — the plain `gpu_plugin` deployment, no NFD overlay) | `intel/intel-device-plugins-for-kubernetes` |
| 4 | metallb | `scripts/deploy_all.sh` | `.../metallb/metallb/vX.Y.Z/config/manifests/metallb-native.yaml` | `metallb/metallb` |
| 5 | longhorn | `scripts/deploy_all.sh` | `.../longhorn/longhorn/vX.Y.Z/deploy/longhorn.yaml` | `longhorn/longhorn` |
| 6 | cert-manager | `scripts/deploy_all.sh` | `.../cert-manager/releases/download/vX.Y.Z/cert-manager.yaml` | `cert-manager/cert-manager` |
| 7 | kubectl (pod-cleanup) | `pod-cleanup/pod-cleanup.yaml` | `image: registry.k8s.io/kubectl:vX.Y.Z` | — see below, **not** the newest upstream |

Don't trust the version numbers above — they're patterns, not current values. Always
re-read the actual pinned version from the file at run time (`grep` for the pattern in
that row) before comparing to upstream.

## Workflow

For each of the 7 (kubectl is the exception to steps 2-3 — see its bullet in step 2):

1. **Extract the current pinned version** from the file with `grep`/`Read`.
2. **Find the latest upstream release.** Load `WebFetch` (it's a deferred tool — call
   `ToolSearch` for it first if not already available) and hit
   `https://api.github.com/repos/<org>/<repo>/releases/latest`.
   - **Don't trust a response just because it returned 200.** Some repos run more than
     one release train through the same `/releases` endpoint (e.g. a core release next
     to a Helm chart release, or a monorepo with per-component tags), and
     `/releases/latest` reflects whichever was *published* most recently — not
     necessarily the one whose tag shape matches what's pinned in this repo. Before
     trusting the result, check that its tag matches the pattern already in the file
     (row above) — same prefix/suffix shape, not just "looks like a version". If it
     doesn't match (or the endpoint 404s because the repo only uses plain tags, no
     GitHub Release objects), fall back to `https://api.github.com/repos/<org>/<repo>/tags`
     (or `/releases` unpaginated) and filter to tags matching that exact shape yourself.
   - **metallb specifically** does this: `/releases/latest` tends to return a
     `metallb-chart-X.Y.Z` Helm chart release rather than the bare `vX.Y.Z` core tag
     that `deploy_all.sh`'s raw-manifest URL needs. Go straight to
     `https://api.github.com/repos/metallb/metallb/tags` and take the newest tag
     matching `^v[0-9]`.
   - **kubectl** doesn't follow upstream latest: it must stay within one minor version
     of the cluster (`kubectl get nodes` VERSION, e.g. `v1.36.5+k3s1` → 1.36). Target
     the newest patch of the cluster's minor from
     `curl -sL https://registry.k8s.io/v2/kubectl/tags/list` (plain `vX.Y.Z` tags only).
     Its command (`kubectl delete pods` with selectors) is stable, so a lag is harmless
     — only report it as behind once the cluster has moved to a different minor.
   - Skip pre-releases / release candidates (`-rc`, `-beta`, `-alpha` suffixes) unless
     that's literally the only thing published.
   - Compare **as semver** (`v0.9.0` < `v0.10.0`), not as strings.
   - For authentik specifically, cross-check the tag against the published image tags
     at `ghcr.io/goauthentik/server` (e.g. via the repo's `pkgs/container/server` page)
     — the release tag naming has drifted before (`version/2026.8.1` as the git tag vs.
     `2026.8.1` as the image tag) and doesn't always equal the image tag verbatim.
3. **Skim the release notes** for the versions between current and latest (GitHub's
   compare view or the release body) for anything flagged as a breaking change,
   migration step, or deprecation. Note it in the report even if you still apply the
   version bump — don't silently swallow a breaking-change warning.
4. **If behind, update the file(s):**
   - authentik: edit the image tag with `replace_all: true` so both occurrences move
     together.
   - intel-gpu-plugin: edit `?ref=vOLD` → `?ref=vNEW` (one occurrence; use `replace_all: true`
     anyway in case more remote bases get added later).
   - external-dns / kubectl / metallb / longhorn / cert-manager: single targeted edit.
   - Do **not** run `scripts/deploy_all.sh`, `kubectl apply`, or commit/push anything —
     this only edits the working tree. Applying is the user's call (bootstrap-layer
     changes aren't covered by ArgoCD selfHeal, so a stale live cluster won't
     self-correct — ArgoCD only auto-syncs top-level app directories, not `scripts/`
     or the infra it applies).

## Report format

Finish with one table covering all 7, even the ones already current:

| Component | Current | Latest | Status | Notes |
|---|---|---|---|---|
| authentik | 2026.8.0 | 2026.8.0 | ✅ up to date | |
| external-dns | v0.22.0 | v0.23.0 | ⬆️ updated | |
| intel-gpu-plugin | v0.36.0 | v0.36.0 | ✅ up to date | |
| metallb | v0.16.1 | v0.16.1 | ✅ up to date | |
| longhorn | v1.12.1 | v1.13.0 | ⬆️ updated | check volume migration notes before applying |
| cert-manager | v1.21.1 | v1.21.1 | ✅ up to date | |
| kubectl | v1.36.5 | v1.36.5 | ✅ matches cluster 1.36 | |

Then remind the user: files were edited in the working tree only; re-run the relevant
part of `scripts/deploy_all.sh` (or `kubectl apply -f <url>` for that one component)
to actually roll it out, and commit the version bump once applied and verified.
