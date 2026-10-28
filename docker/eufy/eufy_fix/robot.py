"""A live MQTT session with one robot.

Keeps the robot's latest DPS values, map frames and scenes as they arrive,
asks for a fresh map the way the app does, and sends requests that wait for
the ack carrying the same ``seq``.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from google.protobuf.message import DecodeError, Message

from . import codec
from .cloud import Account, Device
from .mapdata import (FRAME_MAP_BACKUP, FRAME_SCENES, MapParts, Snapshot, classify_frame)
from .mqtt import EufyMqtt, decode_biz_payload, decode_cmd_payload
from .proto.cloud.app_device_info_pb2 import AppInfo
from .proto.cloud.keepalive_pb2 import KeepAliveRequest
from .proto.cloud.stream_pb2 import MapBackup, SceneWrap
from .proto.cloud.version_pb2 import AppFunction

R = TypeVar("R", bound=Message)

# What the Android app 6.1.20 announces when its map screen opens.
_APP_VERSION = "6.1.20_31181"


class Robot:
    def __init__(self, account: Account, device: Device, log_path: Path | None = None) -> None:
        self.account = account
        self.device = device
        self.dps: dict[str, Any] = dict(device.dps)
        self.parts = MapParts()
        self.saved_map: Snapshot | None = None  # last MapBackup frame
        self.scenes: SceneWrap | None = None
        self.scenes_at = 0.0
        self._replies: list[tuple[float, str, str]] = []  # (received_at, DPS key, raw value)
        self._client = EufyMqtt(account.mqtt, account.openudid, device.sn, device.model)
        self._log_path = log_path
        self._log = None
        self._seq = int(time.time()) % 100000

    def __enter__(self) -> Robot:
        if self._log_path is not None:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log = self._log_path.open("a")
        self._client.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self._client.close()
        if self._log is not None:
            self._log.close()

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    # -- receiving -------------------------------------------------------------

    def _handle(self, msg) -> None:
        if self._log is not None:
            self._log.write(json.dumps({"t": msg.received_at, "topic": msg.topic,
                                        "payload": msg.payload.decode(errors="replace")}) + "\n")
            self._log.flush()
        if msg.is_request:
            return
        if not msg.is_biz:
            for key, value in (decode_cmd_payload(msg.payload) or {}).items():
                self.dps[key] = value
                if isinstance(value, str):
                    self._replies.append((msg.received_at, key, value))
            return
        biz = decode_biz_payload(msg.payload)
        if biz is None:
            return
        kind, decoded = classify_frame(biz[1])
        if decoded is None:
            return
        if kind == FRAME_MAP_BACKUP:
            assert isinstance(decoded, MapBackup)
            self.saved_map = Snapshot(decoded, msg.received_at, kind)
        elif kind == FRAME_SCENES:
            assert isinstance(decoded, SceneWrap)
            self.scenes, self.scenes_at = decoded, msg.received_at
        else:
            self.parts.add(kind, decoded, msg.received_at)

    def pump(self, seconds: float, until: Callable[[], bool] | None = None) -> bool:
        """Process messages for up to *seconds*; stop early once *until()* holds."""
        if until is not None and until():
            return True
        for msg in self._client.iter_messages(seconds):
            self._handle(msg)
            if until is not None and until():
                return True
        return False

    # -- map -------------------------------------------------------------------

    def map_since(self, t: float) -> Snapshot | None:
        """The newest complete map received at or after *t* (saved copy preferred)."""
        if self.saved_map is not None and self.saved_map.captured_at >= t:
            return self.saved_map
        if self.parts.complete_since(t):
            return self.parts.snapshot()
        return None

    def sync_map(self, timeout: float = 30) -> Snapshot | None:
        """Make the robot stream its map, as when the app opens the map screen.

        The app sends AppInfo, then a KeepAlive with force_sync; the robot
        answers within a second with the map, room outline, room params,
        zones and obstacles. Neither message changes anything on the robot.
        """
        t0 = time.time()
        info = AppInfo(platform=AppInfo.PF_ANDROID, app_version=_APP_VERSION,
                       user_id=self.account.mqtt["user_id"],
                       app_function=AppFunction(multi_maps=AppFunction.Module(options=1),
                                                optimization=AppFunction.Module(version=1,
                                                                                options=14)))
        now_us = int(t0 * 1e6)
        self._client.send_dps({codec.DPS_APP_INFO: codec.encode_dps(info)})
        self._client.send_dps({codec.DPS_KEEPALIVE: codec.encode_dps(
            KeepAliveRequest(timestamp=now_us, force_sync=True))})
        self.pump(timeout, lambda: self.parts.complete_since(t0))
        return self.map_since(t0)

    # -- requests --------------------------------------------------------------

    def request(self, key: str, msg: Message, response_type: type[R],
                reply_keys: tuple[str, ...] | None = None, timeout: float = 30,
                final: Callable[[R], bool] = lambda r: True) -> R | None:
        """Send *msg* on DPS *key*; return the reply with the same seq, or None.

        Replies that *final* rejects (e.g. a STARTED ack) are skipped while
        waiting for the next one.
        """
        seq = getattr(msg, "seq")
        keys = reply_keys or (key,)
        start = len(self._replies)
        found: list[R] = []

        def answered() -> bool:
            nonlocal start
            for _, k, value in self._replies[start:]:
                if k not in keys:
                    continue
                try:
                    reply = codec.decode_dps(response_type, value)
                except (DecodeError, ValueError):
                    continue
                if getattr(reply, "seq") == seq:
                    found.append(reply)
                    if final(reply):
                        return True
            start = len(self._replies)
            return False

        self._client.send_dps({key: codec.encode_dps(msg)})
        self.pump(timeout, answered)
        return found[-1] if found else None
