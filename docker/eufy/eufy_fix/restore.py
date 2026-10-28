"""Plan a restore: put a backup's rooms and settings back on the robot's current map.

The robot's map geometry can't be uploaded, but everything layered on top of
it can be re-applied through the same requests the app sends:

  rooms      split / merge the current rooms until they match the backup's
  names      room names, room types and floor types        (RENAME_ROOM)
  custom     per-room cleaning settings and the smart mode  (SET_ROOMS_CUSTOM)
  zones      virtual walls, no-go and no-mop zones          (SET_RESTRICTED_ZONES)
  scenes     scenes, with room ids and zone areas carried over (SceneRequest)
  schedules  schedules, pointing at the restored scenes/rooms   (TimerRequest)

Rooms are matched by where they lie once the two maps are aligned (see
align.py), so room ids may differ between backup and robot. Splits are drawn
as a straight line along the backup's boundary between the two rooms.
"""
from __future__ import annotations

import math
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass

from .align import Alignment
from .codec import encode_varint
from .mapdata import CELL_CARPET, CELL_FREE, MAX_ROOM_ID, Grid
from .proto.cloud.common_pb2 import Point, Quadrangle
from .proto.cloud.map_edit_pb2 import MapEditRequest
from .proto.cloud.scene_pb2 import SceneInfo, SceneRequest, SceneResponse
from .proto.cloud.stream_pb2 import RestrictedZone, RoomParams, SceneWrap
from .proto.cloud.timing_pb2 import TimerInfo, TimerRequest, TimerResponse

PARTS = ("rooms", "names", "custom", "zones", "scenes", "schedules")
MIN_ROOM_M2 = 1.0  # smaller overlaps are alignment noise along room edges
SPLIT_OVERSHOOT_CM = 15  # the app draws split lines ~10 cm into the walls
WALL_CM = 20  # rooms this close count as touching (walls and door sills aren't floor)
_FLOOR = (CELL_FREE, CELL_CARPET)
# The app 6.1 adds MapEditRequest field 4 = {2: 34700} to every map edit (not in
# our proto, meaning unknown; constant across edits). Sent the same way here.
_APP_EDIT_FIELD = bytes.fromhex("2204108c8f02")


def map_edit(**fields) -> MapEditRequest:
    """A MapEditRequest as the app sends it."""
    return MapEditRequest.FromString(MapEditRequest(**fields).SerializeToString() + _APP_EDIT_FIELD)


@dataclass(frozen=True)
class RoomEdit:
    kind: str  # "divide" or "merge"
    rooms: tuple[int, ...]  # divide: (room,); merge: the two rooms
    ref_rooms: tuple[int, ...]  # backup rooms this separates / joins
    points: tuple[tuple[int, int], ...] = ()

    def request(self, map_id: int, seq: int) -> MapEditRequest:
        if self.kind == "divide":
            return map_edit(
                method=MapEditRequest.DIVIDE_ROOM, seq=seq, map_id=map_id,
                divide_room=MapEditRequest.DivideRoom(
                    room_id=self.rooms[0], points=[Point(x=x, y=y) for x, y in self.points]))
        return map_edit(method=MapEditRequest.MERGE_ROOMS, seq=seq, map_id=map_id,
                        merge_rooms=MapEditRequest.MergeRooms(room_ids=list(self.rooms)))

    def describe(self, ref_names: dict[int, str]) -> str:
        names = " / ".join(ref_names.get(r, f"room {r}") for r in self.ref_rooms)
        if self.kind == "divide":
            (x0, y0), (x1, y1) = self.points
            return (f"split room {self.rooms[0]} into {names} "
                    f"along ({x0}, {y0})-({x1}, {y1}) cm")
        return f"merge rooms {self.rooms[0]} + {self.rooms[1]} into {names}"


class RoomLayout:
    """The current map's rooms, against the backup's rooms found on the same cells.

    ``labels`` is the room outline, which also covers the furniture and other
    obstacles inside a room (its floor alone is often in several pieces).
    Areas and overlaps count floor cells only.
    """

    def __init__(self, grid: Grid, ref_labels: list[int]) -> None:
        self.grid = grid
        self.ref = ref_labels
        self.floor = [c in _FLOOR for c in grid.cells]
        self.labels = [grid.room_at(i) for i in range(len(grid.cells))]
        self.min_cells = int(MIN_ROOM_M2 / (grid.resolution / 100) ** 2)

    def copy(self) -> RoomLayout:
        other = RoomLayout.__new__(RoomLayout)
        other.grid, other.ref, other.min_cells = self.grid, self.ref, self.min_cells
        other.floor = self.floor
        other.labels = list(self.labels)
        return other

    # -- geometry helpers -----------------------------------------------------

    def _neighbours(self, i: int):
        w = self.grid.width
        if i % w:
            yield i - 1
        if (i + 1) % w:
            yield i + 1
        if i >= w:
            yield i - w
        if i + w < len(self.labels):
            yield i + w

    def _world(self, i: int) -> tuple[float, float]:
        g = self.grid
        return (g.origin_x + (i % g.width + 0.5) * g.resolution,
                g.origin_y + (i // g.width + 0.5) * g.resolution)

    def _near(self, cells: set[int], cm: float) -> set[int]:
        """Cells within *cm* of *cells* (in steps across any cell type)."""
        reached, frontier = set(cells), set(cells)
        for _ in range(max(1, round(cm / self.grid.resolution))):
            frontier = {j for i in frontier for j in self._neighbours(i)} - reached
            reached |= frontier
        return reached

    def _components(self, cells: set[int]) -> list[list[int]]:
        seen: set[int] = set()
        comps = []
        for start in cells:
            if start in seen:
                continue
            seen.add(start)
            comp, todo = [], deque([start])
            while todo:
                i = todo.popleft()
                comp.append(i)
                for j in self._neighbours(i):
                    if j in cells and j not in seen:
                        seen.add(j)
                        todo.append(j)
            comps.append(comp)
        return comps

    # -- what overlaps what ---------------------------------------------------

    def overlaps(self) -> dict[int, Counter[int]]:
        out: dict[int, Counter[int]] = defaultdict(Counter)
        for label, ref, floor in zip(self.labels, self.ref, self.floor):
            if label and floor:
                out[label][ref] += 1
        return out

    def _ref_totals(self) -> Counter[int]:
        return Counter(r for r, label, floor in zip(self.ref, self.labels, self.floor)
                       if label and r and floor)

    def _significant(self, ov: dict[int, Counter[int]], totals: Counter[int]) -> dict[int, list[int]]:
        """Backup rooms that make up a real part of each current room, biggest first."""
        out = {}
        for room, counts in ov.items():
            area = sum(counts.values())
            out[room] = sorted(
                (r for r, n in counts.items()
                 if r and n >= self.min_cells and (n >= 0.15 * area or n >= 0.5 * totals[r])),
                key=lambda r: -counts[r])
        return out

    def matching(self) -> dict[int, int]:
        """Current room id -> backup room id, one current room per backup room."""
        ov = self.overlaps()
        best: dict[int, tuple[int, int]] = {}
        for room, counts in ov.items():
            area = sum(counts.values())
            ref, n = max(((r, n) for r, n in counts.items() if r), key=lambda rn: rn[1],
                         default=(0, 0))
            if ref and n >= self.min_cells and n >= 0.3 * area:
                if ref not in best or n > best[ref][1]:
                    best[ref] = (room, n)
        return {room: ref for ref, (room, _) in best.items()}

    def unmatched(self) -> tuple[list[int], list[int]]:
        """(current rooms with no backup room, backup rooms not found on the map)."""
        m = self.matching()
        ov = self.overlaps()
        current = [r for r in ov if r not in m and sum(ov[r].values()) >= self.min_cells]
        totals = self._ref_totals()
        missing = [r for r in totals if r not in m.values() and totals[r] >= self.min_cells]
        return sorted(current), sorted(missing)

    # -- planning -------------------------------------------------------------

    def next_edit(self, skip: set[RoomEdit]) -> RoomEdit | None:
        """The next split (first) or merge that brings the rooms closer to the backup.

        A split is only proposed if simulating it gives exactly two pieces that
        follow the backup's two rooms.
        """
        ov = self.overlaps()
        sig = self._significant(ov, self._ref_totals())
        splits = sorted(((ov[room][refs[1]], room, refs[0], refs[1])
                         for room, refs in sig.items() if len(refs) >= 2), reverse=True)
        for _, room, a, b in splits:
            for points in self._split_lines(room, a, b):
                edit = RoomEdit("divide", (room,), (a, b), points)
                if edit not in skip and self.copy().simulate(edit):
                    return edit
        owned: dict[int, list[int]] = defaultdict(list)
        for room, refs in sig.items():
            if len(refs) == 1:
                owned[refs[0]].append(room)
        for ref, rooms in sorted(owned.items()):
            rooms.sort(key=lambda r: -ov[r][ref])
            for i, a in enumerate(rooms):
                for b in rooms[i + 1:]:
                    edit = RoomEdit("merge", (a, b), (ref,))
                    if edit not in skip and self._adjacent(a, b):
                        return edit
        return None

    def _adjacent(self, a: int, b: int) -> bool:
        near_a = self._near({i for i, label in enumerate(self.labels) if label == a}, WALL_CM)
        return any(self.labels[i] == b for i in near_a)

    def _split_lines(self, room: int, a: int, b: int):
        """Candidate straight lines between backup rooms *a* and *b* inside *room*.

        First across each opening where their floor touches (a doorway, or the
        line a room was split along), widest first; then along the whole strip
        where they come within a wall's thickness of each other.
        """
        in_a = {i for i, (label, r) in enumerate(zip(self.labels, self.ref))
                if label == room and r == a}
        in_b = {i for i, (label, r) in enumerate(zip(self.labels, self.ref))
                if label == room and r == b}
        touching = {i for i in in_a | in_b
                    if any(j in (in_b if i in in_a else in_a) for j in self._neighbours(i))}
        openings = sorted(self._components(self._near(touching, self.grid.resolution) & touching
                                           if touching else set()), key=len, reverse=True)
        for edge in openings:
            line = self._fit_line(edge)
            if line is not None:
                yield line
        line = self._fit_line(list((in_a & self._near(in_b, WALL_CM))
                                   | (in_b & self._near(in_a, WALL_CM))))
        if line is not None:
            yield line

    def _fit_line(self, edge: list[int]) -> tuple[tuple[int, int], ...] | None:
        """The principal axis of *edge*, a little past both ends."""
        if len(edge) < 3:
            return None
        pts = [self._world(i) for i in edge]
        mx = sum(p[0] for p in pts) / len(pts)
        my = sum(p[1] for p in pts) / len(pts)
        sxx = sum((p[0] - mx) ** 2 for p in pts)
        syy = sum((p[1] - my) ** 2 for p in pts)
        sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
        theta = 0.5 * math.atan2(2 * sxy, sxx - syy)
        ux, uy = math.cos(theta), math.sin(theta)
        ts = [(p[0] - mx) * ux + (p[1] - my) * uy for p in pts]
        lo = min(ts) - SPLIT_OVERSHOOT_CM - self.grid.resolution
        hi = max(ts) + SPLIT_OVERSHOOT_CM + self.grid.resolution
        return ((round(mx + lo * ux), round(my + lo * uy)),
                (round(mx + hi * ux), round(my + hi * uy)))

    # -- simulation (dry run) ---------------------------------------------------

    def simulate(self, edit: RoomEdit) -> bool:
        """Apply *edit* to the labels the way the robot would; False if it would fail.

        A split is judged on the floor: once the line is cut out, every sizeable
        floor piece must lie (almost) entirely in one of the backup's two rooms,
        and both must be present. Pieces of the second room get a new id;
        everything else in the room (walls, furniture, crumbs) joins the piece
        next to it.
        """
        if edit.kind == "merge":
            a, b = edit.rooms
            sizes = Counter(label for label in self.labels if label in (a, b))
            keep, drop = (a, b) if sizes[a] >= sizes[b] else (b, a)
            self.labels = [keep if label == drop else label for label in self.labels]
            return True
        room = edit.rooms[0]
        a, b = edit.ref_rooms
        (x0, y0), (x1, y1) = edit.points
        cells = {i for i, label in enumerate(self.labels) if label == room}
        floor = {i for i in cells if self.floor[i]}
        reach = 0.75 * self.grid.resolution
        cut = {i for i in floor if _segment_distance(self._world(i), (x0, y0), (x1, y1)) <= reach}
        sides: dict[int, list[int]] = {a: [], b: []}
        for part in self._components(floor - cut):
            if len(part) < self.min_cells:
                continue
            counts = Counter(self.ref[i] for i in part if self.ref[i])
            total = sum(counts.values())
            if not total:
                continue
            owner, n = counts.most_common(1)[0]
            if owner not in sides or n < 0.8 * total:
                return False  # the line doesn't separate the two rooms
            sides[owner].extend(part)
        if not sides[a] or not sides[b]:
            return False
        keep, move = (a, b) if len(sides[a]) >= len(sides[b]) else (b, a)
        free = [r for r in range(1, MAX_ROOM_ID + 1) if r not in set(self.labels)]
        if not free:
            return False
        for i in sides[move]:
            self.labels[i] = free[0]
        assigned = set(sides[keep]) | set(sides[move])
        todo = deque(assigned)
        while todo:
            i = todo.popleft()
            for j in self._neighbours(i):
                if j in cells and j not in assigned:
                    assigned.add(j)
                    self.labels[j] = self.labels[i]
                    todo.append(j)
        return True


def _segment_distance(p: tuple[float, float], a: tuple[float, float],
                      b: tuple[float, float]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = 0.0 if not length2 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def plan_rooms(layout: RoomLayout, max_edits: int = 40) -> tuple[list[RoomEdit], RoomLayout]:
    """Simulate splits/merges until the rooms match; return them and the final layout."""
    sim = layout.copy()
    edits: list[RoomEdit] = []
    for _ in range(max_edits):
        edit = sim.next_edit(set(edits))
        if edit is None:
            break
        sim.simulate(edit)
        edits.append(edit)
    return edits, sim


# -- requests for everything else ------------------------------------------------

def _room_key(room: RoomParams.Room) -> tuple:
    return (room.name, room.floor.type, room.scene.type, room.scene.index.value)


def name_requests(map_id: int, matching: dict[int, int], ref: RoomParams,
                  cur: RoomParams) -> list[tuple[str, MapEditRequest]]:
    ref_rooms = {r.id: r for r in ref.rooms}
    cur_rooms = {r.id: r for r in cur.rooms}
    out = []
    for room, ref_id in sorted(matching.items()):
        want = ref_rooms.get(ref_id)
        if want is None:
            continue
        have = cur_rooms.get(room, RoomParams.Room(id=room))
        if _room_key(have) == _room_key(want):
            continue
        desc = MapEditRequest.RoomDesc(id=room, name=want.name)
        desc.floor.CopyFrom(want.floor)
        desc.scene.CopyFrom(want.scene)
        label = want.name or "(unnamed)"
        out.append((f"room {room}: {have.name or '(unnamed)'} -> {label}",
                    map_edit(method=MapEditRequest.RENAME_ROOM, map_id=map_id,
                             room_desc=desc)))
    return out


def custom_request(map_id: int, matching: dict[int, int], ref: RoomParams,
                   cur: RoomParams, rooms_on_map: list[int]) -> MapEditRequest | None:
    """Per-room settings and order for every room on the map (unmatched ones kept)."""
    ref_rooms = {r.id: r for r in ref.rooms}
    cur_rooms = {r.id: r for r in cur.rooms}
    custom = MapEditRequest.RoomsCustom()
    custom.smart_mode_sw.CopyFrom(ref.smart_mode_sw)
    changed = cur.smart_mode_sw != ref.smart_mode_sw
    for room in sorted(rooms_on_map):
        have = cur_rooms.get(room, RoomParams.Room(id=room))
        want = ref_rooms.get(matching.get(room, -1), have)
        part = custom.rooms_parm.rooms.add(id=room)
        part.custom.ParseFromString(want.custom.SerializeToString())
        if want.order.value:
            custom.rooms_order.rooms.add(id=room, order=want.order.value)
        changed |= (have.custom.SerializeToString() != want.custom.SerializeToString()
                    or have.order.value != want.order.value)
    if not changed:
        return None
    return map_edit(method=MapEditRequest.SET_ROOMS_CUSTOM, map_id=map_id,
                    rooms_custom=custom)


def _move(p: Point, al: Alignment) -> None:
    x, y = al.to_other(p.x, p.y)
    p.x, p.y = round(x), round(y)


def _move_quad(q: Quadrangle, al: Alignment) -> None:
    for p in (q.p0, q.p1, q.p2, q.p3):
        _move(p, al)


def _zone_points(z: RestrictedZone) -> list[tuple[int, int]]:
    pts = []
    for w in z.virtual_walls:
        pts += [(w.p0.x, w.p0.y), (w.p1.x, w.p1.y)]
    for q in list(z.forbidden_zones) + list(z.ban_mop_zones):
        pts += [(p.x, p.y) for p in (q.p0, q.p1, q.p2, q.p3)]
    return pts


def zones_request(map_id: int, ref: RestrictedZone, cur: RestrictedZone,
                  al: Alignment) -> MapEditRequest | None:
    zones = RestrictedZone()
    zones.CopyFrom(ref)  # keeps fields this proto doesn't declare (newer firmware)
    zones.map_id = map_id
    zones.releases = cur.releases
    zones.ClearField("suggestion")
    for w in zones.virtual_walls:
        _move(w.p0, al)
        _move(w.p1, al)
    for q in list(zones.forbidden_zones) + list(zones.ban_mop_zones):
        _move_quad(q, al)
    same_shape = (len(zones.virtual_walls), len(zones.forbidden_zones), len(zones.ban_mop_zones)) \
        == (len(cur.virtual_walls), len(cur.forbidden_zones), len(cur.ban_mop_zones))
    if same_shape and all(math.dist(a, b) <= 5 for a, b in zip(_zone_points(zones),
                                                                 _zone_points(cur))):
        return None
    return map_edit(method=MapEditRequest.SET_RESTRICTED_ZONES, map_id=map_id,
                    restricted_zone=zones)


def _scene_for_map(scene: SceneWrap.Scene, map_id: int, rooms: dict[int, int],
                   al: Alignment, warnings: list[str]) -> SceneRequest.Scene:
    """The backup's scene as a request, with room ids and zones carried over."""
    out = SceneRequest.Scene()
    out.info.CopyFrom(SceneInfo(id=scene.info.id, valid=True, name=scene.info.name,
                                mapid=map_id, index=scene.info.index))
    for task in scene.tasks:
        t = out.tasks.add()
        t.CopyFrom(task)
        if not t.HasField("current_room"):
            continue
        keep = []
        for unit in t.current_room.units:
            if unit.HasField("room_clean"):
                ref_room = unit.room_clean.room_id
                if ref_room not in rooms:
                    warnings.append(f"scene {scene.info.name!r}: room {ref_room} is not on the "
                                    "map any more; left out")
                    continue
                unit.room_clean.room_id = rooms[ref_room]
            elif unit.HasField("zone_clean"):
                _move_quad(unit.zone_clean.quadrangle, al)
            keep.append(unit)
        del t.current_room.units[:]
        t.current_room.units.extend(keep)
    return out


_SCENE_TIMER_TAG = bytes([4 << 3 | 2])  # SceneRequest.Scene field 4, newer than our proto


def _with_schedule(scene: SceneRequest.Scene, timer: TimerInfo, user_id: str,
                   now_ms: int) -> SceneRequest.Scene:
    """Embed the scene's schedule the way the app 6.1 does when it saves a scene.

    The app puts a TimerInfo in Scene field 4 (with an empty id and an empty
    scene-clean action) and then also sends the TimerRequest on its own.
    """
    t = TimerInfo(status=timer.status, desc=timer.desc)
    t.id.SetInParent()
    t.addition.create_time, t.addition.create_user_id = now_ms, user_id
    t.addition.renew_time, t.addition.renew_user_id = now_ms, user_id
    t.action.type = TimerInfo.Action.SCHEDULE_SCENE_CLEAN
    t.action.sche_scene_clean.SetInParent()
    body = t.SerializeToString()
    raw = scene.SerializeToString() + _SCENE_TIMER_TAG + encode_varint(len(body)) + body
    return SceneRequest.Scene.FromString(raw)  # the extra field is kept as unknown


def scene_requests(ref: SceneWrap, cur_list: SceneResponse | None, cur: SceneWrap | None,
                   map_id: int, rooms: dict[int, int], al: Alignment,
                   timers: TimerResponse | None, user_id: str,
                   warnings: list[str]) -> list[tuple[str, SceneRequest, int]]:
    """MODIFY the backup's own scenes that differ, ADD the ones that are gone.

    The robot's built-in scenes (whole-house daily/deep, after dinner, pets)
    are left alone.
    """
    existing = {i.id.value: i for i in cur_list.infos} if cur_list else {}
    current = {s.info.id.value: s for s in cur.scenes} if cur else {}
    schedule = {t.action.sche_scene_clean.scene_id: t for t in (timers.timers if timers else [])
                if t.action.HasField("sche_scene_clean")}
    now_ms = int(time.time() * 1000)
    out = []
    for scene in ref.scenes:
        if scene.info.type != SceneInfo.SCENE_NORMAL:
            continue
        want = _scene_for_map(scene, map_id, rooms, al, warnings)
        sid = scene.info.id.value
        have = current.get(sid)
        if have is not None and have.info.name == want.info.name \
                and have.info.mapid == map_id and have.info.valid \
                and list(have.tasks) == list(want.tasks):
            continue
        if sid in schedule:
            want = _with_schedule(want, schedule[sid], user_id, now_ms)
        if sid in existing:
            out.append((f"update scene {scene.info.name!r}",
                        SceneRequest(method=SceneRequest.MODIFY_SCENE, scene=want), sid))
        else:
            want.info.ClearField("id")
            out.append((f"add scene {scene.info.name!r}",
                        SceneRequest(method=SceneRequest.ADD_SCENE, scene=want), sid))
    return out


def _bare_timer(timer: TimerInfo) -> TimerInfo:
    """A copy without the bookkeeping the robot adds (who/when, the scene's name)."""
    t = TimerInfo()
    t.CopyFrom(timer)
    t.ClearField("addition")
    if t.action.HasField("sche_scene_clean"):
        t.action.sche_scene_clean.ClearField("scene_name")
    return t


def _timer_for_map(timer: TimerInfo, map_id: int, rooms: dict[int, int],
                   scene_ids: dict[int, int], warnings: list[str]) -> TimerInfo:
    t = _bare_timer(timer)
    action = t.action
    if action.HasField("sche_scene_clean"):
        old = action.sche_scene_clean.scene_id
        action.sche_scene_clean.scene_id = scene_ids.get(old, old)
    elif action.HasField("sche_rooms_clean"):
        rc = action.sche_rooms_clean
        for part in (rc.general, rc.custom):
            if part.map_id:
                part.map_id = map_id
            gone = [i for i, r in enumerate(part.rooms) if r.id not in rooms]
            if gone:
                warnings.append(f"schedule {timer.id.value}: some rooms are not on the map any "
                                "more; left out")
            for i in reversed(gone):
                del part.rooms[i]
            for r in part.rooms:
                r.id = rooms[r.id]
    elif action.HasField("sche_cruise"):
        action.sche_cruise.map_id = map_id
    return t


def timer_requests(ref: TimerResponse, cur: TimerResponse | None, map_id: int,
                   rooms: dict[int, int], scene_ids: dict[int, int], user_id: str,
                   warnings: list[str]) -> list[tuple[str, TimerRequest]]:
    existing = {t.id.value: t for t in cur.timers} if cur else {}
    # A re-added scene may have brought its schedule along under a new id.
    by_scene = {t.action.sche_scene_clean.scene_id: t for t in existing.values()
                if t.action.HasField("sche_scene_clean")}
    now_ms = int(time.time() * 1000)
    out = []
    for timer in ref.timers:
        want = _timer_for_map(timer, map_id, rooms, scene_ids, warnings)
        have = existing.get(timer.id.value)
        if have is None and want.action.HasField("sche_scene_clean"):
            have = by_scene.get(want.action.sche_scene_clean.scene_id)
            if have is not None:
                want.id.CopyFrom(have.id)
        if have is not None:
            if _bare_timer(have) == want:
                continue
            want.addition.renew_time, want.addition.renew_user_id = now_ms, user_id
            out.append((f"update schedule {want.id.value} ({describe_timer(want)})",
                        TimerRequest(method=TimerRequest.MOTIFY, timer=want)))
        else:
            want.ClearField("id")
            want.addition.create_time, want.addition.create_user_id = now_ms, user_id
            want.addition.renew_time, want.addition.renew_user_id = now_ms, user_id
            out.append((f"add schedule ({describe_timer(want)})",
                        TimerRequest(method=TimerRequest.ADD, timer=want)))
    return out


_DAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")


def describe_timer(t: TimerInfo) -> str:
    d = t.desc
    when = f"{d.timing.hours:02d}:{d.timing.minutes:02d}"
    if d.trigger == TimerInfo.Desc.CYCLE:
        days = [name for bit, name in enumerate(_DAYS) if d.cycle.week_bits >> bit & 1]
        when += " " + ",".join(days)
    else:
        when += " once"
    kind = TimerInfo.Action.Type.Name(t.action.type).removeprefix("SCHEDULE_").lower()
    state = "on" if t.status.opened else "off"
    return f"{when}, {kind}, {state}"
