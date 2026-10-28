"""Eufy cloud HTTP API: login, MQTT credentials and device discovery.

Adapted from eufy-clean's api/http.py and api/cloud.py (synchronous rewrite,
Tuya-cloud fallback dropped: only MQTT devices can stream or edit maps).
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

import requests

_LOGGER = logging.getLogger(__name__)

API_BASE = "https://api.eufylife.com"
HOME_API_BASE = "https://home-api.eufylife.com"
AIOT_API_BASE = "https://aiot-clean-api-pr.eufylife.com"

URL_USER_INFO = f"{API_BASE}/v1/user/user_center_info"
URL_DEVICE_V2 = f"{API_BASE}/v1/device/v2"
URL_AIOT_DEVICES = f"{AIOT_API_BASE}/app/devicerelation/get_device_list"
URL_MQTT_INFO = f"{AIOT_API_BASE}/app/devicemanage/get_user_mqtt_info"

USER_AGENT = "EufyHome-Android-3.1.3-753"
TIMEOUT = 30

# Tried in order: the unified "Eufy" app (v2) first, then the legacy "Eufy Clean"
# app (v1). Accounts migrated to the unified app only get a user_center id from v2.
LOGIN_CONFIGS: list[dict[str, str]] = [
    {
        "label": "v2 (Eufy app)",
        "url": f"{HOME_API_BASE}/v1/user/v2/email/login",
        "client_id": "eufy-app",
        "client_secret": "8FHf22gaTKu7MZXqz5zytw",
        "category": "Health",
    },
    {
        "label": "v1 (Eufy Clean app)",
        "url": f"{HOME_API_BASE}/v1/user/email/login",
        "client_id": "eufyhome-app",
        "client_secret": "GQCpr9dSp3uQpsOMgJ4xQ",
        "category": "Home",
    },
]


class EufyLoginError(Exception):
    """Login or discovery failed."""


@dataclass
class Device:
    sn: str
    model: str
    name: str
    dps: dict[str, Any] = field(default_factory=dict)
    firmware: str = ""


@dataclass
class Account:
    openudid: str
    session: dict[str, Any]
    user_info: dict[str, Any]
    mqtt: dict[str, Any]
    devices: list[Device]


def _attempt_login(http: requests.Session, cfg: dict[str, str], username: str,
                   password: str, openudid: str) -> dict[str, Any] | None:
    resp = http.post(
        cfg["url"],
        timeout=TIMEOUT,
        headers={
            "category": cfg["category"],
            "Accept": "*/*",
            "openudid": openudid,
            "Content-Type": "application/json",
            "clientType": "1",
            "User-Agent": USER_AGENT,
        },
        json={
            "email": username,
            "password": password,
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
        },
    )
    if resp.status_code == 429:
        # Don't fall through to the next login flavour: its token can yield MQTT
        # credentials that the broker then refuses for this robot.
        raise EufyLoginError(f"{cfg['label']} login is rate-limited (HTTP 429); "
                             "wait a few minutes and retry")
    try:
        body = resp.json()
    except ValueError:
        body = None
    if resp.status_code == 200 and body and body.get("access_token"):
        return body
    _LOGGER.debug("Login via %s failed: HTTP %s %s", cfg["label"], resp.status_code,
                  (body or {}).get("message") if isinstance(body, dict) else body)
    return None


def _get_user_info(http: requests.Session, session: dict[str, Any],
                   openudid: str) -> dict[str, Any] | None:
    resp = http.get(
        URL_USER_INFO,
        timeout=TIMEOUT,
        headers={
            "user-agent": USER_AGENT,
            "category": "Home",
            "token": session["access_token"],
            "openudid": openudid,
            "clienttype": "2",
        },
    )
    if resp.status_code != 200:
        return None
    info = resp.json()
    if not info or not info.get("user_center_id"):
        return None
    info["gtoken"] = hashlib.md5(info["user_center_id"].encode()).hexdigest()
    return info


def _aiot_headers(user_info: dict[str, Any], openudid: str) -> dict[str, str]:
    return {
        "user-agent": USER_AGENT,
        "openudid": openudid,
        "os-version": "Android",
        "model-type": "PHONE",
        "app-name": "eufy_home",
        "x-auth-token": user_info["user_center_token"],
        "gtoken": user_info["gtoken"],
        "content-type": "application/json; charset=UTF-8",
    }


def _get_devices(http: requests.Session, session: dict[str, Any],
                 user_info: dict[str, Any], openudid: str) -> list[Device]:
    # Names and model codes come from the cloud device list...
    meta: dict[str, dict[str, Any]] = {}
    resp = http.get(
        URL_DEVICE_V2,
        timeout=TIMEOUT,
        headers={
            "user-agent": USER_AGENT,
            "category": "Home",
            "token": session["access_token"],
            "openudid": openudid,
            "clienttype": "2",
        },
    )
    if resp.status_code == 200:
        for d in resp.json().get("devices", []) or []:
            if d.get("id"):
                meta[d["id"]] = d

    # ...the MQTT-capable devices and their current DPS from the AIOT list.
    resp = http.post(URL_AIOT_DEVICES, timeout=TIMEOUT,
                     headers=_aiot_headers(user_info, openudid), json={"attribute": 3})
    aiot: list[dict[str, Any]] = []
    if resp.status_code == 200:
        for entry in (resp.json().get("data") or {}).get("devices") or []:
            if "device" in entry:
                aiot.append(entry["device"])
    if not aiot:
        # Unified-app accounts sometimes return an empty AIOT list; fall back to
        # the cloud list (no initial DPS then).
        aiot = [{"device_sn": sn} for sn in meta]

    devices = []
    for d in aiot:
        sn = d.get("device_sn")
        if not sn:
            continue
        m = meta.get(sn, {})
        model = (m.get("product", {}).get("product_code") or m.get("device_model")
                 or d.get("device_model") or "")
        # The MQTT topic needs the bare model code ("T2351"); 6-char codes such
        # as "T2080A" are real models, anything longer carries a suffix.
        devices.append(Device(
            sn=sn,
            model=model if len(model) <= 6 else model[:5],
            name=m.get("alias_name") or m.get("device_name") or d.get("device_name") or sn,
            dps=d.get("dps") or {},
            firmware=d.get("main_sw_version") or d.get("soft_version") or "",
        ))
    return devices


def _finish(http: requests.Session, session: dict[str, Any], user_info: dict[str, Any],
            openudid: str) -> Account:
    resp = http.post(URL_MQTT_INFO, timeout=TIMEOUT, headers=_aiot_headers(user_info, openudid))
    mqtt = resp.json().get("data") if resp.status_code == 200 else None
    if not mqtt:
        raise EufyLoginError(f"Could not get MQTT credentials (HTTP {resp.status_code})")
    devices = _get_devices(http, session, user_info, openudid)
    return Account(openudid, session, user_info, mqtt, devices)


def login(username: str, password: str, openudid: str,
          cached_session: dict[str, Any] | None = None) -> Account:
    """Return MQTT credentials plus the account's devices.

    A *cached_session* ({"access_token": ...}) from an earlier run is tried
    first: the login endpoints rate-limit after a handful of calls.
    """
    http = requests.Session()
    if cached_session and cached_session.get("access_token"):
        user_info = _get_user_info(http, cached_session, openudid)
        if user_info:
            _LOGGER.info("Reusing cached Eufy session")
            return _finish(http, cached_session, user_info, openudid)
        _LOGGER.info("Cached Eufy session expired, logging in again")
    for cfg in LOGIN_CONFIGS:
        session = _attempt_login(http, cfg, username, password, openudid)
        if not session:
            continue
        user_info = _get_user_info(http, session, openudid)
        if not user_info:
            _LOGGER.debug("Login via %s gave no user_center id, trying next", cfg["label"])
            continue
        _LOGGER.info("Logged in via %s", cfg["label"])
        return _finish(http, {"access_token": session["access_token"]}, user_info, openudid)
    raise EufyLoginError("Login failed (wrong credentials, or the account has no MQTT access)")
