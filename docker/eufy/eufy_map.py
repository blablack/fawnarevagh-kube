#!/usr/bin/env python3
"""Back up and restore the map setup of a Eufy robot vacuum (X10 Pro Omni and other MQTT models).

Read-only:
  devices                     list robots, current map id and state
  backup                      save the map, rooms, zones, scenes, schedules and settings
  listen                      print everything the robot sends; keep map snapshots
                              (--app-commands: also record what the Eufy app sends)
  snapshot                    store the robot's current map in backups/
  show DIR                    print a stored snapshot's summary (re-renders map.png)
  diff GOOD OTHER             how far OTHER has drifted/rotated from GOOD

Writes to the robot (dry run unless --yes):
  restore BACKUP              put a backup's rooms, names, room settings, zones, scenes
                              and schedules back on the robot's current map
  recover                     ask the robot to restore its map (MAP_RECOVERY)
  load                        switch the active saved map (MAP_LOAD)
  replace                     MAP_REPLACE with --map-id; which way it copies is untested
  delete-scene                delete a scene by --id (SceneRequest DELETE_SCENE)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any

from google.protobuf.message import DecodeError
from google.protobuf.message import Message as Proto

from eufy_fix import codec
from eufy_fix.align import Alignment, align, ref_rooms_on
from eufy_fix.backup import Backup, decode_state, now_label, settings_changes
from eufy_fix.cloud import Account, Device, EufyLoginError, login
from eufy_fix.mapdata import (FRAME_CLEAN_RECORD, FRAME_MAP, FRAME_MAP_BACKUP,
                              FRAME_MAP_DESCRIPTION, FRAME_OBSTACLES, FRAME_POSE,
                              FRAME_RESTRICTED_ZONE, FRAME_ROOM_OUTLINE, FRAME_ROOM_PARAMS,
                              FRAME_SCENES, Snapshot, classify_frame, compare)
from eufy_fix.mqtt import EufyMqtt, Message, decode_biz_payload, decode_cmd_payload
from eufy_fix.proto.cloud.map_edit_pb2 import MapEditResponse
from eufy_fix.proto.cloud.multi_maps_pb2 import MultiMapsManageRequest
from eufy_fix.proto.cloud.scene_pb2 import SceneRequest, SceneResponse
from eufy_fix.proto.cloud.timing_pb2 import TimerResponse
from eufy_fix.proto.cloud.work_status_pb2 import WorkStatus
from eufy_fix.restore import (PARTS, RoomEdit, RoomLayout, custom_request, name_requests,
                              plan_rooms, scene_requests, timer_requests, zones_request)
from eufy_fix.robot import Robot

ROOT = Path(__file__).resolve().parent
# Where config.json, the login cache, backups and captures live (a volume in the container).
DATA = Path(os.environ.get("EUFY_DATA", ROOT))
STATE_FILE = DATA / ".eufy_state.json"
BACKUPS = DATA / "backups"
CAPTURES = DATA / "captures"

# Don't touch the map while the robot is moving around on it.
BUSY_STATES = {WorkStatus.FAST_MAPPING, WorkStatus.CLEANING, WorkStatus.REMOTE_CTRL,
               WorkStatus.GO_HOME, WorkStatus.CRUISIING}
# Below this floor overlap the backup and the robot's map are probably not the
# same home (or the robot's map is badly broken): zones would land wrong.
MIN_OVERLAP = 0.6

log = logging.getLogger("eufy_map")


# -- setup ---------------------------------------------------------------------

def log_in(args: argparse.Namespace) -> tuple[Account, dict[str, Any]]:
    """Log in, reusing the session cached in .eufy_state.json when it is still valid.

    The state file also keeps a stable fake phone id (openudid), so the cloud
    sees one client rather than a new one on every run.
    """
    config = json.loads(Path(args.config).read_text())
    try:
        state = json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        state = {}
    state.setdefault("openudid", secrets.token_hex(16))
    account = login(config["username"], config["password"], state["openudid"],
                    state.get("session"))
    state["session"] = account.session
    STATE_FILE.touch(mode=0o600)
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")
    return account, config


def connect_account(args: argparse.Namespace) -> tuple[Account, Device]:
    account, config = log_in(args)
    if not account.devices:
        sys.exit("No MQTT robots on this account.")
    wanted = args.device or config.get("device_sn")
    if wanted:
        device = next((d for d in account.devices if d.sn == wanted), None)
        if device is None:
            sys.exit(f"Device {wanted} not found; run `devices` to list them.")
    elif len(account.devices) == 1:
        device = account.devices[0]
    else:
        sys.exit("Several robots on this account; pick one with --device SN.")
    return account, device


def open_mqtt(account: Account, device: Device, watch_requests: bool = False) -> EufyMqtt:
    client = EufyMqtt(account.mqtt, account.openudid, device.sn, device.model, watch_requests)
    client.connect()
    log.info("Connected to MQTT for %s (%s %s)", device.name, device.model, device.sn)
    return client


def work_state(dps: dict[str, Any]) -> int | None:
    value = dps.get(codec.DPS_WORK_STATUS)
    if not isinstance(value, str):
        return None
    try:
        return codec.decode_dps(WorkStatus, value).state
    except (DecodeError, ValueError):
        return None


def stamp() -> str:
    return time.strftime("%Y-%m-%dT%H-%M-%S")


def device_info(device: Device) -> dict[str, Any]:
    return {"name": device.name, "sn": device.sn, "model": device.model,
            "firmware": device.firmware}


def refuse_if_busy(args: argparse.Namespace, dps: dict[str, Any]) -> None:
    state = work_state(dps)
    if state is not None and state in BUSY_STATES and not args.force:
        sys.exit(f"Robot is {WorkStatus.State.Name(state)}; dock it first (or pass --force).")


# -- message handling ---------------------------------------------------------

_PART_NAMES = {FRAME_ROOM_OUTLINE: "room outline", FRAME_ROOM_PARAMS: "room names/settings",
               FRAME_RESTRICTED_ZONE: "zones and virtual walls", FRAME_OBSTACLES: "obstacles"}


class Recorder:
    """Logs every message to a JSONL file and keeps decoded map frames."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self._log = (directory / "messages.jsonl").open("a")
        self.snapshots: list[tuple[Path, Snapshot]] = []

    def close(self) -> None:
        self._log.close()

    def handle(self, msg: Message, quiet_poses: bool = True) -> tuple[str, Any] | None:
        """Record *msg*; return ("dps", dict) or (frame kind, decoded message)."""
        self._log.write(json.dumps({"t": msg.received_at, "topic": msg.topic,
                                    "payload": msg.payload.decode(errors="replace")}) + "\n")
        self._log.flush()
        when = time.strftime("%H:%M:%S", time.localtime(msg.received_at))
        if msg.is_request:
            dps = decode_cmd_payload(msg.payload)
            if dps is None:
                print(f"[{when}] -> robot on {msg.topic}: {msg.payload[:300]!r}")
                return None
            for key, value in dps.items():
                print(f"[{when}] -> robot DPS {key}: "
                      f"{json.dumps(codec.describe_request(key, value), ensure_ascii=False)}")
            return "request", dps
        if not msg.is_biz:
            dps = decode_cmd_payload(msg.payload)
            if dps is None:
                print(f"[{when}] cmd: (no DPS) {msg.payload[:200]!r}")
                return None
            for key, value in dps.items():
                print(f"[{when}] DPS {key}: {json.dumps(codec.describe_dps(key, value))[:600]}")
            return "dps", dps

        biz = decode_biz_payload(msg.payload)
        if biz is None:
            print(f"[{when}] biz: unrecognised payload ({len(msg.payload)} bytes)")
            return None
        channel, frame = biz
        kind, decoded = classify_frame(frame)
        if kind in (FRAME_MAP_BACKUP, FRAME_MAP, FRAME_CLEAN_RECORD):
            snap = Snapshot.from_frame(kind, decoded, msg.received_at)  # type: ignore[arg-type]
            if kind in (FRAME_MAP_BACKUP, FRAME_CLEAN_RECORD):
                suffix = "_history" if kind == FRAME_CLEAN_RECORD else ""
                path = snap.save(self.directory / f"{stamp()}_map{snap.map_id}{suffix}")
                self.snapshots.append((path, snap))
                what = "CLEANING-HISTORY MAP" if suffix else "FULL MAP (MapBackup)"
                print(f"[{when}] biz ch{channel}: {what} map_id={snap.map_id} "
                      f"rooms={len(snap.room_names())} -> {path}")
            else:
                # Live frames arrive every few seconds while cleaning; keep the latest.
                path = snap.save(self.directory / "latest_live_map")
                print(f"[{when}] biz ch{channel}: live map frame "
                      f"{snap.backup.map.info.width}x{snap.backup.map.info.height} -> {path}")
            return kind, snap
        if kind in _PART_NAMES:
            print(f"[{when}] biz ch{channel}: {_PART_NAMES[kind]} "
                  f"(map {getattr(decoded, 'map_id', '?')})")
        elif kind == FRAME_SCENES:
            names = [sc.info.name for sc in decoded.scenes]  # type: ignore[union-attr]
            print(f"[{when}] biz ch{channel}: scenes with their tasks: {', '.join(names)}")
        elif kind == FRAME_MAP_DESCRIPTION:
            print(f"[{when}] biz ch{channel}: map description {codec.to_dict(decoded)}")  # type: ignore[arg-type]
        elif kind == FRAME_POSE:
            if not quiet_poses:
                print(f"[{when}] biz ch{channel}: robot pose {codec.to_dict(decoded)}")  # type: ignore[arg-type]
        else:
            print(f"[{when}] biz ch{channel}: unknown frame, {len(frame)} bytes")
        return kind, decoded


# -- commands -----------------------------------------------------------------

def cmd_devices(args: argparse.Namespace) -> None:
    account, _ = log_in(args)
    for d in account.devices:
        state = work_state(d.dps)
        print(f"{d.name}\n  serial: {d.sn}\n  model: {d.model}  firmware: {d.firmware or '?'}")
        print(f"  state: {WorkStatus.State.Name(state) if state is not None else '?'}")
        print(f"  current map id: {codec.current_map_id(d.dps) or '?'}")
        for key in (codec.DPS_MAP_DATA, codec.DPS_UNISETTING):
            if key in d.dps:
                print(f"  DPS {key}: {json.dumps(codec.describe_dps(key, d.dps[key]))[:800]}")
        if args.raw:
            print(json.dumps(d.dps, indent=2))


def cmd_listen(args: argparse.Namespace) -> None:
    account, device = connect_account(args)
    rec = Recorder(CAPTURES / stamp())
    print(f"Recording to {rec.directory} (Ctrl+C to stop)")
    try:
        with open_mqtt(account, device, args.app_commands) as client:
            for msg in client.iter_messages(args.seconds or None):
                rec.handle(msg, quiet_poses=not args.poses)
    except KeyboardInterrupt:
        pass
    finally:
        rec.close()
    print(f"Saved {len(rec.snapshots)} full map snapshot(s) in {rec.directory}")


def cmd_backup(args: argparse.Namespace) -> None:
    account, device = connect_account(args)
    target = BACKUPS / f"{stamp()}_{args.label}"
    with Robot(account, device, target / "capture" / "messages.jsonl") as robot:
        print("Asking the robot for its map...")
        snap = robot.sync_map(args.wait)
        if snap is None:
            print("  WARNING: no map arrived; rooms, names and zones won't be in this backup.")
        listed = decode_state(robot.dps, codec.DPS_SCENE, SceneResponse)
        own = [i.name for i in listed.infos if i.type == i.SCENE_NORMAL] if listed else []
        if robot.scenes is None and own and args.scene_wait > 0:
            # The robot only publishes what each scene does after a scene or room
            # change; saving a scene unchanged in the app is enough.
            print(f"\nTo include what each scene does ({', '.join(own)}), open any scene\n"
                  "in the Eufy app and tap Save without changing anything.\n"
                  f"Waiting up to {args.scene_wait:.0f}s (Ctrl+C to skip)...")
            try:
                if robot.pump(args.scene_wait, lambda: robot.scenes is not None):
                    print("  got them.")
            except KeyboardInterrupt:
                print("  skipped.")
        backup = Backup(now_label(), device_info(device), dict(robot.dps), snap, robot.scenes)
    backup.save(target)
    print(f"\nBackup: {target}")
    for line in backup.summary():
        print(f"  {line}")
    if snap is not None:
        print(f"  check that {target / 'map' / 'map.png'} shows the map you want")


def cmd_snapshot(args: argparse.Namespace) -> None:
    account, device = connect_account(args)
    found: Snapshot | None = None
    if not args.from_history:
        with Robot(account, device, CAPTURES / f"{stamp()}_snapshot" / "messages.jsonl") as robot:
            found = robot.sync_map(args.wait)
        if found is None:
            sys.exit("The robot sent no map.")
    else:
        rec = Recorder(CAPTURES / f"{stamp()}_snapshot")
        print("Open the cleaning-history entry you want in the Eufy app and leave its map on\n"
              "screen for a few seconds.")
        try:
            with open_mqtt(account, device) as client:
                for msg in client.iter_messages(args.wait):
                    result = rec.handle(msg)
                    if result and result[0] == FRAME_CLEAN_RECORD:
                        found = result[1]
                        break
        except KeyboardInterrupt:
            pass
        finally:
            rec.close()
        if found is None:
            sys.exit(f"No history map received within {args.wait}s (raw log in {rec.directory}).")
    label = f"_{args.label}" if args.label else ""
    path = found.save(BACKUPS / f"{stamp()}_map{found.map_id}{label}")
    print(f"Snapshot saved: {path}\n  open {path / 'map.png'} to check it is the map you want.")


def map_dir(path: str) -> Path:
    """A snapshot folder, or the map inside a backup folder."""
    d = Path(path)
    return d / "map" if (d / "map").is_dir() else d


def cmd_show(args: argparse.Namespace) -> None:
    snap = Snapshot.load(map_dir(args.snapshot))
    snap.save(map_dir(args.snapshot))
    summary = snap.summary()
    for key in ("room_params", "restricted_zone", "description", "map_info"):
        summary.pop(key)
    print(json.dumps(summary, indent=2))


def cmd_diff(args: argparse.Namespace) -> None:
    result = compare(Snapshot.load(map_dir(args.good)), Snapshot.load(map_dir(args.other)),
                     max_angle=args.max_angle)
    print(json.dumps(result, indent=2))
    print(
        f"\nfloor overlap {result['floor_overlap']:.0%}, walls {result['wall_overlap']:.0%}; "
        f"best fit after turning {result['rotation_deg']:+.2f}° -> "
        f"{result['floor_overlap_after_rotation']:.0%}"
    )


def send_and_watch(args: argparse.Namespace, account: Account, device: Device,
                   dps: dict[str, Any], what: str, expect_key: str) -> None:
    """Dry-run or send a write, then report the robot's ack and any new map."""
    print(f"{what}\n  DPS {next(iter(dps))} = {next(iter(dps.values()))}")
    if not args.yes:
        print("Dry run: nothing sent. Re-run with --yes to send it.")
        return
    state = work_state(device.dps)
    if state is not None and state in BUSY_STATES and not args.force:
        sys.exit(f"Robot is {WorkStatus.State.Name(state)}; dock it first (or pass --force).")
    rec = Recorder(CAPTURES / f"{stamp()}_{args.command}")
    try:
        with open_mqtt(account, device) as client:
            client.send_dps(dps)
            print(f"Sent. Watching replies for {args.wait}s (raw log in {rec.directory})...")
            for msg in client.iter_messages(args.wait):
                result = rec.handle(msg)
                if result and result[0] == "dps" and expect_key in result[1]:
                    print(">>> robot replied to the request (see DPS "
                          f"{expect_key} above; result SUCCESS/STARTED/FAILED)")
    except KeyboardInterrupt:
        pass
    finally:
        rec.close()
    if rec.snapshots:
        print(f"New full map(s) received: {[str(p) for p, _ in rec.snapshots]}\n"
              "Compare against your good backup with: diff BACKUP_DIR NEW_DIR")


def resolve_map_id(args: argparse.Namespace, device: Device) -> int:
    if args.map_id:
        return args.map_id
    map_id = codec.current_map_id(device.dps)
    if not map_id:
        sys.exit("Could not read the current map id; pass --map-id (see `devices`).")
    return map_id


def cmd_recover(args: argparse.Namespace) -> None:
    account, device = connect_account(args)
    map_id = resolve_map_id(args, device)
    req = MultiMapsManageRequest(method=MultiMapsManageRequest.MAP_RECOVERY, seq=args.seq,
                                 common=MultiMapsManageRequest.Common(cloud_mapid=map_id))
    send_and_watch(args, account, device, {codec.DPS_MULTI_MAP_MANAGE: codec.encode_dps(req)},
                   f"MAP_RECOVERY for map {map_id}", codec.DPS_MULTI_MAP_MANAGE)


def cmd_load(args: argparse.Namespace) -> None:
    account, device = connect_account(args)
    req = MultiMapsManageRequest(method=MultiMapsManageRequest.MAP_LOAD, seq=args.seq,
                                 common=MultiMapsManageRequest.Common(cloud_mapid=args.map_id))
    send_and_watch(args, account, device, {codec.DPS_MULTI_MAP_MANAGE: codec.encode_dps(req)},
                   f"MAP_LOAD map {args.map_id}", codec.DPS_MULTI_MAP_MANAGE)


def cmd_replace(args: argparse.Namespace) -> None:
    account, device = connect_account(args)
    current = codec.current_map_id(device.dps) or "?"
    req = MultiMapsManageRequest(method=MultiMapsManageRequest.MAP_REPLACE, seq=args.seq,
                                 common=MultiMapsManageRequest.Common(cloud_mapid=args.map_id))
    send_and_watch(args, account, device, {codec.DPS_MULTI_MAP_MANAGE: codec.encode_dps(req)},
                   f"MAP_REPLACE map {args.map_id} (current map {current})",
                   codec.DPS_MULTI_MAP_MANAGE)


def cmd_delete_scene(args: argparse.Namespace) -> None:
    account, device = connect_account(args)
    req = SceneRequest(method=SceneRequest.DELETE_SCENE, seq=args.seq,
                       common=SceneRequest.Common(scene_id=args.id))
    send_and_watch(args, account, device, {codec.DPS_SCENE: codec.encode_dps(req)},
                   f"DELETE_SCENE scene {args.id}", codec.DPS_SCENE)


def _outcome(reply: Proto | None) -> tuple[bool, str]:
    if reply is None:
        return False, "no answer from the robot"
    if isinstance(reply, MapEditResponse):
        if reply.result == MapEditResponse.SUCCESS:
            return True, "done"
        return False, f"refused ({MapEditResponse.FailCode.Value.Name(reply.fail_code.value)})"
    result = getattr(reply, "result")
    if result.value == 0:
        return True, "done"
    return False, f"refused (error {result.err_code})"


class Sender:
    """Prints each step; with --yes also sends it and waits for the robot's answer."""

    def __init__(self, args: argparse.Namespace, robot: Robot) -> None:
        self.live = args.yes
        self.wait = args.wait
        self.robot = robot
        self.failures = 0

    def send(self, text: str, key: str, req: Proto, reply_type: type[Proto],
             reply_keys: tuple[str, ...] | None = None) -> Proto | None:
        if not self.live:
            print(f"  would {text}")
            return None
        print(f"  {text} ... ", end="", flush=True)
        setattr(req, "seq", self.robot.next_seq())
        reply = self.robot.request(
            key, req, reply_type, reply_keys, timeout=self.wait,
            final=lambda r: not (isinstance(r, MapEditResponse)
                                 and r.result == MapEditResponse.STARTED))
        ok, detail = _outcome(reply)
        print(detail)
        if not ok:
            self.failures += 1
            return None
        return reply


# MapEditResponse comes back on 170 on the X10, on 164 per eufy-clean.
_MAP_EDIT_REPLIES = (codec.DPS_MAP_EDIT_RESPONSE, codec.DPS_TIMER)
MAX_ROOM_EDITS = 40


def apply_room_edits(sender: Sender, robot: Robot, backup: Backup, current: Snapshot,
                     al: Alignment, names: dict[int, str]) -> tuple[Snapshot, RoomLayout]:
    """Split/merge on the robot one edit at a time, re-reading its map after each."""
    assert backup.map is not None
    failed: set[RoomEdit] = set()
    for _ in range(MAX_ROOM_EDITS):
        layout = RoomLayout(current.grid(), ref_rooms_on(current.grid(), backup.map.grid(), al))
        edit = layout.next_edit(failed)
        if edit is None:
            return current, layout
        t0 = time.time()
        if sender.send(edit.describe(names), codec.DPS_MAP_EDIT_REQUEST,
                       edit.request(current.map_id, 0), MapEditResponse,
                       _MAP_EDIT_REPLIES) is None:
            failed.add(edit)
            continue
        # The robot publishes the edited map a few seconds after its ack.
        robot.pump(20, lambda: robot.map_since(t0) is not None)
        updated = robot.map_since(t0) or robot.sync_map()
        if updated is None:
            sys.exit("The robot didn't send its updated map; stopping here.")
        if updated.backup.rooms.pixels == current.backup.rooms.pixels:
            failed.add(edit)  # acked, but nothing changed
        current = updated
    sys.exit(f"Rooms still don't match the backup after {MAX_ROOM_EDITS} edits; stopping. "
             "Fix the rooms in the app, then re-run restore.")


def cmd_restore(args: argparse.Namespace) -> None:
    backup = Backup.load(Path(args.backup))
    if backup.map is None:
        sys.exit("This backup has no map, so rooms, names and zones can't be restored.")
    parts: set[str] = set(args.only.split(",")) if args.only else set(PARTS)
    if parts - set(PARTS):
        sys.exit(f"--only takes a comma-separated list of: {', '.join(PARTS)}")
    account, device = connect_account(args)
    with Robot(account, device, CAPTURES / f"{stamp()}_restore" / "messages.jsonl") as robot:
        restore(args, account, device, robot, backup, parts)


def restore(args: argparse.Namespace, account: Account, device: Device, robot: Robot,
            backup: Backup, parts: set[str]) -> None:
    assert backup.map is not None
    names = backup.map.room_names()
    print(f"Backup: map {backup.map_id} from {backup.captured_at}")
    current = robot.sync_map()
    if current is None:
        sys.exit("The robot didn't send its map (is it online?).")
    print(f"Robot:  map {current.map_id}")
    if args.yes:
        refuse_if_busy(args, robot.dps)
    print("Lining the maps up (takes a few seconds)...")
    al = align(backup.map, current, max_angle=args.max_angle)
    print(f"  {al.describe()}")
    if al.overlap < MIN_OVERLAP and not args.force:
        sys.exit("The maps don't line up well enough to carry rooms and zones across. "
                 "Is this the same home? (--force goes on anyway)")
    if args.yes:
        safety = Backup(now_label(), device_info(device), dict(robot.dps), current, robot.scenes)
        path = safety.save(BACKUPS / f"{stamp()}_pre-restore")
        print(f"  saved the robot's current state to {path} first")
    sender = Sender(args, robot)

    print("\nRooms:")
    layout = RoomLayout(current.grid(), ref_rooms_on(current.grid(), backup.map.grid(), al))
    if "rooms" in parts:
        if args.yes:
            current, layout = apply_room_edits(sender, robot, backup, current, al, names)
        else:
            edits, layout = plan_rooms(layout)
            for edit in edits:
                print(f"  would {edit.describe(names)}")
            if edits:
                print("  (ids of rooms made by a split are guesses until the robot does it)")
    matching = layout.matching()
    for room, ref in sorted(matching.items(), key=lambda kv: kv[1]):
        print(f"  {names.get(ref, ref)} = robot room {room}")
    extra, missing = layout.unmatched()
    if extra:
        print(f"  robot rooms that aren't in the backup (left alone): {extra}")
    if missing:
        print("  backup rooms not found on the robot's map: "
              + ", ".join(names.get(r, str(r)) for r in missing))

    map_id = current.map_id
    ref_params, cur_params = backup.map.backup.room_params, current.backup.room_params
    edit_key = codec.DPS_MAP_EDIT_REQUEST
    if "names" in parts:
        print("\nRoom names and types:")
        renames = name_requests(map_id, matching, ref_params, cur_params)
        for text, req in renames:
            sender.send(text, edit_key, req, MapEditResponse, _MAP_EDIT_REPLIES)
        if not renames:
            print("  already as in the backup")
    if "custom" in parts:
        print("\nPer-room cleaning settings:")
        on_map = sorted(set(layout.labels) - {0})
        req = custom_request(map_id, matching, ref_params, cur_params, on_map)
        if req is None:
            print("  already as in the backup")
        else:
            sender.send(f"set them for {len(on_map)} rooms", edit_key, req, MapEditResponse,
                        _MAP_EDIT_REPLIES)
    if "zones" in parts:
        print("\nZones:")
        ref_zones = backup.map.backup.restricted_zone
        req = zones_request(map_id, ref_zones, current.backup.restricted_zone, al)
        if req is None:
            print("  already as in the backup")
        else:
            sender.send(f"set {len(ref_zones.virtual_walls)} virtual walls, "
                        f"{len(ref_zones.forbidden_zones)} no-go and "
                        f"{len(ref_zones.ban_mop_zones)} no-mop zones, moved onto the current "
                        "map (replaces the robot's zones)",
                        edit_key, req, MapEditResponse, _MAP_EDIT_REPLIES)

    rooms_now = {ref: room for room, ref in matching.items()}
    warnings: list[str] = []
    scene_ids: dict[int, int] = {}
    if "scenes" in parts:
        print("\nScenes:")
        if backup.scenes is None:
            print("  the backup has the scene names only, not what they do; skipped")
        else:
            listed = decode_state(robot.dps, codec.DPS_SCENE, SceneResponse)
            known = {i.id.value for i in listed.infos} if listed else set()
            if robot.scenes is None:
                print("  (the robot hasn't sent its scenes' contents to compare, so all are "
                      "re-sent)")
            todo = scene_requests(backup.scenes, listed, robot.scenes, map_id, rooms_now, al,
                                  backup.timers, account.mqtt["user_id"], warnings)
            for text, req, old_id in todo:
                reply = sender.send(text, codec.DPS_SCENE, req, SceneResponse)
                if isinstance(reply, SceneResponse) and req.method == SceneRequest.ADD_SCENE:
                    new = [i.id.value for i in reply.infos
                           if i.name == req.scene.info.name and i.id.value not in known]
                    if new:
                        scene_ids[old_id] = new[0]
                        known.add(new[0])
            if not todo:
                print("  already as in the backup")
    if "schedules" in parts:
        print("\nSchedules:")
        timers = backup.timers
        if timers is None:
            print("  none in the backup")
        else:
            current_timers = decode_state(robot.dps, codec.DPS_TIMER, TimerResponse)
            todo = timer_requests(timers, current_timers, map_id, rooms_now, scene_ids,
                                  account.mqtt["user_id"], warnings)
            for text, req in todo:
                sender.send(text, codec.DPS_TIMER, req, TimerResponse)
            if not todo:
                print("  already as in the backup")

    changed = settings_changes(backup.dps, robot.dps)
    print("\nGlobal settings (not restored; a remap doesn't touch them): "
          + (f"differ from the backup: {', '.join(changed)}" if changed else "same as the backup"))
    for w in warnings:
        print(f"WARNING: {w}")
    if not args.yes:
        print("\nDry run: nothing was sent. Re-run with --yes to apply.")
    elif sender.failures:
        print(f"\n{sender.failures} step(s) failed (see above). Re-running restore retries them.")
    else:
        print("\nDone. Check the map in the app.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=str(DATA / "config.json"))
    parser.add_argument("--device", help="robot serial number (if the account has several)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("devices", help="list robots, current map id and state")
    p.add_argument("--raw", action="store_true", help="dump all initial DPS values")
    p.set_defaults(func=cmd_devices)

    p = sub.add_parser("listen", help="print and record everything the robot sends")
    p.add_argument("--seconds", type=float, default=0, help="stop after N seconds (0 = never)")
    p.add_argument("--poses", action="store_true", help="also print robot position frames")
    p.add_argument("--app-commands", action="store_true",
                   help="also record the commands the Eufy app sends to the robot")
    p.set_defaults(func=cmd_listen)

    p = sub.add_parser("backup", help="save map, rooms, zones, scenes, schedules, settings")
    p.add_argument("--label", default="backup", help="suffix for the backup folder")
    p.add_argument("--wait", type=float, default=30, help="seconds to wait for the map")
    p.add_argument("--scene-wait", type=float, default=300,
                   help="seconds to wait for the scenes' contents (0 = don't)")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("snapshot", help="store the robot's current map in backups/")
    p.add_argument("--label", help="suffix for the backup folder, e.g. good")
    p.add_argument("--wait", type=float, default=30, help="seconds to wait")
    p.add_argument("--from-history", action="store_true",
                   help="wait for the map of a cleaning-history entry opened in the app")
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("show", help="summarise a stored snapshot")
    p.add_argument("snapshot")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("diff", help="compare two snapshots")
    p.add_argument("good")
    p.add_argument("other")
    p.add_argument("--max-angle", type=float, default=10.0)
    p.set_defaults(func=cmd_diff)

    def write_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--yes", action="store_true", help="actually send (default: dry run)")
        p.add_argument("--force", action="store_true", help="send even if the robot is busy")
        p.add_argument("--wait", type=float, default=120,
                       help="seconds to wait for each reply (recover/load: to watch replies)")
        p.add_argument("--seq", type=int, default=int(time.time()) % 100000)

    p = sub.add_parser("recover", help="ask the robot to restore its map (MAP_RECOVERY)")
    p.add_argument("--map-id", type=int, help="default: the current map")
    write_args(p)
    p.set_defaults(func=cmd_recover)

    p = sub.add_parser("load", help="switch to another saved map (MAP_LOAD)")
    p.add_argument("--map-id", type=int, required=True)
    write_args(p)
    p.set_defaults(func=cmd_load)

    p = sub.add_parser("replace", help="MAP_REPLACE a saved map (direction untested)")
    p.add_argument("--map-id", type=int, required=True)
    write_args(p)
    p.set_defaults(func=cmd_replace)

    p = sub.add_parser("delete-scene", help="delete a scene (DELETE_SCENE)")
    p.add_argument("--id", type=int, required=True, help="scene id (see a backup's scenes)")
    write_args(p)
    p.set_defaults(func=cmd_delete_scene)

    p = sub.add_parser("restore", help="put a backup's rooms, zones, scenes, schedules back")
    p.add_argument("backup", help="a folder made by `backup`")
    p.add_argument("--only", help=f"comma-separated subset of: {','.join(PARTS)}")
    p.add_argument("--max-angle", type=float, default=15.0,
                   help="largest turn between the two maps to look for (degrees)")
    write_args(p)
    p.set_defaults(func=cmd_restore)

    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    if not args.verbose:
        logging.getLogger("urllib3").setLevel(logging.WARNING)
    try:
        args.func(args)
    except EufyLoginError as exc:
        sys.exit(f"Login failed: {exc}")
    except ConnectionError as exc:
        sys.exit(f"MQTT failed: {exc}")


if __name__ == "__main__":
    main()
