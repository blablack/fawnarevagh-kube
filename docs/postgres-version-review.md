# PostgreSQL version review (2026-09-06)

Six deployments in this repo run their own embedded Postgres container with a hardcoded
image tag. This started as an audit of each against what upstream currently ships/recommends;
`mealie`, `vikunja`, and `paperless-ngx` have since been bumped (2026-09-06) via dump/restore,
one at a time, each verified healthy before moving to the next. See "Migration log" below for
what was actually done and a gotcha hit along the way (Postgres 18's changed volume layout).

## Summary

| App | Image | Current major | Upstream recommends | Status |
|---|---|---|---|---|
| `authentik` | `postgres:16-alpine` | 16 | 16-alpine (current official compose) | Already matched upstream — no change |
| `warracker` | `postgres:15-alpine` | 15 | 15-alpine (current official compose) | Already matched upstream — no change |
| `immich` | `ghcr.io/immich-app/postgres:16-vectorchord0.5.3-pgvector0.8.1` | 16 | Officially still ships 14 (deliberately frozen); 16/17/18 confirmed working | Already ahead of upstream's own default — no change. Optional: bump the vectorchord/pgvector extension build (see below) |
| `mealie` | `postgres:17` (was 15) | 17 | `postgres:17` (current docs example) | **Bumped 2026-09-06** ✅ |
| `vikunja` | `postgres:18` (was 15) | 18 | `postgres:18` (current docs example) | **Bumped 2026-09-06** ✅ |
| `paperless-ngx` | `postgres:18` (was 16) | 18 | `postgres:18` (current `docker-compose.postgres.yml`) | **Bumped 2026-09-06** ✅ |

None of these were urgent from a support/EOL standpoint — see the Postgres EOL table below. This
was a "nice to do during a maintenance window" list, not a fire drill.

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
start against a `postgres:15` data directory. All of these deployments mount the data dir via a
fixed `subPath` on the app's PVC, so swapping the tag in place would just crash-loop the pod.

This is the procedure actually used for the `mealie`/`vikunja`/`paperless-ngx` bumps
(small homelab-scale DBs, so `pg_dump`/`pg_restore` is simplest — no need for `pg_upgrade`
machinery):

1. `./scripts/stop_argocd.sh` (once, covers all apps being migrated in the same window) so
   selfHeal doesn't revert the manual steps below.
2. With the *old* container still running (needed since postgres is a sidecar in the same pod
   as the app — scaling the deployment to 0 kills it too): `kubectl exec` in and run
   `pg_dump -U <user> -d <db> -Fc -f /tmp/backup.dump`, then `kubectl cp` it out to a local file.
3. Swap the deployment to a **temporary postgres-only** version — same PVC, new image tag, new
   `subPath` — with the app (and any other sidecar, e.g. redis) container removed entirely. This
   is the step that needs a real teardown of the container list, not a patch:
   `kubectl apply -f` alone was **not reliable for dropping a container** — it depends on
   `kubectl` having a clean `last-applied-configuration` baseline to diff against, and one of the
   three migrations here (`vikunja`) briefly ended up with the app container still present and
   racing against a not-yet-restored empty database. No data was lost (postgres itself was
   crash-looping so nothing had been written yet), but the fix was to force it with a JSON patch
   that replaces the whole container list outright:
   `kubectl patch deployment <app> --type=json -p '[{"op":"replace","path":"/spec/template/spec/containers","value":[<postgres-only container spec>]}]'`.
   Confirm with `kubectl get deployment <app> -o jsonpath='{.spec.template.spec.containers[*].name}'`
   before proceeding — it should print `postgres` alone.
4. Let the new container initialize fresh (empty subPath ⇒ auto-creates the role/db from
   `POSTGRES_USER`/`PASSWORD`/`DB` env vars), then restore:
   `kubectl cp` the dump in and `pg_restore -U <user> -d <db> --no-owner /tmp/backup.dump`.
   A clean (exit 0) restore into a *genuinely* empty database is itself a check — if the app
   container had touched the db first and run its own migrations, restore would fail with
   "already exists" errors instead.
5. Verify row/table counts match the pre-migration numbers, **then** edit the tracked yaml with
   the real final state (new image, new subPath, app container back) and `kubectl apply -f` it —
   adding a container back this way works fine, it's only removal that needs the JSON-patch
   workaround. Verify the app itself (logs, a table count via `psql`, an HTTP check) before
   moving to the next app.
6. **Commit and push the matching yaml edits to `main` before running `start_argocd.sh`.**
   ArgoCD reconciles against `origin/main`, not the local working tree — resuming it while your
   edits are only local/`kubectl apply`'d makes selfHeal immediately revert every app back to the
   old image/subPath the moment it comes back up (hit this live during this exact migration;
   caught and fixed by committing+pushing, then forcing a resync per app with
   `kubectl -n argocd patch application <app> --type merge -p '{"operation":{"sync":{"revision":"HEAD"}}}'`
   rather than waiting for the poll interval). Once pushed and confirmed synced, `start_argocd.sh`
   and leave the old versioned subPath (e.g. `postgresql_15`) in place for a while as a fallback
   before deleting it.

### Gotcha: Postgres 18 changed its expected volume layout

Postgres 18+ official images no longer expect the data directory to be mounted directly at
`/var/lib/postgresql/data`. They now manage a versioned path themselves
(`/var/lib/postgresql/<major>/docker`) and expect the **volume mounted at the parent**,
`/var/lib/postgresql` — see
[docker-library/postgres#1259](https://github.com/docker-library/postgres/pull/1259). Mounting
at the old `.../data` path makes the postgres:18 entrypoint refuse to start, treating it as
leftover data from an unmanaged upgrade ("there appears to be PostgreSQL data in:
/var/lib/postgresql/data (unused mount/volume)"). This hit both `vikunja` and `paperless-ngx`
(both went to postgres:18) — the fix was mounting the subPath at `/var/lib/postgresql` instead
of `/var/lib/postgresql/data`, with no other change needed. `paperless.yaml` also had a
`preStop` hook hardcoding `pg_ctl stop -D /var/lib/postgresql/data/pgdata`, which needed
updating to the new real PGDATA path (`/var/lib/postgresql/18/docker`). `mealie` (→ postgres:17)
wasn't affected since the old layout is unchanged through 17.

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

### mealie — bumped 15 → 17 ✅

- `mealie/mealie.yaml:31`, data at `subPath: postgresql_17` (was `postgresql_15`)
- Mealie's install docs (`docs.mealie.io/.../installation/postgres/`) show `postgres:17` as the
  example image. A maintainer confirmed in
  [discussion #5481](https://github.com/mealie-recipes/mealie/discussions/5481) that the sample
  compose file just hadn't been updated for a while, and 17 is what they'd point people at now.
- Migrated 2026-09-06 via `pg_dump`/`pg_restore` (see procedure above). Verified: table count,
  `users` row count, and the alembic migration marker all matched pre-migration; app came up
  clean with no restarts and served `200` over HTTP.

### paperless-ngx — bumped 16 → 18 ✅

- `paperless/paperless.yaml:43`, data at `subPath: postgresql_18` (was unversioned `postgresql`)
- Upstream's `docker/compose/docker-compose.postgres.yml` specifies `postgres:18`. A
  paperless-ngx commit ([#11084](https://github.com/paperless-ngx/paperless-ngx)) had already
  changed the default Postgres data path in their reference compose file for the same reason
  covered in the Postgres-18-layout gotcha above — see
  [discussion #11678](https://github.com/paperless-ngx/paperless-ngx/discussions/11678>) for
  other self-hosters going through the same 16→18 jump.
- Migrated 2026-09-06. Hit the postgres:18 volume-layout change (see gotcha above); fixed by
  mounting `subPath: postgresql_18` at `/var/lib/postgresql` instead of `.../data`, and updating
  the `preStop` hook's `pg_ctl stop -D` path to match. Verified: table count (74) and
  `documents_document` row count (76) matched pre-migration exactly; paperless's own startup
  migrations reported "No migrations to apply", and the app came up 3/3 healthy serving the
  expected `302` redirect-to-login over HTTP.

### vikunja — bumped 15 → 18 ✅

- `vikunja/vikunja.yaml:41`, data at `subPath: postgresql_18` (was `postgresql_15`)
- Vikunja's documented minimum is Postgres 12+, and the current "Full docker example" in their
  docs uses `postgres:18`.
- Migrated 2026-09-06. Also hit the postgres:18 volume-layout gotcha (same fix as paperless:
  mount at `/var/lib/postgresql`, not `.../data`). This was also the migration where the
  container-list-removal issue described above showed up — resolved with the JSON-patch replace.
  Verified: table count (37) and `users` row count (1) matched pre-migration; vikunja's own
  migrations ran and reported success; app came up 2/2 healthy serving `200` on `/api/v1/info`.
  (One harmless restart of the `vikunja` container during the final rollout — it raced postgres's
  own startup by about a second on the first attempt, same benign race that already existed
  before this change since nothing enforces container start order within the pod.)

### warracker

- Current: `postgres:15-alpine` (`warracker/warracker.yaml:34`)
- Warracker's own `docker-compose.yml` (github.com/sassanix/Warracker) uses the same
  `postgres:15-alpine` for its `warrackerdb` service.
- **No change needed.** Already matches upstream exactly.

---

## Bottom line

- `authentik` and `warracker`: already current, nothing to do.
- `immich`: already ahead of upstream's own default, nothing to do (optional extension-version bump only).
- `mealie`, `vikunja`, `paperless-ngx`: bumped and verified 2026-09-06 (see per-app sections and
  migration notes above). Old versioned subPaths (`postgresql_15` for mealie/vikunja, plain
  `postgresql` for paperless) were left in place on each PVC as a fallback — safe to delete once
  you're confident, to reclaim a little space on each small Longhorn volume.
