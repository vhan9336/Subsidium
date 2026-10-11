"""Real landing footage as the camera.

The pictures are real, so time to contact is measured from real images. What footage can't give
us is a rangefinder or an inertial unit, so we make those two from the clip's altitude record
(`truth` in clips.toml), scaled to the rig and with the same noise as the simulator. A clip
with no altitude record is "tracking only": the camera runs and nothing gets voted on.

Time here is seconds of video. The clock keeps running while paused so scenario scripts still
fire. It only goes back to zero when the clip loops, which the pipeline treats as a fresh start.
"""
import csv
import time
import tomllib

import cv2
import numpy as np

from ..config import ROOT
from .base import Sample, Source

HOLD_S = 3.0          # sit on the last frame this long before looping
MAX_WIDTH = 1024      # scale wider frames down before streaming them


def load_clips() -> dict[str, dict]:
    """The clips in clips.toml whose video file is actually on disk."""
    with open(ROOT / "clips.toml", "rb") as f:
        raw = tomllib.load(f)
    return {k: {**v, "id": k} for k, v in raw.items() if (ROOT / v["file"]).exists()}


class Truth:
    """An altitude record (t, alt_m) turned into a smooth altitude in rig mm.

    Callouts are coarse (whole metres), so a cubic is fitted through them. Readings that are
    already fine-grained (telemetry) are joined with straight lines instead (fit = "linear").
    """

    def __init__(self, path, mm_per_m: float, fit: str = "cubic"):
        rows = list(csv.DictReader(open(ROOT / path)))
        self.t = np.array([float(r["t"]) for r in rows])
        self.mm = np.array([float(r["alt_m"]) for r in rows]) * mm_per_m
        self.poly = None if fit == "linear" else np.polyfit(self.t, self.mm, 3)

    def alt(self, t: float) -> float:
        t = min(max(t, self.t[0]), self.t[-1])
        alt = np.interp(t, self.t, self.mm) if self.poly is None else np.polyval(self.poly, t)
        return float(max(alt, 1.0))


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
        self.open(clip or next(iter(self.clips)))

    def open(self, clip_id: str):
        """Switch to a clip and read its settings from clips.toml."""
        c = self.clip = self.clips[clip_id]
        if self.cap:
            self.cap.release()
        self.cap = cv2.VideoCapture(str(ROOT / c["file"]))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.every = int(c.get("every", 1))               # for fast footage, use every n-th frame
        self.start, self.end = float(c.get("start", 0.0)), float(c["end"])
        self.view = c.get("view")                         # [x, y, w, h] crop of the source frame
        scale = float(c.get("mm_per_m", 10.0))
        self.truth = Truth(c["truth"], scale, c.get("fit", "cubic")) if c.get("truth") else None
        # some records show what the lander *believed*. The real altitude is that plus a reported error
        self.offset = float(c.get("offset_m", 0.0)) * scale if c.get("believed") else 0.0
        self.offset_at = float(c.get("offset_at", 0.0))
        self.reconstructed_cam = c.get("camera") == "reconstructed"
        self.cam = (None, 0.0)                            # the made-up camera reading, when there's no camera
        self.tau_gain = float(c.get("tau_gain", 1.0))
        self.show_hazard = bool(c.get("hazard", True))
        self.h0 = self.truth.alt(self.start) if self.truth else 0.0
        self.t = 0.0
        self.wall = time.monotonic()
        self.rewind()

    def rewind(self):
        self.cap.set(cv2.CAP_PROP_POS_MSEC, self.start * 1000)
        self.pos, self.playing, self.hold, self.frame = self.start, True, 0.0, None
        self.grab()

    def grab(self) -> bool:
        """Read the next frame (skipping `every` - 1), crop it and shrink it. False at the end of the file."""
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
                "camera": "reconstructed" if self.reconstructed_cam else "measured",
                "believed": bool(c.get("believed")), "tau_gain": self.tau_gain,
                "pos": round(self.pos - self.start, 1), "dur": round(self.end - self.start, 1)}

    def catalog(self) -> list[dict]:
        return [{"id": c["id"], "name": c["name"], "mission": c.get("mission"), "truth": bool(c.get("truth"))}
                for c in self.clips.values() if not c.get("replay_only")]

    def cam_reading(self) -> tuple[float | None, float]:
        """Time to contact and lock quality, for a clip with no descent camera in it."""
        return self.cam

    def command(self, name: str):
        if name == "descend":
            if self.ended:
                self.rewind()
            self.playing = True
        elif name == "stop":
            self.playing = False
        elif name == "reset":
            if self.pos - self.start > 0.5:               # skip the reset that follows our own loop
                self.rewind()
        elif name.startswith("clip:") and name[5:] in self.clips:
            if name[5:] != self.clip["id"]:
                self.open(name[5:])
            elif self.pos - self.start > 0.5:
                self.rewind()

    def read(self) -> Sample:
        dt = self.every / self.fps
        if self.realtime:
            time.sleep(max(0.0, self.wall + dt - time.monotonic()))
            self.wall = time.monotonic()
        self.t += dt
        if self.ended or (self.playing and not self.grab()):
            self.pos = max(self.pos, self.end)
            self.hold += dt
            if self.hold > HOLD_S:                        # loop: the clock restarts and the pipeline resets
                self.t = 0.0
                self.rewind()

        nav = self.truth.alt(self.pos) if self.truth else None     # what the inertial unit believes
        alt = nav
        if nav is not None and self.offset and self.pos >= self.offset_at:
            alt = nav + self.offset * min(1.0, self.pos - self.offset_at)   # the error opens up over one second
        rf = float(alt + self.rng.normal(0, 1.5)) if alt is not None else None
        steps = int(round((self.h0 - nav) / self.mm_per_step)) if nav is not None else 0
        if self.reconstructed_cam and alt is not None:
            # Use the descent speed over the same 0.6 s the pipeline uses, so tau x v gives the altitude back
            rate = (self.truth.alt(self.pos - 0.6) - nav) / 0.6
            self.cam = (float(alt / rate * (1 + self.rng.normal(0, 0.02))), 0.9) if rate > 1.0 else (None, 0.0)
        return Sample(self.t, self.frame, rf, steps, alt, self.playing and not self.ended, self.h0)

    def close(self):
        self.cap.release()
