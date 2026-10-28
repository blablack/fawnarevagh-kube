"""Backup and restore run the CLI (eufy_map.py) as a subprocess; its output is the log."""
from __future__ import annotations

import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import eufy_map

CLI = Path(eufy_map.__file__).resolve()
LOGS = eufy_map.DATA / "jobs"


@dataclass
class Job:
    id: str
    title: str
    args: list[str]
    started: float = field(default_factory=time.time)
    proc: subprocess.Popen | None = None

    @property
    def log_path(self) -> Path:
        return LOGS / f"{self.id}.log"

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    @property
    def returncode(self) -> int | None:
        return None if self.proc is None else self.proc.poll()

    def output(self) -> str:
        try:
            return self.log_path.read_text(errors="replace")
        except OSError:
            return ""


class Jobs:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}

    def running(self) -> bool:
        return any(j.running for j in self.jobs.values())

    def start(self, title: str, args: list[str]) -> Job:
        if self.running():
            raise RuntimeError("another job is still running")
        LOGS.mkdir(parents=True, exist_ok=True)
        job = Job(uuid.uuid4().hex[:8], title, args)
        with job.log_path.open("w") as out:
            job.proc = subprocess.Popen([sys.executable, "-u", str(CLI), *args], stdout=out,
                                        stderr=subprocess.STDOUT, cwd=CLI.parent)
        self.jobs[job.id] = job
        for old in sorted(self.jobs.values(), key=lambda j: j.started)[:-20]:
            if not old.running:
                del self.jobs[old.id]
        return job
