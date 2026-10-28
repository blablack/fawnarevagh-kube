"""Status page and actions for the Eufy robot. Run: uvicorn eufy_web.app:app"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

import eufy_map
from eufy_fix.restore import PARTS

from . import views
from .jobs import Jobs
from .monitor import MODES, Monitor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

NAME = re.compile(r"^[\w.\-]+$")
monitor = Monitor()
jobs = Jobs()
monitor.job_running = jobs.running


def write_config() -> None:
    """Create config.json from the environment (the Secret) when it is set."""
    user, password = os.environ.get("EUFY_USERNAME"), os.environ.get("EUFY_PASSWORD")
    if user and password:
        eufy_map.DATA.mkdir(parents=True, exist_ok=True)
        config = {"username": user, "password": password}
        if os.environ.get("EUFY_DEVICE_SN"):
            config["device_sn"] = os.environ["EUFY_DEVICE_SN"]
        path = eufy_map.DATA / "config.json"
        path.touch(mode=0o600)
        path.write_text(json.dumps(config))


@asynccontextmanager
async def lifespan(_: FastAPI):
    write_config()
    monitor.start()
    yield
    monitor.halt.set()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def backup_dir(name: str) -> Path:
    path = eufy_map.BACKUPS / name
    if not NAME.match(name) or not path.is_dir():
        raise HTTPException(404)
    return path


def back(to: str = "/") -> RedirectResponse:
    return RedirectResponse(to, status_code=303)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "connected": monitor.status["connected"]}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    try:
        latest = json.loads((monitor.latest_dir / "latest.json").read_text())
    except (OSError, ValueError):
        latest = None
    body = (views.status_card(monitor.status, monitor.settings, latest)
            + views.auto_card(monitor.settings)
            + views.history_card(monitor.history()))
    return views.page("Moppy", body, refresh=30)


@app.get("/map/latest.png")
def latest_map() -> FileResponse:
    path = monitor.latest_dir / "map.png"
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, headers={"Cache-Control": "no-cache"})


@app.get("/history/{name}/map.png")
def history_map(name: str) -> FileResponse:
    path = monitor.history_dir / name / "map.png"
    if not NAME.match(name) or not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


@app.post("/mode")
def set_mode(mode: str = Form(...)) -> RedirectResponse:
    if mode not in MODES:
        raise HTTPException(400, "unknown mode")
    monitor.settings.update(mode=mode)
    return back()


def run_on_robot(fn):
    if jobs.running():
        raise HTTPException(409, "a backup or restore is running")
    try:
        return monitor.call(fn)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"{type(e).__name__}: {e}") from e


@app.post("/snapshot")
def snapshot() -> RedirectResponse:
    run_on_robot(lambda robot: monitor.cycle(robot, "manual", False))
    return back()


@app.post("/recover")
def recover() -> RedirectResponse:
    run_on_robot(lambda robot: monitor.cycle(robot, "manual", True))
    return back()


@app.get("/backups", response_class=HTMLResponse)
def backups() -> str:
    items = []
    if eufy_map.BACKUPS.is_dir():
        for d in sorted((p for p in eufy_map.BACKUPS.iterdir() if p.is_dir()), reverse=True):
            m = eufy_map.map_dir(str(d))
            items.append({"name": d.name, "has_map": (m / "map.png").exists(),
                          "full": (d / "state.json").exists()})
    return views.page("Backups", views.backups_page(items, jobs.running()))


@app.get("/backups/{name}/map.png")
def backup_map(name: str) -> FileResponse:
    path = eufy_map.map_dir(str(backup_dir(name))) / "map.png"
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


@app.get("/backups/{name}.zip")
def backup_zip(name: str) -> Response:
    root = backup_dir(name)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(root.rglob("*")):
            if f.is_file() and "capture" not in f.relative_to(root).parts:
                z.write(f, Path(name) / f.relative_to(root))
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}.zip"'})


def start_job(title: str, args: list[str], backup: str = "") -> RedirectResponse:
    try:
        job = jobs.start(title, args)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e
    return back(f"/jobs/{job.id}?backup={backup}")


@app.post("/jobs/backup")
def job_backup(label: str = Form("manual"), wait: str = Form("")) -> RedirectResponse:
    if not re.match(r"^[\w\-]{1,40}$", label):
        raise HTTPException(400, "label: letters, digits, - and _ only")
    return start_job("backup", ["backup", "--label", label, "--scene-wait", "300" if wait else "0"])


@app.post("/jobs/restore-plan/{name}")
def job_restore_plan(name: str) -> RedirectResponse:
    backup_dir(name)
    return start_job("restore plan", ["restore", str(eufy_map.BACKUPS / name)], name)


@app.post("/jobs/restore/{name}")
def job_restore(name: str, only: str = Form(""), force: str = Form("")) -> RedirectResponse:
    backup_dir(name)
    args = ["restore", str(eufy_map.BACKUPS / name), "--yes"]
    if only.strip():
        parts = [p.strip() for p in only.split(",") if p.strip()]
        if not set(parts) <= set(PARTS):
            raise HTTPException(400, f"only: any of {', '.join(PARTS)}")
        args += ["--only", ",".join(parts)]
    if force:
        args.append("--force")
    return start_job("restore", args, name)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job(job_id: str, backup: str = "") -> str:
    j = jobs.jobs.get(job_id)
    if j is None:
        raise HTTPException(404)
    name = backup if NAME.match(backup) else None
    return views.page(f"Job {j.title}", views.job_page(j, name)
                      + '<p><a href="/backups">Back to backups</a></p>',
                      refresh=3 if j.running else None)
