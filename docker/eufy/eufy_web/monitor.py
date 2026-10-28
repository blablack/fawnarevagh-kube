"""Holds one MQTT session to the robot and logs what each clean does to the map.

After a clean ends (the robot is back on its dock and stays there for a few
minutes) it takes a snapshot and compares it with the reference map. In
`recover` mode it also sends MAP_RECOVERY, snapshots again and compares again.
Everything that talks to the robot runs on this thread: web handlers hand it
callables through `call()`.
"""
from __future__ import annotations

import argparse
import json
import logging
import queue
import shutil
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Callable

import eufy_map
from eufy_fix import codec
from eufy_fix.mapdata import Snapshot, compare
from eufy_fix.proto.cloud.multi_maps_pb2 import MultiMapsManageRequest, MultiMapsManageResponse
from eufy_fix.proto.cloud.work_status_pb2 import WorkStatus
from eufy_fix.robot import Robot

log = logging.getLogger("eufy_web")

MODES = ("off", "observe", "recover")
SESSION_SECONDS = 30 * 60  # reconnect now and then; the login is cached
KEEP_HISTORY_DIRS = 100
DPS_BATTERY = "163"


class Settings:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {"mode": "observe", "reference": None, "delay": 300}
        try:
            self.data.update(json.loads(path.read_text()))
        except (OSError, ValueError):
            pass

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def update(self, **values: Any) -> None:
        self.data.update(values)
        self.path.write_text(json.dumps(self.data, indent=2) + "\n")


class Monitor(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True, name="monitor")
        self.data = eufy_map.DATA
        self.settings = Settings(self.data / "settings.json")
        self.history_file = self.data / "history.jsonl"
        self.history_dir = self.data / "history"
        self.latest_dir = self.data / "latest"
        self.status: dict[str, Any] = {"connected": False, "state": None, "map_id": None,
                                       "battery": None, "error": None, "last_message": None,
                                       "waiting": None}
        self.job_running: Callable[[], bool] = lambda: False
        self.halt = threading.Event()
        self._tasks: queue.Queue[tuple[Callable[[Robot], Any], Future]] = queue.Queue()
        self._was_busy = False
        self._saw_mapping = False
        self._docked_since: float | None = None
        self._reference: tuple[str, Snapshot] | None = None

    # -- called from the web side ----------------------------------------------

    def call(self, fn: Callable[[Robot], Any], timeout: float = 180) -> Any:
        future: Future = Future()
        self._tasks.put((fn, future))
        return future.result(timeout)

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        try:
            lines = self.history_file.read_text().splitlines()
        except OSError:
            return []
        return [json.loads(line) for line in lines[-limit:]][::-1]

    # -- the session ----------------------------------------------------------

    def run(self) -> None:
        ns = argparse.Namespace(config=str(self.data / "config.json"), device=None)
        backoff = 10
        while not self.halt.is_set():
            try:
                account, device = eufy_map.connect_account(ns)
                with Robot(account, device, None) as robot:
                    self.status.update(connected=True, error=None)
                    backoff = 10
                    deadline = time.time() + SESSION_SECONDS
                    self._capture(robot, "startup")
                    while not self.halt.is_set() and time.time() < deadline:
                        robot.pump(1)
                        self._tick(robot)
                        self._drain(robot)
            except (Exception, SystemExit) as e:  # connect_account exits on setup errors
                log.exception("robot session failed")
                self.status.update(error=str(e) or type(e).__name__)
                self.halt.wait(backoff)
                backoff = min(backoff * 2, 300)
            finally:
                self.status["connected"] = False

    def _drain(self, robot: Robot) -> None:
        while True:
            try:
                fn, future = self._tasks.get_nowait()
            except queue.Empty:
                return
            try:
                future.set_result(fn(robot))
            except BaseException as e:  # noqa: BLE001 - handed to the caller
                future.set_exception(e)

    def _tick(self, robot: Robot) -> None:
        now = time.time()
        state = eufy_map.work_state(robot.dps)
        battery = robot.dps.get(DPS_BATTERY)
        self.status.update(
            state=WorkStatus.State.Name(state) if state is not None else None,
            map_id=codec.current_map_id(robot.dps),
            battery=battery if isinstance(battery, int) else None,
            last_message=now)
        if state is None:
            return
        if state in eufy_map.BUSY_STATES:
            self._was_busy = True
            self._docked_since = None
            self.status["waiting"] = None
            if state == WorkStatus.FAST_MAPPING:
                self._saw_mapping = True
        elif self._was_busy and state == WorkStatus.CHARGING:
            # The mop wash and dust bin emptying come after docking, and the robot
            # flips back to CLEANING for the wash: wait until it stays put.
            if self._docked_since is None:
                self._docked_since = now
            wait = self.settings["delay"] - (now - self._docked_since)
            self.status["waiting"] = max(0, int(wait))
            if wait <= 0 and not self.job_running():
                self._after_clean(robot)
        else:
            self._docked_since = None
            self.status["waiting"] = None

    # -- maps -----------------------------------------------------------------

    def _capture(self, robot: Robot, label: str) -> tuple[Snapshot, Path] | None:
        snap = robot.sync_map(30)
        if snap is None:
            return None
        dest = snap.save(self.history_dir / f"{eufy_map.stamp()}_{label}")
        self.latest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(dest / "map.png", self.latest_dir / "map.png")
        (self.latest_dir / "latest.json").write_text(json.dumps(
            {"t": time.time(), "label": label, "map_id": snap.map_id}))
        for old in sorted(p for p in self.history_dir.iterdir() if p.is_dir())[:-KEEP_HISTORY_DIRS]:
            shutil.rmtree(old, ignore_errors=True)
        return snap, dest

    def reference(self) -> Snapshot | None:
        name = self.settings["reference"]
        if not name:
            return None
        if self._reference is None or self._reference[0] != name:
            try:
                snap = Snapshot.load(eufy_map.map_dir(str(eufy_map.BACKUPS / name)))
            except (OSError, ValueError):
                return None
            self._reference = (name, snap)
        return self._reference[1]

    def set_reference_here(self, robot: Robot) -> str:
        """Save the robot's current map as a new snapshot and make it the reference."""
        snap = robot.sync_map(30)
        if snap is None:
            raise RuntimeError("the robot sent no map")
        dest = snap.save(eufy_map.BACKUPS / f"{eufy_map.stamp()}_map{snap.map_id}_reference")
        self.settings.update(reference=dest.name)
        return dest.name

    def _record(self, entry: dict[str, Any]) -> None:
        self.data.mkdir(parents=True, exist_ok=True)
        with self.history_file.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    @staticmethod
    def _overlaps(ref: Snapshot, snap: Snapshot) -> dict[str, float]:
        r = compare(ref, snap)
        return {"floor": r["floor_overlap"], "walls": r["wall_overlap"], "rotation": r["rotation_deg"]}

    def cycle(self, robot: Robot, kind: str, recover: bool) -> dict[str, Any]:
        """Snapshot, optionally recover, snapshot again; log how each compares with the reference."""
        entry: dict[str, Any] = {"t": time.time(), "kind": kind,
                                 "mode": "recover" if recover else "observe"}
        ref = self.reference()
        got = self._capture(robot, kind)
        if got is None:
            entry["note"] = "the robot sent no map"
            self._record(entry)
            return entry
        before, before_dir = got
        entry.update(map_id=before.map_id, dir=before_dir.name)
        usable = ref is not None and ref.map_id == before.map_id
        if ref is None:
            entry["note"] = "no reference map set"
        elif not usable:
            entry["note"] = f"map {before.map_id} is not the reference map {ref.map_id}"
        else:
            entry["before"] = self._overlaps(ref, before)
        if recover and (usable or kind == "manual"):
            state = eufy_map.work_state(robot.dps)
            if state in eufy_map.BUSY_STATES:
                entry["recover"] = "refused: the robot is busy"
            else:
                req = MultiMapsManageRequest(
                    method=MultiMapsManageRequest.MAP_RECOVERY, seq=robot.next_seq(),
                    common=MultiMapsManageRequest.Common(cloud_mapid=before.map_id))
                reply = robot.request(codec.DPS_MULTI_MAP_MANAGE, req, MultiMapsManageResponse)
                entry["recover"] = ("no answer" if reply is None
                                    else MultiMapsManageResponse.Result.Name(reply.result))
                robot.pump(20)  # the robot republishes its map
                after = self._capture(robot, "recovered")
                if after is not None:
                    entry["after_dir"] = after[1].name
                    if usable:
                        entry["after"] = self._overlaps(ref, after[0])
        elif recover:
            entry["recover"] = "skipped: needs a reference map"
        self._record(entry)
        return entry

    def _after_clean(self, robot: Robot) -> None:
        mapped = self._saw_mapping
        self._was_busy = self._saw_mapping = False
        self._docked_since = None
        self.status["waiting"] = None
        mode = self.settings["mode"]
        if mode == "off":
            return
        if mapped:
            self._record({"t": time.time(), "kind": "clean", "mode": mode,
                          "note": "the robot mapped during this run; left alone"})
            return
        self.cycle(robot, "clean", mode == "recover")
