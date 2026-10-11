"""Real footage where it can carry a replay, the simulator where it can't.

You can't move the ground under recorded footage, so a replay that needs the plateau
(`footage = false` in its scenario file) runs on the simulator. Every other replay runs on the
real landing video. One clock covers both and only drops back to zero when the clip loops, which
the pipeline treats as a clean restart.
"""
import dataclasses
import time

from .base import Sample, Source
from .sim import SimSource
from .video import VideoSource


class HybridSource(Source):
    def __init__(self, video: VideoSource, sim: SimSource):
        self.video, self.sim, self.cur = video, sim, video
        self.mm_per_step = video.mm_per_step
        self.t, self.last = 0.0, None
        self.home = video.clip["id"]             # the clip a replay flies on unless it names its own

    # The pipeline reads these straight off the source, so they follow whichever one is flying.
    kind = property(lambda self: self.cur.kind)
    h0 = property(lambda self: self.cur.h0)
    tau_gain = property(lambda self: self.cur.tau_gain)
    show_hazard = property(lambda self: self.cur.show_hazard)
    reconstructed_cam = property(lambda self: self.cur.reconstructed_cam)

    def cam_reading(self):
        return self.cur.cam_reading()

    def info(self):
        return self.video.info() if self.cur is self.video else None

    def catalog(self):
        return self.video.catalog()

    def use(self, footage: bool, clip: str | None = None):
        """Pick what the next replay flies on."""
        new = self.video if footage else self.sim
        if footage:
            self.video.command(f"clip:{clip or self.home}")
        if new is self.cur:
            return
        self.cur, self.last = new, None
        if new is self.sim and self.sim.realtime:
            self.sim.t = time.monotonic()        # the simulator's clock stood still while it was idle

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
        if self.last is not None:
            self.t = 0.0 if s.t < self.last else self.t + s.t - self.last     # a drop in time means the clip looped
        self.last = s.t
        return dataclasses.replace(s, t=self.t)

    def close(self):
        self.video.close()
        self.sim.close()
