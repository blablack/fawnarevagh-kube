"""Track storage and the single separation worker.

Every track is a directory under DATA/tracks/<id>/ and the directory is the whole state
(meta.json + audio files), so a pod restart loses nothing: tracks left queued/running are
simply queued again on startup.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

log = logging.getLogger("drumless")

DATA = Path(os.environ.get("DRUMLESS_DATA", "/data"))
TRACKS = DATA / "tracks"
MODELS = DATA / "models"
# BS-RoFormer SW (6 stems: bass, drums, other, vocals, guitar, piano) scores ~14.1 dB drums SDR on
# MVSEP's multisong leaderboard vs ~11.2 for htdemucs_ft, for ~1.7x the CPU time (31 vs 19 min per 4:21 song).
MODEL = os.environ.get("DRUMLESS_MODEL", "BS-Roformer-SW.ckpt")
EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wma", ".aif", ".aiff"}
# Files a finished track serves, as {kind: file name inside the track directory}.
OUTPUTS = {"original": None, "no_drums": "no_drums.flac", "drums": "drums.flac"}


def track_dir(track_id: str) -> Path:
    return TRACKS / track_id


def read_meta(track_id: str) -> dict | None:
    try:
        return json.loads((track_dir(track_id) / "meta.json").read_text())
    except (OSError, ValueError):
        return None


def write_meta(track_id: str, meta: dict) -> None:
    path = track_dir(track_id) / "meta.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta))
    tmp.replace(path)


def list_tracks() -> list[dict]:
    out = []
    if TRACKS.is_dir():
        for d in TRACKS.iterdir():
            meta = read_meta(d.name)
            if meta:
                out.append(meta)
    return sorted(out, key=lambda m: m["created"], reverse=True)


def create_track(name: str, ext: str) -> tuple[str, Path]:
    """Make the directory for a new upload; returns its id and where the original goes."""
    track_id = uuid.uuid4().hex[:12]
    d = track_dir(track_id)
    d.mkdir(parents=True)
    return track_id, d / f"original{ext}"


def file_for(track_id: str, kind: str) -> Path | None:
    d = track_dir(track_id)
    meta = read_meta(track_id)
    if kind not in OUTPUTS or not meta:
        return None
    path = d / (OUTPUTS[kind] or meta["original"])
    return path if path.is_file() else None


def delete_track(track_id: str) -> None:
    shutil.rmtree(track_dir(track_id), ignore_errors=True)


def stem_files(stems: Path) -> dict[str, Path]:
    """Map lowercase stem name -> file. audio-separator writes one file per stem named
    "<input>_(<stem>)_<model>.flac"; Demucs capitalises the stem name, RoFormer models don't, and
    the number of stems depends on the model (4 for htdemucs_ft, 6 for BS-Roformer-SW)."""
    out = {}
    for f in stems.iterdir():
        m = re.search(r"\(([^()]+)\)", f.name)
        if m:
            out[m.group(1).lower()] = f
    return out


def run(cmd: list[str], log_file: Path) -> None:
    with log_file.open("ab") as out:
        out.write(f"\n$ {' '.join(cmd)}\n".encode())
        out.flush()
        subprocess.run(cmd, stdout=out, stderr=subprocess.STDOUT, check=True)


def process(track_id: str) -> None:
    d = track_dir(track_id)
    meta = read_meta(track_id)
    if not meta:
        return  # deleted while queued
    logfile = d / "log.txt"
    stems = d / "stems"
    try:
        meta.update(status="separating", started=time.time(), error=None)
        write_meta(track_id, meta)
        shutil.rmtree(stems, ignore_errors=True)
        MODELS.mkdir(parents=True, exist_ok=True)
        run(["audio-separator", str(d / meta["original"]),
             "-m", MODEL, "--model_file_dir", str(MODELS),
             "--output_dir", str(stems), "--output_format", "FLAC"], logfile)

        meta.update(status="mixing")
        write_meta(track_id, meta)
        files = stem_files(stems)
        if "drums" not in files or len(files) < 2:
            raise RuntimeError(f"model produced no usable stems (got: {sorted(p.name for p in stems.iterdir())})")
        # Every stem that isn't drums, whatever the model calls them, so a 6-stem model's guitar and
        # piano aren't dropped. Sum (not average) them back together; the limiter only catches rare clipping.
        rest = [f for name, f in sorted(files.items()) if name != "drums"]
        run(["ffmpeg", "-y", "-loglevel", "error",
             *[a for f in rest for a in ("-i", str(f))],
             "-filter_complex", f"amix=inputs={len(rest)}:normalize=0:duration=longest,alimiter=limit=0.97",
             "-c:a", "flac", str(d / "no_drums.flac")], logfile)
        shutil.copyfile(files["drums"], d / "drums.flac")
        shutil.rmtree(stems, ignore_errors=True)
        meta.update(status="done", finished=time.time())
    except Exception as e:  # noqa: BLE001 - any failure becomes a visible error on the track
        log.exception("track %s failed", track_id)
        meta.update(status="error", error=f"{type(e).__name__}: {e}", finished=time.time())
    if track_dir(track_id).is_dir():  # not deleted meanwhile
        write_meta(track_id, meta)


class Worker:
    """One thread, one track at a time: the CPU is the bottleneck, not the queue."""

    def __init__(self) -> None:
        self.q: queue.Queue[str] = queue.Queue()
        self.current: str | None = None

    def start(self) -> None:
        TRACKS.mkdir(parents=True, exist_ok=True)
        for meta in reversed(list_tracks()):  # oldest first
            if meta["status"] in ("queued", "separating", "mixing"):
                meta.update(status="queued")
                write_meta(meta["id"], meta)
                self.q.put(meta["id"])
        threading.Thread(target=self.loop, daemon=True).start()

    def submit(self, track_id: str) -> None:
        self.q.put(track_id)

    def loop(self) -> None:
        while True:
            track_id = self.q.get()
            self.current = track_id
            try:
                process(track_id)
            finally:
                self.current = None
