"""Protobuf <-> DPS value encoding, plus decoders for the DPS keys we care about.

DPS numbers and wire format come from eufy-clean (const.py DPS_MAP, utils.py).
"""
from __future__ import annotations

from base64 import b64decode, b64encode
from typing import Any, TypeVar

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import DecodeError, Message

from .proto.cloud.app_device_info_pb2 import AppInfo, DeviceInfo
from .proto.cloud.clean_param_pb2 import CleanParamRequest, CleanParamResponse
from .proto.cloud.control_pb2 import ModeCtrlRequest
from .proto.cloud.keepalive_pb2 import KeepAliveRequest
from .proto.cloud.language_pb2 import LanguageRequest, LanguageResponse
from .proto.cloud.map_edit_pb2 import MapEditRequest, MapEditResponse
from .proto.cloud.multi_maps_pb2 import MultiMapsManageRequest, MultiMapsManageResponse
from .proto.cloud.scene_pb2 import SceneRequest, SceneResponse
from .proto.cloud.station_pb2 import StationRequest, StationResponse
from .proto.cloud.stream_pb2 import RoomParams
from .proto.cloud.timing_pb2 import TimerRequest, TimerResponse
from .proto.cloud.undisturbed_pb2 import UndisturbedRequest, UndisturbedResponse
from .proto.cloud.universal_data_pb2 import UniversalDataResponse
from .proto.cloud.unisetting_pb2 import UnisettingRequest, UnisettingResponse
from .proto.cloud.work_status_pb2 import WorkStatus

DPS_MODE_CTRL = "152"
DPS_WORK_STATUS = "153"
DPS_KEEPALIVE = "153"  # the same key carries the app's KeepAliveRequest
DPS_CLEAN_PARAM = "154"
DPS_UNDISTURBED = "157"
DPS_VOICE = "162"
# On the X10 (T2351) 164 carries the schedule list (TimerResponse) and the
# MapEditResponse ack comes back on 170, the key of the request. eufy-clean
# reads 164 as the MapEditResponse, which may hold for other models.
DPS_TIMER = "164"
DPS_MAP_DATA = "165"
DPS_DEVICE_INFO = "169"  # DeviceInfo from the robot, AppInfo from the app
DPS_APP_INFO = "169"
DPS_MAP_EDIT_REQUEST = "170"
DPS_MAP_EDIT_RESPONSE = "170"
DPS_MULTI_MAP_MANAGE = "172"
DPS_STATION = "173"
DPS_UNISETTING = "176"
DPS_SCENE = "180"

M = TypeVar("M", bound=Message)


def encode_varint(n: int) -> bytes:
    out = bytearray()
    while n >= 0x80:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


def strip_varint_prefix(data: bytes) -> bytes:
    """Drop the length-delimiting varint that prefixes every frame."""
    pos = 0
    while pos < len(data) and data[pos] & 0x80:
        pos += 1
    if pos >= len(data):
        raise ValueError("truncated varint prefix")
    return data[pos + 1:]


def encode_dps(msg: Message) -> str:
    """Serialize a request the way the robot expects: varint length + base64."""
    body = msg.SerializeToString()
    return b64encode(encode_varint(len(body)) + body).decode()


def decode_dps(msg_type: type[M], value: str) -> M:
    return msg_type.FromString(strip_varint_prefix(b64decode(value)))


def to_dict(msg: Message) -> dict[str, Any]:
    return MessageToDict(msg, preserving_proto_field_name=True)


def lz4_block_decompress(data: bytes, uncompressed_size: int) -> bytes:
    """Decompress a raw LZ4 block (no frame header). From eufy-clean map_stream.py."""
    out = bytearray()
    pos, n = 0, len(data)
    while pos < n:
        token = data[pos]
        pos += 1
        lit_len = token >> 4
        if lit_len == 15:
            while pos < n:
                extra = data[pos]
                pos += 1
                lit_len += extra
                if extra != 255:
                    break
        out += data[pos:pos + lit_len]
        pos += lit_len
        if pos >= n:
            break
        offset = data[pos] | (data[pos + 1] << 8)
        pos += 2
        match_len = (token & 0xF) + 4
        if (token & 0xF) == 15:
            while pos < n:
                extra = data[pos]
                pos += 1
                match_len += extra
                if extra != 255:
                    break
        start = len(out) - offset
        for i in range(match_len):
            out.append(out[start + i])
    if len(out) != uncompressed_size:
        raise ValueError(f"LZ4: got {len(out)} bytes, expected {uncompressed_size}")
    return bytes(out)


def _map_data(value: str) -> dict[str, Any]:
    # DPS 165 is either UniversalDataResponse (room table) or RoomParams.
    universal = decode_dps(UniversalDataResponse, value)
    if universal.cur_map_room.map_id or universal.cur_map_room.data:
        return {"type": "UniversalDataResponse", **to_dict(universal)}
    return {"type": "RoomParams", **to_dict(decode_dps(RoomParams, value))}


def _timer_or_map_edit(value: str) -> dict[str, Any]:
    timers = decode_dps(TimerResponse, value)
    if timers.timers:
        return {"type": "TimerResponse", **to_dict(timers)}
    return {"type": "MapEditResponse", **to_dict(decode_dps(MapEditResponse, value))}


_DECODERS = {
    DPS_WORK_STATUS: lambda v: to_dict(decode_dps(WorkStatus, v)),
    DPS_CLEAN_PARAM: lambda v: to_dict(decode_dps(CleanParamResponse, v)),
    DPS_UNDISTURBED: lambda v: to_dict(decode_dps(UndisturbedResponse, v)),
    DPS_VOICE: lambda v: to_dict(decode_dps(LanguageResponse, v)),
    DPS_TIMER: _timer_or_map_edit,
    DPS_STATION: lambda v: to_dict(decode_dps(StationResponse, v)),
    DPS_SCENE: lambda v: to_dict(decode_dps(SceneResponse, v)),
    DPS_MAP_DATA: _map_data,
    DPS_DEVICE_INFO: lambda v: to_dict(decode_dps(DeviceInfo, v)),
    DPS_MAP_EDIT_RESPONSE: lambda v: to_dict(decode_dps(MapEditResponse, v)),
    DPS_MULTI_MAP_MANAGE: lambda v: to_dict(decode_dps(MultiMapsManageResponse, v)),
    DPS_UNISETTING: lambda v: to_dict(decode_dps(UnisettingResponse, v)),
}


def describe_dps(key: str, value: Any) -> Any:
    """Decode a DPS value we know about; return other values unchanged."""
    decoder = _DECODERS.get(key)
    if decoder is None or not isinstance(value, str):
        return value
    try:
        return decoder(value)
    except (DecodeError, ValueError) as exc:
        return {"undecodable": value, "error": str(exc)}


# Requests the app (or we) send, by DPS key; everything is logged raw as well.
_REQUESTS: dict[str, type[Message]] = {
    DPS_MODE_CTRL: ModeCtrlRequest,
    DPS_KEEPALIVE: KeepAliveRequest,  # every minute while the app is open
    DPS_APP_INFO: AppInfo,  # sent once each time the app opens the map screen
    DPS_CLEAN_PARAM: CleanParamRequest,
    DPS_UNDISTURBED: UndisturbedRequest,
    DPS_VOICE: LanguageRequest,
    DPS_TIMER: TimerRequest,
    DPS_MAP_EDIT_REQUEST: MapEditRequest,
    DPS_MULTI_MAP_MANAGE: MultiMapsManageRequest,
    DPS_STATION: StationRequest,
    DPS_UNISETTING: UnisettingRequest,
    DPS_SCENE: SceneRequest,
}


def describe_request(key: str, value: Any) -> Any:
    """Decode a DPS write sent to the robot, if we know its request type."""
    msg_type = _REQUESTS.get(key)
    if msg_type is None or not isinstance(value, str):
        return value
    try:
        return {"type": msg_type.__name__, **to_dict(decode_dps(msg_type, value))}
    except (DecodeError, ValueError) as exc:
        return {"undecodable": value, "error": str(exc)}


def current_map_id(dps: dict[str, Any]) -> int | None:
    """The active map id, from DPS 165 (MAP_DATA), if present."""
    value = dps.get(DPS_MAP_DATA)
    if not isinstance(value, str):
        return None
    try:
        universal = decode_dps(UniversalDataResponse, value)
        if universal.cur_map_room.map_id:
            return universal.cur_map_room.map_id
        return decode_dps(RoomParams, value).map_id or None
    except (DecodeError, ValueError):
        return None
