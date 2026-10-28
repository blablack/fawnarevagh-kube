"""Eufy cloud MQTT transport (mutual TLS on port 8883).

Adapted from eufy-clean's api/client.py: same topics and command envelope,
rewritten for paho-mqtt 2.x with a blocking, queue-based receive loop.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import ssl
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Any

from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

_LOGGER = logging.getLogger(__name__)

# The broker drops (rather than refuses) a session whose subscriptions it doesn't
# allow; paho then reconnects forever. Give up after this many drops in a row.
MAX_DROPS = 5


@dataclass
class Message:
    topic: str
    payload: bytes
    received_at: float

    @property
    def is_biz(self) -> bool:
        return self.topic.startswith("biz/")

    @property
    def is_request(self) -> bool:
        """Sent *to* the robot (by the app, or echoed back from us)."""
        return self.topic.endswith("/req") or self.topic.startswith("smart/mb/")


class EufyMqtt:
    """One MQTT session bound to a single robot."""

    def __init__(self, creds: dict[str, Any], openudid: str, device_sn: str,
                 device_model: str, watch_requests: bool = False) -> None:
        self.creds = creds
        self.watch_requests = watch_requests
        self.openudid = openudid
        self.device_sn = device_sn
        self.device_model = device_model
        self.messages: queue.Queue[Message] = queue.Queue()
        self._connected = threading.Event()
        self._client_id = (
            f"android-{creds['app_name']}-eufy_android_{openudid}_{creds['user_id']}"
            f"-{int(time.time() * 1000)}"
        )
        self._client: mqtt.Client | None = None
        self._drops = 0

    @property
    def _cmd_topic(self) -> str:
        return f"cmd/eufy_home/{self.device_model}/{self.device_sn}"

    @property
    def _biz_topic(self) -> str:
        return f"biz/eufy_home/{self.device_model}/{self.device_sn}"

    def connect(self, timeout: float = 20) -> None:
        client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=self._client_id,
            protocol=mqtt.MQTTv311,
        )
        client.username_pw_set(self.creds["thing_name"])
        # tls_set() loads the key pair into the SSL context immediately, so the
        # temp files only need to exist for the duration of the call.
        with tempfile.TemporaryDirectory() as tmp:
            cert = os.path.join(tmp, "cert.pem")
            key = os.path.join(tmp, "key.pem")
            with open(cert, "w") as f:
                f.write(self.creds["certificate_pem"])
            with open(os.open(key, os.O_WRONLY | os.O_CREAT, 0o600), "w") as f:
                f.write(self.creds["private_key"])
            client.tls_set(certfile=cert, keyfile=key, cert_reqs=ssl.CERT_REQUIRED,
                           tls_version=ssl.PROTOCOL_TLSv1_2)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        self._client = client
        _LOGGER.debug("Connecting to %s as %s", self.creds["endpoint_addr"], self._client_id)
        client.connect(self.creds["endpoint_addr"], 8883, 60)
        client.loop_start()
        if not self._connected.wait(timeout):
            self.close()
            raise TimeoutError("MQTT connection timed out")

    def close(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None

    def __enter__(self) -> EufyMqtt:
        if self._client is None:
            self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            _LOGGER.error("MQTT connect refused: %s", reason_code)
            return
        client.subscribe(f"{self._cmd_topic}/res")
        client.subscribe(f"{self._biz_topic}/res")
        if self.watch_requests:
            # What the app sends to the robot. Topics from albertoxamin/eufyhome.
            client.subscribe(f"{self._cmd_topic}/req")
            client.subscribe(f"{self._biz_topic}/req")
            client.subscribe(f"smart/mb/+/{self.device_sn}")
        self._connected.set()

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        self._connected.clear()
        if reason_code.is_failure:
            self._drops += 1
            _LOGGER.warning("MQTT disconnected unexpectedly: %s", reason_code)

    def _on_message(self, client, userdata, msg) -> None:
        self._drops = 0
        self.messages.put(Message(msg.topic, msg.payload, time.time()))

    def send_dps(self, dps: dict[str, Any]) -> None:
        """Publish a DPS write ({dps_key: value}) to the robot."""
        if not self._client or not self._connected.is_set():
            raise RuntimeError("MQTT not connected")
        ts = int(time.time() * 1000)
        inner = json.dumps({
            "account_id": self.creds["user_id"],
            "data": dps,
            "device_sn": self.device_sn,
            "protocol": 2,
            "t": ts,
        })
        envelope = {
            "head": {
                "client_id": self._client_id,
                "cmd": 65537,
                "cmd_status": 2,
                "msg_seq": 1,
                "seed": "",
                "sess_id": self._client_id,
                "sign_code": 0,
                "timestamp": ts,
                "version": "1.0.0.1",
            },
            "payload": inner,
        }
        _LOGGER.debug("Publishing %s", dps)
        info = self._client.publish(f"{self._cmd_topic}/req", json.dumps(envelope).encode())
        info.wait_for_publish(10)

    def iter_messages(self, seconds: float | None):
        """Yield incoming messages until *seconds* elapse (forever if None)."""
        deadline = None if seconds is None else time.monotonic() + seconds
        while True:
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                return
            if self._drops >= MAX_DROPS:
                raise ConnectionError(
                    "the MQTT broker keeps closing the connection; these credentials "
                    "probably have no access to this robot (delete .eufy_state.json "
                    "to force a fresh login)")
            try:
                yield self.messages.get(timeout=min(remaining or 1.0, 1.0))
            except queue.Empty:
                continue


def decode_cmd_payload(payload: bytes) -> dict[str, Any] | None:
    """Return the DPS dict from a cmd/.../res message, or None."""
    try:
        msg = json.loads(payload)
        data = msg.get("payload", {})
        if isinstance(data, str):
            data = json.loads(data)
        dps = data.get("data")
        return dps if isinstance(dps, dict) else None
    except (ValueError, AttributeError):
        return None


def decode_biz_payload(payload: bytes) -> tuple[int, bytes] | None:
    """Return (channel_id, raw frame bytes) from a biz/.../res message, or None."""
    try:
        msg = json.loads(payload)
        data = msg.get("payload", {})
        if isinstance(data, str):
            data = json.loads(data)
        inner = data.get("data", {})
        channel_id, hex_data = inner.get("channel_id"), inner.get("data")
        if channel_id is None or not hex_data:
            return None
        return int(channel_id), bytes.fromhex(hex_data)
    except (ValueError, AttributeError):
        return None
