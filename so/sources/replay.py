"""Recording a session and playing it back.

A session folder holds:
  video.mp4       the camera frames
  samples.jsonl   one line per frame with the raw readings, before any fault is injected
  commands.jsonl  every command with the time it was given
  meta.json       mm_per_step, h0 and the kind of source

Playback feeds the same frames and readings back and re-sends the commands at the same
moments, so a recorded demo runs identically. That makes it a backup for the live demo, and
it lets you re-score an old session after changing the monitor's settings.
"""
import json
import pathlib
import time

import cv2

from .base import Sample, Source


class Recorder:
    def __init__(self, folder, meta: dict, fps: float = 30.0):
        self.dir = pathlib.Path(folder)
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "meta.json").write_text(json.dumps(meta, indent=2))
        self.samples = open(self.dir / "samples.jsonl", "w")
        self.commands = open(self.dir / "commands.jsonl", "w")
        self.fps, self.writer = fps, None

    def frame(self, s: Sample):
        if self.writer is None:                    # we only learn the frame size from the first frame
            h, w = s.frame.shape[:2]
            self.writer = cv2.VideoWriter(str(self.dir / "video.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), self.fps, (w, h))
        self.writer.write(s.frame)
        self.samples.write(json.dumps(s.meta()) + "\n")

    def command(self, t: float, name: str):
        self.commands.write(json.dumps({"t": t, "name": name}) + "\n")
        self.commands.flush()

    def close(self):
        if self.writer:
            self.writer.release()
        self.samples.close()
        self.commands.close()


class ReplaySource(Source):
    kind = "replay"

    def __init__(self, folder, realtime: bool = True, loop: bool = False):
        self.dir = pathlib.Path(folder)
        meta = json.loads((self.dir / "meta.json").read_text())
        self.mm_per_step, self.h0 = meta["mm_per_step"], meta.get("h0")
        self.rows = [json.loads(line) for line in open(self.dir / "samples.jsonl")]
        cmds = self.dir / "commands.jsonl"
        self.cmds = [json.loads(line) for line in open(cmds)] if cmds.exists() else []
        self.realtime, self.loop = realtime, loop
        self.open()

    def open(self):
        self.cap = cv2.VideoCapture(str(self.dir / "video.mp4"))
        self.i = self.ci = 0                       # next sample, next command
        self.wall0 = time.monotonic()

    def due_commands(self, t: float) -> list[str]:
        """Commands recorded up to time t. The pipeline re-applies them."""
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
            self.open()
        ok, frame = self.cap.read()
        if not ok:
            return None
        r = self.rows[self.i]
        self.i += 1
        if self.realtime:                          # play at the speed it was recorded
            time.sleep(max(0.0, self.wall0 + r["t"] - self.rows[0]["t"] - time.monotonic()))
        self.h0 = r.get("h0", self.h0)
        return Sample(r["t"], frame, r["rf_raw"], r["steps"], r.get("true_alt"), r["descending"], self.h0)
