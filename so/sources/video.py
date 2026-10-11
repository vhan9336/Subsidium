"""Real landing footage as the camera.

The frames are real, so the camera's time-to-contact is measured from real images. What the
footage cannot give is a rangefinder or an inertial unit, so those two witnesses are generated
from the clip's altitude record (clips.toml -> `truth`), at rig scale (`mm_per_m`), with the same
noise as the simulator. A clip without an altitude record is "tracking only": the camera runs,
nothing is voted on.

Clip time is in seconds of video. The time base (`t`) keeps running while paused so scenario
scripts still fire; it only goes back to zero when the clip loops, which the pipeline treats as
a clean restart.
"""
from __future__ import annotations

import csv
import time
import tomllib

import cv2
import numpy as np

from ..config import ROOT
from .base import Sample, Source

HOLD_S = 3.0          # pause on the last frame before looping
MAX_WIDTH = 1024      # frames wider than this are scaled down for the stream


def load_clips(path=None) -> dict[str, dict]:
    """Clips from clips.toml whose video file is actually on disk."""
    with open(path or ROOT / "clips.toml", "rb") as f:
        raw = tomllib.load(f)
    return {k: {**v, "id": k} for k, v in raw.items() if (ROOT / v["file"]).exists()}


class Truth:
    """Altitude record (t, alt_m) -> smooth altitude in rig mm. Callouts are coarse (whole metres),
    so a cubic is fitted through them rather than stepping from one to the next."""

    def __init__(self, path, mm_per_m: float):
        rows = list(csv.DictReader(open(ROOT / path)))
        self.t = np.array([float(r["t"]) for r in rows])
        self.poly = np.polyfit(self.t, np.array([float(r["alt_m"]) for r in rows]) * mm_per_m, 3)

    def alt(self, t: float) -> float:
        return float(max(np.polyval(self.poly, min(max(t, self.t[0]), self.t[-1])), 1.0))


class VideoSource(Source):
    kind = "video"

    def __init__(self, mm_per_step: float, clip: str | None = None, realtime: bool = True, seed: int = 0):
        self.mm_per_step, self.realtime = mm_per_step, realtime
        self.clips = load_clips()
        if not self.clips:
            raise FileNotFoundError("no footage found: see footage/SOURCES.md and clips.toml")
        if clip and clip not in self.clips:
            raise KeyError(f"unknown clip {clip!r}; available: {', '.join(self.clips)}")
        self.rng = np.random.default_rng(seed + 7)
        self.cap = None
        self._open(clip or next(iter(self.clips)))

    # ---- clip handling ---------------------------------------------------------------------
    def _open(self, clip_id: str):
        c = self.clips[clip_id]
        if self.cap is not None:
            self.cap.release()
        self.clip = c
        self.cap = cv2.VideoCapture(str(ROOT / c["file"]))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.every = int(c.get("every", 1))               # use every n-th frame of fast footage
        self.start, self.end = float(c.get("start", 0.0)), float(c["end"])
        self.view = c.get("view")                         # [x, y, w, h] crop of the source frame
        self.truth = Truth(c["truth"], float(c.get("mm_per_m", 10.0))) if c.get("truth") else None
        self.tau_gain = float(c.get("tau_gain", 1.0))     # read by the pipeline
        self.show_hazard = bool(c.get("hazard", True))    # read by the pipeline
        self.h0 = self.truth.alt(self.start) if self.truth else 0.0
        self.t = 0.0
        self._wall = time.monotonic()
        self._rewind()

    def _rewind(self):
        self.cap.set(cv2.CAP_PROP_POS_MSEC, self.start * 1000)
        self.pos, self.playing, self.hold, self.frame = self.start, True, 0.0, None
        self._grab()

    def _grab(self) -> bool:
        ok, f = False, None
        for _ in range(self.every):
            ok, f = self.cap.read()
            if not ok:
                return False
            self.pos += 1.0 / self.fps
        if self.view:
            x, y, w, h = self.view
            f = f[y:y + h, x:x + w]
        if f.shape[1] > MAX_WIDTH:
            f = cv2.resize(f, (MAX_WIDTH, int(f.shape[0] * MAX_WIDTH / f.shape[1])), interpolation=cv2.INTER_AREA)
        self.frame = np.ascontiguousarray(f)
        return True

    @property
    def ended(self) -> bool:
        return self.pos >= self.end

    def info(self) -> dict:
        c = self.clip
        return {"id": c["id"], "name": c["name"], "mission": c.get("mission"), "credit": c.get("credit"),
                "note": c.get("note"), "truth": self.truth is not None, "mm_per_m": c.get("mm_per_m"),
                "tau_gain": self.tau_gain, "pos": round(self.pos - self.start, 1),
                "dur": round(self.end - self.start, 1)}

    def catalog(self) -> list[dict]:
        return [{"id": c["id"], "name": c["name"], "mission": c.get("mission"), "truth": bool(c.get("truth"))}
                for c in self.clips.values()]

    # ---- Source interface ------------------------------------------------------------------
    def command(self, name: str):
        if name == "descend":
            if self.ended:
                self._rewind()
            self.playing = True
        elif name == "stop":
            self.playing = False
        elif name == "reset":
            if self.pos - self.start > 0.5:               # ignore the reset that follows our own loop
                self._rewind()
        elif name.startswith("clip:") and name[5:] in self.clips:
            self._open(name[5:])

    def read(self) -> Sample:
        dt = self.every / self.fps
        if self.realtime:
            time.sleep(max(0.0, self._wall + dt - time.monotonic()))
            self._wall = time.monotonic()
        self.t += dt
        if self.ended or (self.playing and not self._grab()):
            self.pos = max(self.pos, self.end)
            self.hold += dt
            if self.hold > HOLD_S:                        # loop: time restarts, the pipeline resets
                self.t = 0.0
                self._rewind()
        alt = self.truth.alt(self.pos) if self.truth else None
        steps = int(round((self.h0 - alt) / self.mm_per_step)) if alt is not None else 0
        rf = float(alt + self.rng.normal(0, 1.5)) if alt is not None else None
        return Sample(self.t, self.frame, rf, steps, alt, self.playing and not self.ended, self.h0)

    def close(self):
        self.cap.release()
