"""A full backup on disk: robot state (DPS), the complete map, and the scenes.

Layout of a backup folder:
  state.json          raw DPS values (schedules, scene list, settings...) + device
  state_decoded.json  the same, decoded, for reading
  map/                the map with rooms and zones (see mapdata.Snapshot.save)
  scenes.pb           every scene with its tasks (stream SceneWrap), if received
  scenes.json         the same, decoded
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.protobuf.message import DecodeError

from . import codec
from .mapdata import BACKUP_FILE, Snapshot
from .proto.cloud.scene_pb2 import SceneResponse
from .proto.cloud.stream_pb2 import SceneWrap
from .proto.cloud.timing_pb2 import TimerResponse

STATE_FILE = "state.json"
MAP_DIR = "map"
SCENES_FILE = "scenes.pb"


def decode_state(dps: dict[str, Any], key: str, msg_type):
    value = dps.get(key)
    if not isinstance(value, str):
        return None
    try:
        return codec.decode_dps(msg_type, value)
    except (DecodeError, ValueError):
        return None


@dataclass
class Backup:
    captured_at: str
    device: dict[str, Any]
    dps: dict[str, Any]
    map: Snapshot | None
    scenes: SceneWrap | None

    @property
    def map_id(self) -> int | None:
        return self.map.map_id if self.map else codec.current_map_id(self.dps)

    @property
    def timers(self) -> TimerResponse | None:
        t = decode_state(self.dps, codec.DPS_TIMER, TimerResponse)
        return t if t is not None and t.timers else None

    @property
    def scene_list(self) -> SceneResponse | None:
        return decode_state(self.dps, codec.DPS_SCENE, SceneResponse)

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / STATE_FILE).write_text(json.dumps({
            "captured_at": self.captured_at,
            "device": self.device,
            "map_id": self.map_id,
            "dps": self.dps,
        }, indent=2) + "\n")
        (directory / "state_decoded.json").write_text(json.dumps(
            {k: codec.describe_dps(k, v)
             for k, v in sorted(self.dps.items(), key=lambda kv: int(kv[0]))},
            indent=2, ensure_ascii=False) + "\n")
        if self.map is not None:
            self.map.save(directory / MAP_DIR)
        if self.scenes is not None:
            (directory / SCENES_FILE).write_bytes(self.scenes.SerializeToString())
            (directory / "scenes.json").write_text(json.dumps(
                codec.to_dict(self.scenes), indent=2, ensure_ascii=False) + "\n")
        return directory

    @classmethod
    def load(cls, directory: Path) -> Backup:
        state = json.loads((directory / STATE_FILE).read_text())
        snap = None
        if (directory / MAP_DIR / BACKUP_FILE).exists():
            snap = Snapshot.load(directory / MAP_DIR)
        scenes = None
        if (directory / SCENES_FILE).exists():
            scenes = SceneWrap.FromString((directory / SCENES_FILE).read_bytes())
        return cls(state.get("captured_at", "?"), state.get("device", {}), state["dps"], snap,
                   scenes)

    def summary(self) -> list[str]:
        """One line per backed-up category."""
        lines = []
        if self.map is not None:
            names = self.map.room_names()
            areas = {r["id"]: r["area_m2"] for r in self.map.summary()["rooms"]}
            rooms = [f"{names.get(rid, rid)} ({a} m²)" for rid, a in areas.items()]
            rz = self.map.backup.restricted_zone
            lines.append(f"map {self.map_id}: {len(rooms)} rooms: {', '.join(rooms)}")
            lines.append(f"zones: {len(rz.virtual_walls)} virtual walls, "
                         f"{len(rz.forbidden_zones)} no-go, {len(rz.ban_mop_zones)} no-mop")
        else:
            lines.append("map: MISSING (rooms, names and zones can't be restored)")
        listed = self.scene_list
        user_scenes = [i.name for i in listed.infos if i.type == i.SCENE_NORMAL] if listed else []
        if self.scenes is not None:
            lines.append(f"{len(self.scenes.scenes)} scenes with their tasks: "
                         + ", ".join(s.info.name for s in self.scenes.scenes))
        elif user_scenes:
            lines.append(f"scenes: names only ({', '.join(user_scenes)}); their tasks are "
                         "MISSING")
        timers = self.timers
        lines.append(f"{len(timers.timers) if timers else 0} schedules")
        settings = [name for key, name in SETTINGS if key in self.dps]
        lines.append(f"settings: {', '.join(settings)}")
        return lines


# Global settings: backed up and compared, not re-sent (a remap leaves them alone).
SETTINGS = ((codec.DPS_CLEAN_PARAM, "cleaning"), (codec.DPS_STATION, "dock"),
            (codec.DPS_UNDISTURBED, "do-not-disturb"), (codec.DPS_UNISETTING, "general"),
            (codec.DPS_VOICE, "voice"))
# The parts of each that are settings rather than live status.
_SETTING_FIELDS: dict[str, tuple[str, ...] | None] = {
    codec.DPS_CLEAN_PARAM: ("clean_param", "area_clean_param"),
    codec.DPS_STATION: ("auto_cfg_status",),
    codec.DPS_UNDISTURBED: ("undisturbed",),
    codec.DPS_VOICE: ("current_id",),
    codec.DPS_UNISETTING: None,  # everything but the fields below
}
_UNISETTING_STATUS = ("unistate", "ap_signal_strength", "wifi_data")


def settings_changes(ref: dict[str, Any], cur: dict[str, Any]) -> list[str]:
    """Names of the global settings that differ between two DPS states."""
    changed = []
    for key, name in SETTINGS:
        a, b = codec.describe_dps(key, ref.get(key)), codec.describe_dps(key, cur.get(key))
        if not isinstance(a, dict) or not isinstance(b, dict):
            continue
        fields = _SETTING_FIELDS[key]
        if fields is None:
            a = {k: v for k, v in a.items() if k not in _UNISETTING_STATUS}
            b = {k: v for k, v in b.items() if k not in _UNISETTING_STATUS}
        else:
            a = {k: a.get(k) for k in fields}
            b = {k: b.get(k) for k in fields}
        if a != b:
            changed.append(name)
    return changed


def now_label() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")
