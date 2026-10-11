"""Real footage where it can carry a replay, the simulator where it cannot.

Recorded footage cannot have the ground moved under it, so a replay that needs the plateau
(`footage = false` in its scenario file) runs on the simulator; every other replay runs on the
real landing video. One clock runs across both; it only goes back to zero when the clip loops,
which the pipeline treats as a clean restart.
"""
from __future__ import annotations

import dataclasses
import time

from .base import Sample, Source
from .sim import SimSource
from .video import VideoSource


class HybridSource(Source):
    def __init__(self, video: VideoSource, sim: SimSource):
        self.video, self.sim, self.cur = video, sim, video
        self.mm_per_step = video.mm_per_step
        self.t, self._last = 0.0, None
        self.home = video.clip["id"]             # the clip replays fly on unless they name their own

    # what the pipeline reads off a source follows whichever one is flying
    kind = property(lambda self: self.cur.kind)
    h0 = property(lambda self: self.cur.h0)
    tau_gain = property(lambda self: getattr(self.cur, "tau_gain", 1.0))
    show_hazard = property(lambda self: getattr(self.cur, "show_hazard", True))
    reconstructed_cam = property(lambda self: getattr(self.cur, "reconstructed_cam", False))

    def cam_reading(self):
        return self.cur.cam_reading()

    def info(self) -> dict | None:
        return self.video.info() if self.cur is self.video else None

    def catalog(self) -> list[dict]:
        return self.video.catalog()

    def use(self, footage: bool, clip: str | None = None):
        new = self.video if footage else self.sim
        if footage:
            self.video.command(f"clip:{clip or self.home}")
        if new is self.cur:
            return
        self.cur, self._last = new, None
        if new is self.sim and self.sim.realtime:
            self.sim.t = time.monotonic()        # no time passed for the simulator while it was idle

    def command(self, name: str):
        if name.startswith("texture:"):
            self.sim.command(name)
        elif name.startswith("clip:"):
            self.home = name[5:] if name[5:] in self.video.clips else self.home
            self.use(True)
        else:
            self.cur.command(name)

    def read(self) -> Sample:
        s = self.cur.read()
        if self._last is not None and s.t < self._last:
            self.t = 0.0                             # the clip looped
        elif self._last is not None:
            self.t += s.t - self._last
        self._last = s.t
        return dataclasses.replace(s, t=self.t)

    def close(self):
        self.video.close()
        self.sim.close()
