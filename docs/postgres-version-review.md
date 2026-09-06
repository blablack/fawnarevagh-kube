# PostgreSQL version review (2026-09-06)

Six deployments in this repo run their own embedded Postgres container with a hardcoded
image tag. This is a one-time audit of each against what upstream currently ships/recommends,
plus a recommendation on whether to bump.

## Summary

| App | Current image | Current major | Upstream recommends | Action needed? |
|---|---|---|---|---|
| `authentik` | `postgres:16-alpine` | 16 | 16-alpine (current official compose) | **No** — already matches upstream |
| `warracker` | `postgres:15-alpine` | 15 | 15-alpine (current official compose) | **No** — already matches upstream |
| `immich` | `ghcr.io/immich-app/postgres:16-vectorchord0.5.3-pgvector0.8.1` | 16 | Officially still ships 14 (deliberately frozen); 16/17/18 confirmed working | **No** — already ahead of upstream's own default. Optional: bump the vectorchord/pgvector extension build (see below) |
| `mealie` | `postgres:15` | 15 | `postgres:17` (current docs example) | **Optional** — 15 is fine and in support until Nov 2027, but 17 is what's documented/tested now |
| `vikunja` | `postgres:15` | 15 | `postgres:18` (current docs example) | **Optional** — minimum requirement is only 12+; no upstream deprecation of 15 found |
| `paperless-ngx` | `postgres:16` | 16 | `postgres:18` (current `docker-compose.postgres.yml`) | **Worth doing** — upstream moved the default Postgres data path in a recent release, so drifting further behind makes a future forced upgrade messier |

None of these are urgent from a support/EOL standpoint — see the Postgres EOL table below. This
is a "nice to do during a maintenance window" list, not a fire drill.

### Postgres upstream support (EOL) reference

| Version | EOL |
|---|---|
| 18 | Nov 2030 |
| 17 | Nov 2029 |
| 16 | Nov 2028 |
| 15 | Nov 2027 |
| 14 | Nov 2026 |
| 13 | EOL (Nov 2025) — nothing in this repo uses it |

Nothing here is on an unsupported major version. The oldest in use is 15, supported for another ~14 months.

---

## How a major-version bump actually has to happen

This matters because **none of these are safe to fix by just editing the image tag.** Postgres
data files are not forward-compatible across major versions — a `postgres:18` binary refuses to
start against a `postgres:15` data directory. All six deployments mount the data dir at a fixed
path (`/var/lib/postgresql/data`, via `subPath` on the app's PVC), so swapping the tag in place
would just crash-loop the pod.

The generic safe procedure (small homelab-scale DBs, so `pg_dumpall`/restore is simplest — no
need for `pg_upgrade` machinery):

1. `./scripts/stop_argocd.sh` if the app is ArgoCD-managed (so selfHeal doesn't fight you), or
   just `kubectl scale deploy/<app> --replicas=0` isn't enough since postgres runs as a sidecar
   container in the same pod as the app — you need the *old* image still running to dump from.
2. With the old container still up: `kubectl exec` in and run
   `pg_dumpall -U <user> > /tmp/backup.sql` (or `pg_dump -Fc` for just the one DB).
   Copy it out with `kubectl cp`.
3. Bump the image tag in the app's yaml. `mealie` and `vikunja` already namespace their data dir
   by version (`subPath: postgresql_15`) — bump that too (e.g. `postgresql_17`) so the new major
   version starts against an empty directory rather than the old one. `authentik`, `immich`,
   `paperless`, and `warracker` use an unversioned `subPath: postgresql`, so for those you'd want
   to rename the subPath (or point at a fresh PVC) to get a clean init, keeping the old path as a
   fallback until the restore is verified.
4. Let the new container initialize, then restore: `kubectl cp` the dump back in and
   `psql -U <user> -d <db> -f backup.sql` (or `pg_restore` for a custom-format dump).
5. Verify the app works, then `./scripts/start_argocd.sh` and clean up the old data dir/subPath
   once you're confident.

---

## Per-app detail

### authentik

- Current: `postgres:16-alpine` (`authentik/authentik.yaml:40`)
- Upstream's current official `docker-compose.yml` (fetched from docs.goauthentik.io) uses the
  same `docker.io/library/postgres:16-alpine`. Minimum supported version is documented as 14+.
- **No change needed.** This one's already tracking upstream.

### immich

- Current: `ghcr.io/immich-app/postgres:16-vectorchord0.5.3-pgvector0.8.1` (`immich/immich.yaml:37`)
- Immich's own `docker-compose.yml` still pins Postgres **14** — not because 16+ doesn't work,
  but because the maintainers have explicitly said they "shipped with 14 and don't plan to
  update it until we have a path for everyone to do so" ([discussion #25355](https://github.com/immich-app/immich/discussions/25355)).
  A maintainer confirmed 18 with the latest vectorchord build works fine for anyone not on the
  stock compose file.
- This deployment is already on 16, i.e. **ahead of** immich's own shipped default. No action
  needed on the Postgres major version.
- Minor note, not what you asked about but flagged since it's the same image: the `base-images`
  registry now publishes `16-vectorchord1.1.1-pgvector0.8.5`, `17-...`, and `18-...` builds —
  this deployment's `vectorchord0.5.3` is a few extension releases behind. Optional bump, no
  urgency, and it's an extension version rather than a Postgres major version.

### mealie

- Current: `postgres:15` (`mealie/mealie.yaml:31`), data at `subPath: postgresql_15`
- Mealie's install docs (`docs.mealie.io/.../installation/postgres/`) currently show
  `postgres:17` as the example image. A maintainer confirmed in
  [discussion #5481](https://github.com/mealie-recipes/mealie/discussions/5481) that the sample
  compose file just hadn't been updated for a while, and 17 is what they'd point people at now
  (15/16 also still work fine — no hard requirement).
- **Optional.** 15 remains in upstream Postgres support until Nov 2027. Worth bumping to 17
  next time this deployment gets touched, mostly to stay off a version that's 2 majors behind
  what's documented.

### paperless-ngx

- Current: `postgres:16` (`paperless/paperless.yaml:43`), data at unversioned `subPath: postgresql`
- Upstream's `docker/compose/docker-compose.postgres.yml` now specifies `postgres:18`.
- There's an added wrinkle here beyond just the version number: a paperless-ngx commit
  ([#11084](https://github.com/paperless-ngx/paperless-ngx)) changed the default Postgres data
  path in their reference compose file, which is what prompted
  [discussion #11678](https://github.com/paperless-ngx/paperless-ngx/discussions/11678) ("place
  to put hints for Postgres DB update v16 => v18") — other self-hosters going through this same
  16→18 jump have needed to combine the dump/restore with a data-path change, matching the
  procedure above.
- **Worth doing**, not urgent. This is the one that's furthest behind (2 majors) of the ones with
  an unversioned data path, and the repo already has a one-off recovery pod pattern
  (`postgres-recovery.yaml`) that could be adapted for the dump/restore step if useful.

### vikunja

- Current: `postgres:15` (`vikunja/vikunja.yaml:41`), data at `subPath: postgresql_15`
- Vikunja's documented minimum is Postgres 12+, and the current "Full docker example" in their
  docs uses `postgres:18`. I did not find any upstream statement that vikunja itself is dropping
  15 support — a "postgres 15 deprecated" reference that turned up in search is from a third-party
  app catalog (TrueNAS Apps), not vikunja upstream.
- **Optional.** Same reasoning as mealie: not urgent, but 15 is 3 majors behind what's currently
  documented, worth closing the gap opportunistically.

### warracker

- Current: `postgres:15-alpine` (`warracker/warracker.yaml:34`)
- Warracker's own `docker-compose.yml` (github.com/sassanix/Warracker) uses the same
  `postgres:15-alpine` for its `warrackerdb` service.
- **No change needed.** Already matches upstream exactly.

---

## Bottom line

- `authentik` and `warracker`: already current, nothing to do.
- `immich`: already ahead of upstream's own default, nothing to do (optional extension-version bump only).
- `mealie` and `vikunja`: fine to leave, but if you're touching either deployment anyway, bumping
  to the version in their current docs (17 and 18 respectively) is low-risk and keeps you off
  versions further from what's tested/documented.
- `paperless-ngx`: the one I'd actually schedule — 2 majors behind, and the longer it sits the
  more upstream's own compose file (including that data-path change) will have drifted from what
  a future dump/restore needs to account for.
