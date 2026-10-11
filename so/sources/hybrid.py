"""Real footage where it can carry a replay, the simulator where it can't, and the live rig on demand.

You can't move the ground under recorded footage, so a replay that needs the plateau
(`footage = false` in its scenario file) runs on the simulator. Every other replay runs on the
real landing video. One clock covers both and only drops back to zero when the clip loops, which
the pipeline treats as a clean restart.

If a rig is attached, `live:on` switches over to it. While it's live, replays run their scripts on
the rig (the physical steps show up as cues for whoever is working it), and picking a footage
clip, or `live:off`, switches back.
"""
import dataclasses
import time

from .base import Sample, Source
from .sim import SimSource
from .video import VideoSource


class HybridSource(Source):
    def __init__(self, video: VideoSource, sim: SimSource, rig: Source | None = None):
        self.video, self.sim, self.rig, self.cur = video, sim, rig, video
        self.t, self.last = 0.0, None
        self.home = video.clip["id"]             # the clip a replay flies on unless it names its own

    # The pipeline reads these straight off the source, so they follow whichever one is flying.
    kind = property(lambda self: self.cur.kind)
    mm_per_step = property(lambda self: self.cur.mm_per_step)    # the rig counts servo tenths, the others stepper steps
    has_rig = property(lambda self: self.rig is not None)
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

    def go_live(self):
        if self.rig and self.cur is not self.rig:
            self.cur, self.last = self.rig, None
            self.rig.command("reset")            # back to the top, ready to calibrate

    def leave_live(self):
        if self.cur is self.rig:
            self.rig.command("stop")
            self.cur, self.last = self.sim, None
            self.sim.resync()

    def use(self, footage: bool, clip: str | None = None):
        """Pick what the next replay flies on. While the rig is live, replays stay on it."""
        if self.cur is self.rig:
            return
        if clip and clip not in self.video.clips:
            footage = False              # its own broadcast isn't downloaded, so the simulator flies it
        new = self.video if footage else self.sim
        if footage:
            self.video.command(f"clip:{clip or self.home}")
        if new is self.cur:
            return
        self.cur, self.last = new, None
        if new is self.sim and self.sim.realtime:
            self.sim.t = time.monotonic()        # the simulator's clock stood still while it was idle

    def resync(self):
        self.cur.resync()

    def command(self, name: str):
        if name == "live:on" or (name == "live:toggle" and self.cur is not self.rig):
            self.go_live()
        elif name in ("live:off", "live:toggle"):
            self.leave_live()
        elif name.startswith("texture:"):
            self.sim.command(name)
        elif name.startswith("clip:"):
            self.leave_live()                    # picking footage by hand ends the live demonstration
            self.home = name[5:] if name[5:] in self.video.clips else self.home
            self.use(True)
        else:
            self.cur.command(name)

    def read(self) -> Sample | None:
        s = self.cur.read()
        if s is None:                            # the rig's camera didn't deliver a frame
            return None
        if self.last is not None:
            self.t = 0.0 if s.t < self.last else self.t + s.t - self.last     # a drop in time means the clip looped
        self.last = s.t
        return dataclasses.replace(s, t=self.t)

    def close(self):
        for source in (self.video, self.sim, self.rig):
            if source:
                source.close()
