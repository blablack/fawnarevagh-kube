"""Upload a song, get it back without the drums. Run: uvicorn drumless_web.app:app"""
from __future__ import annotations

import logging
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from . import worker
from .page import PAGE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

MAX_BYTES = 500 * 1024 * 1024
ID = re.compile(r"^[0-9a-f]{12}$")
w = worker.Worker()


@asynccontextmanager
async def lifespan(_: FastAPI):
    w.start()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def known(track_id: str) -> dict:
    meta = ID.match(track_id) and worker.read_meta(track_id)
    if not meta:
        raise HTTPException(404)
    return meta


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return PAGE


@app.get("/api/tracks")
def tracks() -> dict:
    items = worker.list_tracks()
    queued = [m["id"] for m in reversed(items) if m["status"] == "queued"]
    for m in items:
        m["position"] = queued.index(m["id"]) + 1 if m["id"] in queued else None
    return {"tracks": items, "model": worker.MODEL}


@app.get("/api/log")
def current_log() -> dict:
    """Live log of the track being processed right now (empty when idle)."""
    track_id = w.current
    meta = track_id and worker.read_meta(track_id)
    if not meta:
        return {"id": None, "name": None, "lines": []}
    return {"id": track_id, "name": meta["name"], "lines": worker.tail_log(track_id)}


@app.post("/api/upload")
async def upload(file: UploadFile) -> dict:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in worker.EXTENSIONS:
        raise HTTPException(415, f"unsupported file type {ext or '(none)'}")
    track_id, dest = worker.create_track(file.filename or "track", ext)
    size = 0
    try:
        with dest.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "file too large (max 500 MB)")
                out.write(chunk)
    except BaseException:
        worker.delete_track(track_id)
        raise
    worker.write_meta(track_id, {
        "id": track_id, "name": Path(file.filename).stem, "original": dest.name,
        "size": size, "status": "queued", "created": time.time(), "error": None,
    })
    w.submit(track_id)
    return {"id": track_id}


@app.get("/files/{track_id}/{kind}")
def download(track_id: str, kind: str, dl: bool = False) -> FileResponse:
    meta = known(track_id)
    path = worker.file_for(track_id, kind)
    if not path:
        raise HTTPException(404)
    label = {"original": "", "no_drums": " (no drums)", "drums": " (drums)"}[kind]
    # No filename means inline playback; with one the browser saves it.
    return FileResponse(path, filename=f"{meta['name']}{label}{path.suffix}" if dl else None)


@app.post("/api/tracks/{track_id}/cancel")
def cancel(track_id: str) -> dict:
    meta = known(track_id)
    if meta["status"] not in ("separating", "mixing"):
        raise HTTPException(409, "not processing")
    worker.cancel(track_id)
    return {"ok": True}


@app.delete("/api/tracks/{track_id}")
def delete(track_id: str) -> dict:
    meta = known(track_id)
    if meta["status"] in ("separating", "mixing"):
        raise HTTPException(409, "still processing")
    worker.delete_track(track_id)
    return {"ok": True}
