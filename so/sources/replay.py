"""Session recording and deterministic replay.

A session folder holds:
  video.mp4        camera frames
  samples.jsonl    one line per frame: raw rig readings (before faults)
  commands.jsonl   every operator / scenario command with its time
  meta.json        mm_per_step, h0, source kind

Replay re-feeds the exact frames and readings *and* re-applies the commands at the same
moments, so a recorded demo re-runs identically (backup for the live demo) and old sessions can
be re-scored after you change the monitor's parameters.
"""
from __future__ import annotations

import json
import pathlib
import time

import cv2

from .base import Sample, Source


class Recorder:
    def __init__(self, folder: str | pathlib.Path, meta: dict, fps: float = 30.0):
        self.dir = pathlib.Path(folder)
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "meta.json").write_text(json.dumps(meta, indent=2))
        self.samples = open(self.dir / "samples.jsonl", "w")
        self.commands = open(self.dir / "commands.jsonl", "w")
        self.fps, self.writer = fps, None

    def frame(self, s: Sample):
        if self.writer is None:
            h, w = s.frame.shape[:2]
            self.writer = cv2.VideoWriter(str(self.dir / "video.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), self.fps, (w, h))
        self.writer.write(s.frame)
        self.samples.write(json.dumps(s.meta()) + "\n")

    def command(self, t: float, name: str):
        self.commands.write(json.dumps({"t": t, "name": name}) + "\n")
        self.commands.flush()

    def close(self):
        if self.writer is not None:
            self.writer.release()
        self.samples.close()
        self.commands.close()


class ReplaySource(Source):
    kind = "replay"

    def __init__(self, folder: str | pathlib.Path, realtime: bool = True, loop: bool = False):
        self.dir = pathlib.Path(folder)
        meta = json.loads((self.dir / "meta.json").read_text())
        self.mm_per_step, self.h0 = meta["mm_per_step"], meta.get("h0")
        self.rows = [json.loads(l) for l in open(self.dir / "samples.jsonl")]
        cpath = self.dir / "commands.jsonl"
        self.cmds = [json.loads(l) for l in open(cpath)] if cpath.exists() else []
        self.realtime, self.loop = realtime, loop
        self._open()

    def _open(self):
        self.cap = cv2.VideoCapture(str(self.dir / "video.mp4"))
        self.i, self.ci = 0, 0
        self.t_wall0 = time.monotonic()

    def due_commands(self, t: float) -> list[str]:
        """Commands recorded up to time t (the pipeline re-applies them)."""
        out = []
        while self.ci < len(self.cmds) and self.cmds[self.ci]["t"] <= t:
            out.append(self.cmds[self.ci]["name"])
            self.ci += 1
        return out

    def read(self) -> Sample | None:
        if self.i >= len(self.rows):
            if not self.loop:
                return None
            self.cap.release()
            self._open()
        ok, frame = self.cap.read()
        if not ok:
            return None
        r = self.rows[self.i]
        self.i += 1
        if self.realtime:
            target = self.t_wall0 + (r["t"] - self.rows[0]["t"])
            time.sleep(max(0.0, target - time.monotonic()))
        self.h0 = r.get("h0", self.h0)
        return Sample(r["t"], frame, r["rf_raw"], r["steps"], r.get("true_alt"), r["descending"], self.h0)
