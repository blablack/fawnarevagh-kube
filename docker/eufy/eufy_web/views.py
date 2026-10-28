"""HTML for the status page. Plain strings, no template engine."""
from __future__ import annotations

import time
from html import escape
from typing import Any

CSS = """
:root{color-scheme:light dark;--bg:#fafaf8;--fg:#1d1d1b;--mut:#6b6b66;--card:#fff;--line:#e3e3dd;
--acc:#2a6f6b;--warn:#b4531a;--ok:#2f7d3b}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--fg:#ececE8;--mut:#9a9a93;--card:#1f1f1c;
--line:#33332f;--acc:#6fbdb7;--warn:#e08a55;--ok:#6fbf7b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:16px}
header{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;justify-content:space-between}
h1{font-size:22px;margin:8px 0}h2{font-size:16px;margin:0 0 8px}
nav a{margin-right:14px;color:var(--acc)}a{color:var(--acc)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;
margin:12px 0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:720px){.grid{grid-template-columns:1fr}}
.pill{display:inline-block;padding:1px 9px;border-radius:99px;border:1px solid var(--line);
font-size:13px}.ok{color:var(--ok)}.bad{color:var(--warn)}.mut{color:var(--mut)}
img.map{max-width:100%;border-radius:6px;background:#fff}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:500}
button,input[type=text],select{font:inherit;padding:5px 11px;border-radius:7px;
border:1px solid var(--line);background:var(--card);color:var(--fg)}
button{cursor:pointer}button.go{background:var(--acc);color:var(--bg);border-color:var(--acc)}
button.danger{border-color:var(--warn);color:var(--warn)}
form.inline{display:inline}pre{background:var(--card);border:1px solid var(--line);
border-radius:8px;padding:12px;overflow:auto;white-space:pre-wrap;font-size:13px}
label{margin-right:12px}
"""


def page(title: str, body: str, refresh: int | None = None) -> str:
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">{meta}'
            f'<title>{escape(title)}</title><style>{CSS}</style></head><body><main>'
            f'<header><h1>{escape(title)}</h1><nav><a href="/">Status</a>'
            f'<a href="/backups">Backups</a></nav></header>{body}</main></body></html>')


def when(t: float | None) -> str:
    return "never" if not t else time.strftime("%a %d %b %H:%M", time.localtime(t))


def ago(t: float | None) -> str:
    if not t:
        return "never"
    s = int(time.time() - t)
    if s < 90:
        return f"{s}s ago"
    if s < 5400:
        return f"{s // 60} min ago"
    return f"{s // 3600} h ago" if s < 172800 else f"{s // 86400} days ago"


def pct(x: float | None) -> str:
    return "" if x is None else f"{x:.1%}"


def overlaps(d: dict[str, float] | None) -> str:
    if not d:
        return '<span class="mut">–</span>'
    return f"floor {pct(d['floor'])}, walls {pct(d['walls'])}"


def status_card(s: dict[str, Any], settings: Any, latest: dict[str, Any] | None) -> str:
    link = ('<span class="pill ok">connected</span>' if s["connected"]
            else '<span class="pill bad">offline</span>')
    err = f'<p class="bad">{escape(str(s["error"]))}</p>' if s["error"] and not s["connected"] else ""
    battery = f'{s["battery"]}%' if s["battery"] is not None else "?"
    wait = (f'<p class="mut">Docked: acting in {s["waiting"]} s unless it moves again.</p>'
            if s["waiting"] is not None else "")
    img = ('<img class="map" src="/map/latest.png" alt="current map">'
           f'<p class="mut">Map {latest["map_id"]}, taken {ago(latest["t"])} ({escape(latest["label"])})</p>'
           if latest else '<p class="mut">No map yet.</p>')
    return f"""<div class="grid"><div class="card"><h2>Robot</h2>
<p>{link} state <b>{escape(str(s["state"] or "?"))}</b>, battery {battery},
current map <b>{s["map_id"] or "?"}</b></p>{err}{wait}
<form method="post" action="/snapshot" class="inline"><button>Refresh map</button></form></div>
<div class="card">{img}</div></div>"""


def auto_card(settings: Any, reference_ok: bool) -> str:
    mode = settings["mode"]
    options = "".join(
        f'<label><input type="radio" name="mode" value="{m}"{" checked" if m == mode else ""}> {m}</label>'
        for m in ("off", "observe", "recover"))
    ref = settings["reference"]
    ref_line = (f'<code>{escape(ref)}</code>' + ("" if reference_ok else ' <span class="bad">(missing)</span>')
                if ref else '<span class="bad">none set</span>')
    return f"""<div class="card"><h2>After each clean</h2>
<form method="post" action="/mode">{options} <button class="go">Save</button></form>
<p class="mut"><b>off</b>: nothing. <b>observe</b>: snapshot and compare with the reference map.
<b>recover</b>: also send recover, snapshot again and compare.
Waits {settings["delay"]} s after the robot docks; never acts while it is busy or mapping.</p>
<p>Reference map: {ref_line}</p>
<form method="post" action="/reference/current" class="inline"
 onsubmit="return confirm('Use the robot\\'s current map as the reference? Only do this while the map is healthy.')">
<button>Use the current map as reference</button></form>
<form method="post" action="/recover" class="inline"
 onsubmit="return confirm('Send recover now? The robot goes back to its last saved map.')">
<button class="danger">Recover now</button></form></div>"""


def history_card(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<div class="card"><h2>History</h2><p class="mut">Nothing yet.</p></div>'
    body = ""
    for r in rows:
        extra = ""
        if r.get("recover"):
            extra = f'recover: {escape(str(r["recover"]))}'
        if r.get("note"):
            extra = (extra + "; " if extra else "") + escape(r["note"])
        before = f'<a href="/history/{escape(r["dir"])}/map.png">{overlaps(r.get("before"))}</a>' \
            if r.get("dir") and r.get("before") else overlaps(r.get("before"))
        after = (f'<a href="/history/{escape(r["after_dir"])}/map.png">{overlaps(r.get("after"))}</a>'
                 if r.get("after_dir") and r.get("after") else overlaps(r.get("after")))
        body += (f'<tr><td>{when(r["t"])}</td><td>{escape(r["kind"])} ({escape(r["mode"])})</td>'
                 f'<td>{r.get("map_id", "")}</td><td>{before}</td><td>{after}</td>'
                 f'<td class="mut">{extra}</td></tr>')
    return ('<div class="card"><h2>History</h2><p class="mut">Overlap with the reference map '
            '(100% = identical). "After" is only filled when recover ran.</p>'
            '<table><tr><th>When</th><th>Event</th><th>Map</th><th>Before recover</th>'
            f'<th>After recover</th><th></th></tr>{body}</table></div>')


def backups_page(items: list[dict[str, Any]], reference: str | None, busy: bool) -> str:
    rows = ""
    for b in items:
        n = escape(b["name"])
        img = f'<a href="/backups/{n}/map.png">map</a>' if b["has_map"] else '<span class="mut">no map</span>'
        marker = ' <span class="pill ok">reference</span>' if b["name"] == reference else ""
        full = "" if not b["full"] else ' <span class="pill">full backup</span>'
        buttons = f"""<form method="post" action="/reference/{n}" class="inline"><button>Set as reference</button></form>"""
        if b["full"]:
            buttons += f"""<form method="post" action="/jobs/restore-plan/{n}" class="inline"><button>Restore…</button></form>"""
        rows += (f'<tr><td><code>{n}</code>{marker}{full}</td><td>{img}</td>'
                 f'<td><a href="/backups/{n}.zip">download</a></td><td>{buttons}</td></tr>')
    note = '<p class="bad">A job is running.</p>' if busy else ""
    return f"""{note}<div class="card"><h2>Back up now</h2>
<form method="post" action="/jobs/backup">
<input type="text" name="label" value="manual" pattern="[\\w\\-]{{1,40}}" size="16">
<label><input type="checkbox" name="wait" value="1"> wait for a scene Save in the app (up to 5 min), so scene contents are included</label>
<button class="go">Back up</button></form></div>
<div class="card"><h2>Backups and snapshots</h2><table><tr><th>Name</th><th></th><th></th><th></th></tr>{rows}</table></div>"""


def job_page(job: Any, backup: str | None) -> str:
    state = ("running…" if job.running else
             ("done" if job.returncode == 0 else f"failed (exit {job.returncode})"))
    follow = ""
    if not job.running and job.returncode == 0 and job.title == "restore plan" and backup:
        follow = f"""<div class="card"><p>This was a dry run: nothing was sent.</p>
<form method="post" action="/jobs/restore/{escape(backup)}"
 onsubmit="return confirm('Send this to the robot?')">
<label>only (optional): <input type="text" name="only" placeholder="rooms,names,custom,zones,scenes,schedules" size="40"></label>
<label><input type="checkbox" name="force" value="1"> force (maps overlap under 60%)</label>
<button class="danger">Apply restore</button></form></div>"""
    return (f'<div class="card"><h2>{escape(job.title)}: {state}</h2>'
            f'<pre>{escape(job.output()) or "…"}</pre></div>{follow}')
