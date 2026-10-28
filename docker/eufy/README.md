# eufy

Backup, restore and map-recover tooling for a Eufy robot vacuum (built for an X10 Pro Omni,
T2351), plus a service that runs it in the cluster at `https://moppy.nowhere`.

## Why

The robot keeps updating its map during every clean, and over weeks the map drifts. The
Eufy app has no way back, but the robot answers the `MAP_RECOVERY` command (the X8 app's
"Revert Map"): it drops its working map and goes back to the last saved one (the end of
mapping, or your last edit in the app). The service sends it after each clean, or just
measures the drift first.

## The service (`eufy_web/`)

One process: a thread that keeps an MQTT session to the robot, and a web page.

* After the robot has been docked for 5 minutes (the mop wash and dust emptying keep
  flipping its state), it snapshots the map. Mode **recover** then sends recover (the robot
  drops its working map and goes back to the map you last saved from the app), snapshots
  again, and logs both. Mode **observe** (the default) only snapshots. It never acts while
  the robot is busy and never after a mapping run.
* The page shows the robot, the latest map, the mode, the history (how much each clean
  changed the map, and whether recover brought it back), the backups (download, restore
  with a dry run first) and a "back up now" button (the CLI as a job).
* No login on the page: it is only reachable inside the cluster. Anyone who can open it can
  trigger recover and restore.

Edit the map in the app only while it is healthy: an edit probably becomes the new saved
version that recover goes back to.

State lives on the PVC mounted at `/data` (`EUFY_DATA`): `config.json` (written from the
`eufy` Secret at start), `.eufy_state.json` (login cache; Eufy rate-limits logins),
`backups/`, `history/`, `history.jsonl`, `settings.json`.

```sh
# local run against your own data folder
uv sync
EUFY_DATA=. uv run uvicorn eufy_web.app:app --port 8099
```

Seed an empty PVC with an existing backup folder:
`kubectl cp backups/<name> default/<eufy pod>:/data/backups/<name>`.

## The CLI


Back up the whole map setup of a Eufy robot vacuum (rooms, names, room settings,
zones, scenes, schedules) and put it back with one command when the robot wrecks
its map (phantom doors, missing walls, merged rooms, a rotated map...). Built and
tested against an X10 Pro Omni (T2351). It talks to Eufy's cloud MQTT the same way
the app does. No Home Assistant needed.

## What is and isn't possible

The robot owns its map's **geometry** (walls, floor). It can be read but not
uploaded: no known command pushes a floor plan back. Everything **layered on top**
of the geometry goes through the same requests the app sends, so it can be
re-applied to whatever map the robot has now, including a fresh remap:

| Part | Backed up from | Restored with | Status |
|---|---|---|---|
| Map (walls, floor, room outlines) | map stream (`sync`, see below) | `recover` (the X8 app's "Revert Map": back to the last edit; works on the X10, see "Map drift") | backup works |
| Room splits/merges | room outline | `DIVIDE_ROOM` / `MERGE_ROOMS`, planned by aligning the maps | request matches the app's; planner tested offline |
| Room names, room type, floor type | room params | `RENAME_ROOM` | from the proto, not yet tried |
| Per-room cleaning settings, smart mode | room params | `SET_ROOMS_CUSTOM` | from the proto, not yet tried |
| Virtual walls, no-go and no-mop zones | restricted zones | `SET_RESTRICTED_ZONES`, moved by the alignment | from the proto, not yet tried |
| Scenes (what each one cleans, how) | scene stream (needs one app "Save", see below) | `SceneRequest MODIFY/ADD` | request matches the app's |
| Schedules | DPS 164 | `TimerRequest MOTIFY/ADD` | request matches the app's byte for byte |
| Cleaning, dock, do-not-disturb, general, voice settings | DPS 154/173/157/176/162 | not re-sent (a remap doesn't touch them) | compared on restore |
| Stop the robot from updating its map | none | none | not in the protocol |

## Setup

```sh
uv sync
```

`config.json` holds the Eufy account:

```json
{"username": "you@example.com", "password": "...", "device_sn": "optional"}
```

The login session and a stable fake phone id are cached in `.eufy_state.json`.
Eufy rate-limits logins (HTTP 429) after a few in a row; the cache avoids that. Delete
the file to force a fresh login.

## The workflow

1. Map the home (or remap), then set everything up in the app: split/merge rooms,
   names, per-room settings, zones, scenes, schedules.
2. Back it all up, with the robot docked:

   ```sh
   uv run eufy_map.py backup --label good
   ```

   The map arrives within a second. To include what each **scene** does, the robot
   has to publish its scenes, and it does that only after a scene or room change.
   So when the script asks, open any scene in the app and tap **Save** without
   changing anything. Check `backups/<date>_good/map/map.png`.
3. When the robot wrecks the map: if the geometry is still fine (only rooms
   merged/split, names or zones lost), restore straight away. If walls are wrong or
   the map is skewed, **remap first** (in the app), let it finish, then restore:

   ```sh
   uv run eufy_map.py restore backups/<date>_good          # dry run: shows the plan
   uv run eufy_map.py restore backups/<date>_good --yes    # does it
   ```

Restore asks the robot for its current map and lines the backup up with it
(remaps come out turned by a few degrees and shifted). It then:

* **rooms**: splits and merges the current rooms until they match the backup's.
  Splits are drawn as a straight line across the opening between the two rooms, the
  way the app's split tool works. Each edit is checked against the robot's
  re-published map before the next one.
* **names**: room names, room types, floor types, matched by position (room ids
  change on a remap).
* **custom**: per-room suction/mop/passes/order and the smart mode.
* **zones**: virtual walls and no-go/no-mop zones, moved onto the new map.
  This *replaces* the robot's zones.
* **scenes**: re-sends the backup's own scenes with room ids and zone-clean areas
  carried over. The built-in scenes are left alone.
* **schedules**: re-sends schedules that differ, pointing at the restored scenes.

`--only rooms,names` (any of `rooms,names,custom,zones,scenes,schedules`) limits it
to some parts. With `--yes` it first saves the robot's current state to
`backups/<date>_pre-restore`. It refuses to run while the robot is cleaning,
mapping or returning, and stops if the maps overlap under 60% (`--force` overrides
both). Steps that fail are listed; re-running restore only redoes what still differs.

## All commands

```sh
uv run eufy_map.py devices                  # robot, state, current map id, rooms
uv run eufy_map.py backup --label good      # everything -> backups/<date>_good/
uv run eufy_map.py restore BACKUP [--yes]   # put a backup back on the current map
uv run eufy_map.py snapshot --label x       # just the map -> backups/<date>_map<id>_x/
uv run eufy_map.py show DIR                 # summary (rooms, areas, zones); re-renders map.png
uv run eufy_map.py diff GOOD OTHER         # how far OTHER drifted/rotated from GOOD
uv run eufy_map.py listen [--app-commands]  # print everything; --app-commands also logs
                                            # what the Eufy app sends to the robot

# Also write to the robot (dry run without --yes):
uv run eufy_map.py recover [--map-id N] --yes   # MultiMapsManageRequest.MAP_RECOVERY, see "Map drift" below
uv run eufy_map.py load --map-id N --yes        # MAP_LOAD: switch to another saved map
```

A backup folder holds `state.json` (raw DPS: schedules, scene list, settings),
`state_decoded.json`, `map/` (`mapbackup.pb` = the map with rooms and zones,
`summary.json`, `map.png`), `scenes.pb`/`scenes.json`, and the raw MQTT log in
`capture/`.

## How the map is read (X10 Pro Omni)

When the app opens its map screen it sends `AppInfo` (DPS 169), then a
`KeepAliveRequest` with `force_sync` (DPS 153). The robot answers within a second
on `biz/…/res` with separate frames: `Map` (occupancy grid), `RoomOutline`,
`RoomParams` (names, room settings), `RestrictedZone` and `ObstacleInfo`. The
scripts send the same two messages, which change nothing on the robot. After a map
edit the robot also publishes a complete `MapBackup` of the saved map, and after a
scene or room change a `SceneWrap` with every scene's tasks. Channel numbers are
assigned by the robot and change, so frames are recognised by content.

Map edit acks (`MapEditResponse`) come back on DPS 170 on the X10, not on 164, which
carries the schedule list there. Room splits, merges, scene saves and schedule
saves made in the app were captured with `listen --app-commands`. The requests
these scripts build match them; see the table for which ones are still untested.

### Reading `diff`

* `floor_overlap` / `wall_overlap`: intersection over union of floor and wall cells,
  1.0 = identical.
* `rotation_deg`: best-fit turn of OTHER relative to GOOD (positive =
  counter-clockwise in `map.png`). If `floor_overlap_after_rotation` is much higher
  than `floor_overlap`, the map has rotated.

### Cleaning-history maps

Every cleaning-history entry stores the map of that clean (`CleanRecordData`), but
the X10 app fetches those over Eufy's encrypted P2P channel: opening one sent
nothing over MQTT (tested 2026-10-27). `snapshot --from-history` waits for one in
case other models publish it.

## Credits

The login flow, MQTT framing, DPS numbers and `eufy_fix/proto/` (copied unmodified)
come from [jeppesens/eufy-clean](https://github.com/jeppesens/eufy-clean) at
commit `baeb32c`. See `eufy_fix/proto/LICENSE-eufy-clean.md`. The Python modules in
`eufy_fix/` are rewritten from it (synchronous, standalone). The app-traffic topics
and app-side notes came from
[albertoxamin/eufyhome](https://github.com/albertoxamin/eufyhome).

## Map drift and `recover`

The robot keeps updating its map while it cleans, and over weeks the map drifts:
the picture in the app can stay right while the robot's laser positioning goes
wrong. The X8 Pro app has a "Revert Map" (Manage Map → ⋯) that goes back to the
map as it was at the last user edit, zones included. The X10 app has no such
button, but `MultiMapsManageRequest.MAP_RECOVERY` looks like the same feature.

Tested 2026-10-28 on map 15: the robot answered `SUCCESS` and the map stayed the
same. That test proves nothing, because the map hadn't changed since its last edit.
To test it properly: right after a clean remap and the app setup (the last edit),
`snapshot --label good`. When the robot starts drifting, `snapshot --label drifted`,
`recover --yes`, `snapshot --label recovered`, then `diff` good against recovered.
Any app edit (renaming a room, moving a zone) probably moves the revert point, so
only edit while the map is healthy.

`replace --map-id 15` with map 16 loaded (2026-10-28): the robot answered `FAILED`
and changed nothing. `MAP_REPLACE` is probably only accepted right after a mapping
run, before the new map is saved (the app's "replace an existing map" choice).
`replace --map-id 16` with 16 loaded: also `FAILED`, nothing changed.

**`recover` works on the X10** (2026-10-28, map 16): after a clean changed the map
(floor 98%, walls 92% against the post-mapping snapshot), `recover --map-id 16 --yes`
put it back (floor 100%, walls 99%). The revert point was the save at the end of the
mapping run, as no app edit had been made since.
