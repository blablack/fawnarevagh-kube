"""Map frames from the biz/ MQTT stream: classify, snapshot to disk, render, compare.

The robot publishes map frames on biz/eufy_home/<model>/<sn>/res:
  * ``MapBackup`` after a map edit: occupancy grid + room outline + room params
    + restricted zones of the saved map, in one frame.
  * the same parts as separate frames (``Map``, ``RoomOutline``, ``RoomParams``,
    ``RestrictedZone``, plus ``ObstacleInfo``) when the app opens the map, i.e.
    on a KeepAlive with force_sync, and again after edits. ``MapParts``
    assembles them into a MapBackup. Plain ``Map`` frames also stream while
    cleaning.
  * ``SceneWrap`` (every scene with its tasks) after a scene or room change.
  * possibly ``CleanRecordData`` (the map stored with a cleaning-history entry)
    when the app opens a history record; not yet seen in the wild.
Channel ids are assigned by the robot and change, so frames are recognised by
content. Frame layout and pixel encodings follow eufy-clean's api/map_stream.py
and the comments in proto/cloud/stream.proto and p2pdata.proto.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from google.protobuf.message import DecodeError, Message
from google.protobuf.unknown_fields import UnknownFieldSet
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .codec import lz4_block_decompress, strip_varint_prefix, to_dict
from .proto.cloud.clean_record_pb2 import CleanRecordData
from .proto.cloud.p2pdata_pb2 import CompleteMap
from .proto.cloud.stream_pb2 import (DynamicData, Map, MapBackup, MapDescription, MapInfo,
                                     ObstacleInfo, RestrictedZone, RoomOutline, RoomParams,
                                     SceneWrap)

FRAME_MAP_BACKUP = "map_backup"
FRAME_MAP = "map"
FRAME_CLEAN_RECORD = "clean_record"
FRAME_ROOM_OUTLINE = "room_outline"
FRAME_ROOM_PARAMS = "room_params"
FRAME_RESTRICTED_ZONE = "restricted_zone"
FRAME_SCENES = "scenes"
FRAME_OBSTACLES = "obstacles"
FRAME_MAP_DESCRIPTION = "map_description"
FRAME_POSE = "pose"
FRAME_UNKNOWN = "unknown"

CELL_UNKNOWN, CELL_OBSTACLE, CELL_FREE, CELL_CARPET = 0, 1, 2, 3
CELL_NAMES = {CELL_UNKNOWN: "unknown", CELL_OBSTACLE: "obstacle",
              CELL_FREE: "free", CELL_CARPET: "carpet"}
MAX_ROOM_ID = 31  # room outline ids >= 32 are markers (gap, obstacle, no data)

BACKUP_FILE = "mapbackup.pb"
SUMMARY_FILE = "summary.json"
IMAGE_FILE = "map.png"


def classify_frame(frame: bytes) -> tuple[str, Message | None]:
    """Work out which message a biz/ frame holds.

    Every candidate type parses "successfully" from arbitrary bytes, so each
    match is guarded by fields that only a genuine frame of that type has. A
    MapBackup must be tried before Map: parsed as a Map its room params land in
    ``pixels``.
    """
    try:
        body = strip_varint_prefix(frame)
    except ValueError:
        return FRAME_UNKNOWN, None
    for kind, parse in (
        (FRAME_MAP_BACKUP, _as_map_backup),
        (FRAME_MAP, _as_map),
        (FRAME_CLEAN_RECORD, _as_clean_record),
        (FRAME_ROOM_OUTLINE, _as_room_outline),
        (FRAME_SCENES, _as_scenes),
        # RoomParams before RestrictedZone: parsed as a RestrictedZone, a
        # RoomParams frame's `releases` lands in `map_id`.
        (FRAME_ROOM_PARAMS, _as_room_params),
        (FRAME_RESTRICTED_ZONE, _as_restricted_zone),
        (FRAME_OBSTACLES, _as_obstacles),
        (FRAME_MAP_DESCRIPTION, _as_map_description),
        (FRAME_POSE, _as_pose),
    ):
        try:
            msg = parse(body)
        except DecodeError:
            continue
        if msg is not None:
            return kind, msg
    return FRAME_UNKNOWN, None


def _as_map_backup(body: bytes) -> MapBackup | None:
    mb = MapBackup.FromString(body)
    m = mb.map
    return mb if m.pixels and m.pixel_size and m.info.width and m.info.height else None


def _as_map(body: bytes) -> Map | None:
    m = Map.FromString(body)
    return m if m.pixels and m.pixel_size and m.info.width and m.info.height else None


def _as_clean_record(body: bytes) -> CleanRecordData | None:
    r = CleanRecordData.FromString(body)
    if r.map.pixels and r.map.pixel_size and r.map.info.width and r.map.info.height:
        return r
    cm = r.map_p2p
    return r if cm.map.pixels and cm.map.pixel_size and cm.map_width and cm.map_height else None


def _well_typed(msg: Message) -> bool:
    """No declared field arrived with the wrong wire type.

    Parsing bytes of another message type puts mismatched fields into the
    unknown set under their declared numbers. Fields the proto doesn't declare
    at all are fine: newer firmware adds some (e.g. RestrictedZone field 11).
    """
    declared = {f.number for f in msg.DESCRIPTOR.fields}
    return not any(u.field_number in declared for u in UnknownFieldSet(msg))


def _as_room_outline(body: bytes) -> RoomOutline | None:
    o = RoomOutline.FromString(body)
    ok = o.map_id and o.width and o.height and o.pixels and o.pixel_size == o.width * o.height
    return o if ok and _well_typed(o) else None


def _as_scenes(body: bytes) -> SceneWrap | None:
    w = SceneWrap.FromString(body)
    ok = w.scenes and all(sc.info.id.value and sc.info.name.isprintable() for sc in w.scenes)
    return w if ok and _well_typed(w) else None


def _as_room_params(body: bytes) -> RoomParams | None:
    p = RoomParams.FromString(body)
    ok = p.map_id and p.rooms and all(0 < r.id <= MAX_ROOM_ID for r in p.rooms)
    return p if ok and _well_typed(p) else None


def _as_restricted_zone(body: bytes) -> RestrictedZone | None:
    z = RestrictedZone.FromString(body)
    return z if z.map_id and _well_typed(z) else None


def _as_obstacles(body: bytes) -> ObstacleInfo | None:
    o = ObstacleInfo.FromString(body)
    return o if o.map_id and o.obstacles and _well_typed(o) else None


def _complete_map_to_backup(cm: CompleteMap) -> MapBackup:
    """Re-pack a P2P CompleteMap into the MapBackup layout (it carries no resolution)."""
    info = MapInfo(map_id=cm.map_id, width=cm.map_width, height=cm.map_height,
                   resolution=5, origin=cm.origin)
    info.docks.extend(cm.docks)
    backup = MapBackup(
        map=Map(pixels=cm.map.pixels, pixel_size=cm.map.pixel_size, info=info,
                id=cm.map_id, name=cm.name, releases=cm.releases),
        room_params=cm.room_params,
        restricted_zone=cm.restricted_zones,
    )
    if cm.room_outline.pixels:
        backup.rooms.CopyFrom(RoomOutline(
            map_id=cm.map_id, width=cm.map_width, height=cm.map_height, resolution=5,
            origin=cm.origin, pixels=cm.room_outline.pixels,
            pixel_size=cm.room_outline.pixel_size))
    return backup


def _as_map_description(body: bytes) -> MapDescription | None:
    d = MapDescription.FromString(body)
    name = d.name.strip()
    return d if d.map_id > 0 and name and name.isprintable() and len(name) <= 48 else None


def _as_pose(body: bytes) -> DynamicData | None:
    if len(body) >= 100:
        return None
    d = DynamicData.FromString(body)
    return d if d.cur_pose.x or d.cur_pose.y else None


_UNPACK_2BPP = [bytes((b >> s) & 3 for s in (0, 2, 4, 6)) for b in range(256)]


def _inflate(pixels: bytes, pixel_size: int) -> bytes:
    return pixels if len(pixels) == pixel_size else lz4_block_decompress(pixels, pixel_size)


@dataclass
class Grid:
    """A decoded map: one byte per cell, row 0 at the lowest world y."""

    width: int
    height: int
    resolution: int  # cm per cell
    origin_x: int  # world position (cm) of cell (0, 0)
    origin_y: int
    cells: bytes  # CELL_* values
    rooms: bytes | None  # room id per cell, aligned with ``cells``; None if no outline

    def room_at(self, i: int) -> int:
        if self.rooms is None:
            return 0
        rid = self.rooms[i]
        return rid if 0 < rid <= MAX_ROOM_ID else 0

    def world_to_cell(self, x_cm: float, y_cm: float) -> tuple[float, float]:
        return (x_cm - self.origin_x) / self.resolution, (y_cm - self.origin_y) / self.resolution


class Snapshot:
    """A map frame wrapped as a MapBackup (parts a frame lacks stay empty)."""

    def __init__(self, backup: MapBackup, captured_at: float, source: str) -> None:
        self.backup = backup
        self.captured_at = captured_at
        self.source = source
        self._grid: Grid | None = None

    @classmethod
    def from_frame(cls, kind: str, msg: Message, captured_at: float | None = None) -> Snapshot:
        captured_at = time.time() if captured_at is None else captured_at
        if kind == FRAME_MAP_BACKUP:
            assert isinstance(msg, MapBackup)
            return cls(msg, captured_at, kind)
        if kind == FRAME_MAP:
            assert isinstance(msg, Map)
            return cls(MapBackup(map=msg), captured_at, kind)
        if kind == FRAME_CLEAN_RECORD:
            assert isinstance(msg, CleanRecordData)
            if not msg.map.pixels:
                return cls(_complete_map_to_backup(msg.map_p2p), captured_at, kind)
            backup = MapBackup(map=msg.map, room_params=msg.room_params,
                               restricted_zone=msg.restricted_zone)
            if msg.room_outline.pixels:
                backup.rooms.CopyFrom(msg.room_outline)
            return cls(backup, captured_at, kind)
        raise ValueError(f"not a map frame: {kind}")

    @property
    def complete(self) -> bool:
        """True when the frame carries room outlines and zones (a MapBackup)."""
        return bool(self.backup.rooms.pixels)

    @property
    def map_id(self) -> int:
        b = self.backup
        return (b.desc.map_id or b.map.id or b.room_params.map_id
                or b.restricted_zone.map_id or b.rooms.map_id)

    @property
    def name(self) -> str:
        return (self.backup.desc.name or self.backup.map.name).strip()

    def room_names(self) -> dict[int, str]:
        return {r.id: (r.name.strip() or f"Room {r.id}") for r in self.backup.room_params.rooms}

    def grid(self) -> Grid:
        if self._grid is not None:
            return self._grid
        m = self.backup.map
        w, h = m.info.width, m.info.height
        res = m.info.resolution or 5
        cells = b"".join(_UNPACK_2BPP[b] for b in _inflate(m.pixels, m.pixel_size))[: w * h]
        rooms = None
        ro = self.backup.rooms
        if ro.pixels and ro.width and ro.height:
            outline = _inflate(ro.pixels, ro.pixel_size)
            # Re-sample the outline onto the occupancy grid: both origins are the
            # world position of their own cell (0, 0).
            dx = round((m.info.origin.x - ro.origin.x) / res)
            dy = round((m.info.origin.y - ro.origin.y) / res)
            out = bytearray(b"\xff" * (w * h))
            for y in range(h):
                ry = y + dy
                if not 0 <= ry < ro.height:
                    continue
                for x in range(w):
                    rx = x + dx
                    if 0 <= rx < ro.width:
                        out[y * w + x] = outline[ry * ro.width + rx] >> 2
            rooms = bytes(out)
        self._grid = Grid(w, h, res, m.info.origin.x, m.info.origin.y, cells, rooms)
        return self._grid

    # -- persistence -------------------------------------------------------

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / BACKUP_FILE).write_bytes(self.backup.SerializeToString())
        (directory / SUMMARY_FILE).write_text(json.dumps(self.summary(), indent=2) + "\n")
        render(self).save(directory / IMAGE_FILE)
        return directory

    @classmethod
    def load(cls, directory: Path) -> Snapshot:
        backup = MapBackup.FromString((directory / BACKUP_FILE).read_bytes())
        summary_path = directory / SUMMARY_FILE
        meta = json.loads(summary_path.read_text()) if summary_path.exists() else {}
        return cls(backup, meta.get("captured_at_unix", 0.0), meta.get("source", FRAME_MAP_BACKUP))

    def summary(self) -> dict[str, Any]:
        g = self.grid()
        counts = {name: 0 for name in CELL_NAMES.values()}
        for value, name in CELL_NAMES.items():
            counts[name] = g.cells.count(value)
        cell_m2 = (g.resolution / 100) ** 2
        names = self.room_names()
        info = to_dict(self.backup.map.info)
        return {
            "captured_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.captured_at)),
            "captured_at_unix": self.captured_at,
            "source": self.source,
            "complete": self.complete,
            "map_id": self.map_id,
            "name": self.name,
            "releases": self.backup.desc.releases or self.backup.map.releases,
            "description": to_dict(self.backup.desc),
            "map_info": info,
            "cells": counts,
            "rooms": [
                {"id": rid, "name": names.get(rid, f"Room {rid}"),
                 "area_m2": round(area * cell_m2, 2)}
                for rid, area in sorted(room_areas(g).items())
            ],
            "room_params": to_dict(self.backup.room_params),
            "restricted_zone": to_dict(self.backup.restricted_zone),
        }


_PART_KINDS = (FRAME_MAP, FRAME_ROOM_OUTLINE, FRAME_ROOM_PARAMS, FRAME_RESTRICTED_ZONE)


class MapParts:
    """The latest separate stream frames, assembled into a MapBackup."""

    def __init__(self) -> None:
        self.frames: dict[str, tuple[float, Message]] = {}

    def add(self, kind: str, msg: Message, at: float) -> None:
        if kind in _PART_KINDS:
            self.frames[kind] = (at, msg)

    def complete_since(self, t: float) -> bool:
        """All four parts arrived at or after *t* and describe the same map."""
        if not all(k in self.frames and self.frames[k][0] >= t for k in _PART_KINDS):
            return False
        ids = {getattr(self.frames[k][1], "map_id") for k in _PART_KINDS[1:]}
        return len(ids) == 1

    def snapshot(self) -> Snapshot:
        f = {k: msg for k, (_, msg) in self.frames.items()}
        backup = MapBackup(map=cast(Map, f[FRAME_MAP]), rooms=cast(RoomOutline, f[FRAME_ROOM_OUTLINE]),
                           room_params=cast(RoomParams, f[FRAME_ROOM_PARAMS]),
                           restricted_zone=cast(RestrictedZone, f[FRAME_RESTRICTED_ZONE]))
        backup.desc.map_id = backup.rooms.map_id
        return Snapshot(backup, max(t for t, _ in self.frames.values()), "stream")


def room_areas(g: Grid) -> dict[int, int]:
    """Floor cells per room id."""
    areas: dict[int, int] = {}
    if g.rooms is None:
        return areas
    for i, cell in enumerate(g.cells):
        if cell in (CELL_FREE, CELL_CARPET):
            rid = g.room_at(i)
            if rid:
                areas[rid] = areas.get(rid, 0) + 1
    return areas


# -- rendering ---------------------------------------------------------------

_BASE_COLORS = {
    CELL_UNKNOWN: (34, 34, 38),
    CELL_OBSTACLE: (10, 10, 10),
    CELL_FREE: (205, 205, 205),
    CELL_CARPET: (170, 160, 140),
}
_ROOM_COLORS = [
    (110, 160, 210), (150, 205, 130), (215, 170, 130), (185, 145, 210),
    (215, 200, 110), (135, 200, 210), (215, 135, 160), (160, 210, 185),
]
_ROOM_PALETTE_BASE = 8


def render(snap: Snapshot, target_px: int = 1200) -> Image.Image:
    """Draw the map like the app does: world y up, rooms coloured, zones overlaid."""
    g = snap.grid()
    index = bytearray(g.cells)
    if g.rooms is not None:
        for i, cell in enumerate(g.cells):
            rid = g.room_at(i)
            if rid and cell in (CELL_FREE, CELL_CARPET):
                index[i] = _ROOM_PALETTE_BASE + rid
    palette = [0] * 768
    for value, rgb in _BASE_COLORS.items():
        palette[value * 3:value * 3 + 3] = rgb
    for rid in range(1, MAX_ROOM_ID + 1):
        p = (_ROOM_PALETTE_BASE + rid) * 3
        palette[p:p + 3] = _ROOM_COLORS[(rid - 1) % len(_ROOM_COLORS)]
    img = Image.frombytes("P", (g.width, g.height), bytes(index))
    img.putpalette(palette)
    scale = max(1, target_px // max(g.width, g.height))
    img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM).convert("RGB")
    img = img.resize((g.width * scale, g.height * scale), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(img)

    def to_px(x_cm: float, y_cm: float) -> tuple[float, float]:
        cx, cy = g.world_to_cell(x_cm, y_cm)
        return (cx + 0.5) * scale, (g.height - 1 - cy + 0.5) * scale

    rz = snap.backup.restricted_zone
    for quad, colour in [(q, (220, 40, 40)) for q in rz.forbidden_zones] + \
                        [(q, (240, 150, 30)) for q in rz.ban_mop_zones]:
        pts = [to_px(p.x, p.y) for p in (quad.p0, quad.p1, quad.p2, quad.p3)]
        draw.polygon(pts, outline=colour, width=max(2, scale))
    for wall in rz.virtual_walls:
        draw.line([to_px(wall.p0.x, wall.p0.y), to_px(wall.p1.x, wall.p1.y)],
                  fill=(220, 40, 40), width=max(2, scale))
    for dock in list(snap.backup.map.info.docks) + [d.pose for d in snap.backup.map.info.docks_v2]:
        x, y = to_px(dock.x, dock.y)
        r = max(4, 2 * scale)
        draw.rectangle([x - r, y - r, x + r, y + r], fill=(40, 90, 220), outline=(255, 255, 255))

    if g.rooms is not None:
        names = snap.room_names()
        font = ImageFont.load_default(size=max(12, 4 * scale))
        sums: dict[int, list[int]] = {}
        for i in range(len(g.cells)):
            rid = g.room_at(i)
            if rid:
                s = sums.setdefault(rid, [0, 0, 0])
                s[0] += i % g.width
                s[1] += i // g.width
                s[2] += 1
        for rid, (sx, sy, n) in sums.items():
            x, y = (sx / n + 0.5) * scale, (g.height - 1 - sy / n + 0.5) * scale
            label = f"{rid}: {names.get(rid, '?')}"
            draw.text((x, y), label, fill=(0, 0, 0), anchor="mm", font=font,
                      stroke_width=2, stroke_fill=(255, 255, 255))
    return img


# -- comparison --------------------------------------------------------------

def _mask(g: Grid, cells: tuple[int, ...], left: int, top: int, size: tuple[int, int],
          res: int) -> Image.Image:
    """Mode-1 image of the given cell types on a shared canvas (row 0 = top = max y)."""
    w, h = size
    data = bytearray(w * h)
    ox = round(g.origin_x / res) - left
    oy = round(g.origin_y / res) - top
    wanted = set(cells)
    for i, cell in enumerate(g.cells):
        if cell in wanted:
            x = i % g.width + ox
            y = h - 1 - (i // g.width + oy)
            if 0 <= x < w and 0 <= y < h:
                data[y * w + x] = 255
    return Image.frombytes("L", size, bytes(data)).convert("1", dither=Image.Dither.NONE)


def _count(img: Image.Image) -> int:
    return img.histogram()[255]


def _iou(a: Image.Image, b: Image.Image) -> float:
    union = _count(ImageChops.logical_or(a, b))
    return _count(ImageChops.logical_and(a, b)) / union if union else 1.0


def _dilate(img: Image.Image) -> Image.Image:
    return img.convert("L").filter(ImageFilter.MaxFilter(3)).convert("1", dither=Image.Dither.NONE)


def _centroid(img: Image.Image) -> tuple[float, float]:
    w = img.width
    sx = sy = n = 0
    for i, v in enumerate(img.convert("L").tobytes()):
        if v:
            sx += i % w
            sy += i // w
            n += 1
    return (sx / n, sy / n) if n else (w / 2, img.height / 2)


def compare(ref: Snapshot, other: Snapshot, max_angle: float = 10.0,
            step: float = 0.25) -> dict[str, Any]:
    """How far *other* has drifted from *ref*.

    Overlaps are intersection-over-union of floor cells (and of walls, dilated
    by one cell so a one-cell wobble still counts) in world coordinates. The
    rotation search turns *other* about its floor centroid, re-centres it on
    *ref*'s and keeps the angle with the best floor overlap: a large best-fit
    angle with a much better overlap than at 0° means the map has rotated.
    """
    ga, gb = ref.grid(), other.grid()
    if ga.resolution != gb.resolution:
        raise ValueError(f"resolutions differ: {ga.resolution} vs {gb.resolution} cm")
    res = ga.resolution
    xs = [round(g.origin_x / res) for g in (ga, gb)]
    ys = [round(g.origin_y / res) for g in (ga, gb)]
    left, top = min(xs), min(ys)
    right = max(xs[0] + ga.width, xs[1] + gb.width)
    bottom = max(ys[0] + ga.height, ys[1] + gb.height)
    margin = max(right - left, bottom - top) // 5
    left, top = left - margin, top - margin
    size = (right - left + margin, bottom - top + margin)

    floor = (CELL_FREE, CELL_CARPET)
    fa, fb = _mask(ga, floor, left, top, size, res), _mask(gb, floor, left, top, size, res)
    wa = _mask(ga, (CELL_OBSTACLE,), left, top, size, res)
    wb = _mask(gb, (CELL_OBSTACLE,), left, top, size, res)

    ca, cb = _centroid(fa), _centroid(fb)
    best_angle, best_iou = 0.0, -1.0
    steps = int(round(max_angle / step))
    # Smallest turns first, so a tie keeps the smaller angle (0° for identical maps).
    for k in sorted(range(-steps, steps + 1), key=abs):
        angle = k * step
        moved = fb.rotate(angle, resample=Image.Resampling.NEAREST, center=cb,
                          translate=(round(ca[0] - cb[0]), round(ca[1] - cb[1])))
        iou = _iou(fa, moved)
        if iou > best_iou:
            best_angle, best_iou = angle, iou

    cell_m2 = (res / 100) ** 2
    areas_a, areas_b = room_areas(ga), room_areas(gb)
    names_a, names_b = ref.room_names(), other.room_names()
    rooms = []
    for rid in sorted(set(areas_a) | set(areas_b)):
        rooms.append({
            "id": rid,
            "name_ref": names_a.get(rid), "name_other": names_b.get(rid),
            "area_m2_ref": round(areas_a.get(rid, 0) * cell_m2, 2),
            "area_m2_other": round(areas_b.get(rid, 0) * cell_m2, 2),
        })
    return {
        "map_id_ref": ref.map_id, "map_id_other": other.map_id,
        "floor_m2_ref": round(_count(fa) * cell_m2, 2),
        "floor_m2_other": round(_count(fb) * cell_m2, 2),
        "floor_overlap": round(_iou(fa, fb), 3),
        "wall_overlap": round(_iou(_dilate(wa), _dilate(wb)), 3),
        "centroid_shift_cm": round(math.dist(ca, cb) * res, 1),
        # PIL angles are counter-clockwise; undoing a turn of +θ needs -θ.
        "rotation_deg": -best_angle,
        "floor_overlap_after_rotation": round(best_iou, 3),
        "rooms": rooms,
        "zones_ref": _zone_counts(ref), "zones_other": _zone_counts(other),
    }


def _zone_counts(snap: Snapshot) -> dict[str, int]:
    rz = snap.backup.restricted_zone
    return {"virtual_walls": len(rz.virtual_walls), "forbidden": len(rz.forbidden_zones),
            "no_mop": len(rz.ban_mop_zones)}
