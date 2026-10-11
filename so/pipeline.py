"""The flight loop: source -> camera -> faults -> both brains -> a state dict for the dashboard.

Everything runs on the source's own clock (real time on the rig, virtual time in fast
simulation, recorded time in a replay), so results can be repeated exactly.
"""
import collections
import json
import queue

import cv2
import numpy as np

from .config import ROOT
from .fusion.faults import FaultInjector
from .fusion.legacy import LegacyGate
from .fusion.triplex import TriplexMonitor
from .fusion.types import Inputs
from .scenarios import ScenarioRunner, load_all
from .sources.replay import Recorder, ReplaySource
from .vision import overlay
from .vision.ttc import TTCEstimator, TTCResult

SPEED_WINDOW_S = 0.6        # descent speed is the slope of the step count over this long


class Pipeline:
    def __init__(self, cfg: dict, source, log_path: str | None = "flight_log.jsonl"):
        self.cfg, self.src = cfg, source
        cam = cfg["camera"]
        self.ttc = TTCEstimator(lookback_s=cam["lookback_s"], grid=cam["grid"])
        self.legacy, self.so = LegacyGate(cfg), TriplexMonitor(cfg)
        self.faults = FaultInjector(cfg)
        self.scenarios = load_all()
        self.runner = ScenarioRunner()
        self.commands = queue.Queue()          # filled by the server thread, emptied by tick()
        self.recorder = None
        self.steps_hist = collections.deque()  # (time, steps), for the descent speed
        self.moving_since = None
        self.last_t = None
        self.jpeg = b""
        self.alt_jpeg = b""                   # the second view, when a source has one
        self.log = open(log_path, "a") if log_path else None
        self.reset_score()

    def command(self, name: str):
        """Safe to call from any thread. It's applied at the start of the next tick."""
        self.commands.put(name)

    def start_recording(self, folder: str):
        self.commands.put(f"record:{folder}")

    def reset_score(self):
        self.score = {"legacy": {"max": 0.0, "last": None}, "so": {"max": 0.0, "last": None}}

    def apply(self, name: str, t: float, record: bool):
        if record and self.recorder and not name.startswith("record"):
            self.recorder.command(t, name)
        if name.startswith("record:"):
            meta = {"mm_per_step": self.src.mm_per_step, "h0": self.src.h0, "source": self.src.kind}
            self.recorder = Recorder(name[7:], meta)
        elif name == "record_stop":
            if self.recorder:
                self.recorder.close()
            self.recorder = None
        elif name.startswith("fault:"):
            self.faults.set(name[6:], t)
        elif name.startswith("scenario:"):
            self.start_scenario(name[9:], t)
        elif name.startswith("live:"):
            if self.src.has_rig:                    # switching between the live rig and the simulator
                self.src.command(name)
                self.apply("reset", t, record=False)
                self.runner.stop()
                self.faults.clear()
        elif name.startswith("clip:"):
            # picking footage by hand ends any replay that was flying and clears its injected faults
            self.runner.stop()
            self.faults.clear()
            self.src.command(name)
        elif name == "restart":
            # run the current replay again from the top, or just reset if none is running
            sid = self.runner.spec["id"] if self.runner.spec else None
            self.apply("reset", t, record=False)
            self.faults.clear()
            if sid:
                self.start_scenario(sid, t)
        elif name == "reset":
            self.src.command("reset")
            for part in (self.ttc, self.legacy, self.so):
                part.reset()
            self.steps_hist.clear()
            self.faults.hist.clear()           # or a lagging rangefinder would replay readings from before the reset
            self.moving_since = None
            self.reset_score()
        else:
            self.src.command(name)

    def start_scenario(self, sid: str, t: float):
        if sid == "stop":
            self.runner.stop()
        elif sid in self.scenarios:
            spec = self.scenarios[sid]
            # a mission replay descends over the orbiter photo of where that lander really came down
            site = ROOT / spec["site"] if spec.get("site") else None
            self.src.command("texture:" + (str(site) if site and site.exists() else ""))
            if hasattr(self.src, "use"):       # footage plus simulator: pick whichever this replay can run on
                self.src.use(spec.get("footage", True), spec.get("clip"))
            self.runner.start(spec, t)

    def descent_speed(self, t: float, steps: int) -> float:
        """Speed in mm/s from the stepper's recent slope. Zero until there's enough history."""
        self.steps_hist.append((t, steps))
        while t - self.steps_hist[0][0] > SPEED_WINDOW_S:
            self.steps_hist.popleft()
        (ta, sa), (tb, sb) = self.steps_hist[0], self.steps_hist[-1]
        return (sb - sa) * self.src.mm_per_step / (tb - ta) if tb - ta > 0.2 else 0.0

    def read_camera(self, s, steady: bool):
        """Time to contact and quality, from real vision or (for footage with no camera) the source."""
        if self.src.reconstructed_cam:
            res = TTCResult(None, None, 0.0, 0, 0.0)
            tau_raw, q_raw = self.src.cam_reading()
        else:
            res = self.ttc.update(s.t, s.frame)
            tau_raw = None if res.tau is None else res.tau * self.src.tau_gain
            q_raw = res.quality
        # the camera only means anything once the whole look-back window is steady descent
        tau, q = self.faults.cam(tau_raw if steady else None, q_raw if steady else 0.0)
        return res, tau_raw, q_raw, tau, q

    def tick(self) -> dict | None:
        # Commands go first, stamped with the previous tick's time, so this tick's reading reflects them
        tp = self.last_t if self.last_t is not None else 0.0
        if isinstance(self.src, ReplaySource) and self.last_t is not None:
            for name in self.src.due_commands(tp):
                self.apply(name, tp, record=False)
        while not self.commands.empty():
            self.apply(self.commands.get(), tp, record=True)
        for name in self.runner.due(tp):
            self.apply(name, tp, record=False)

        s = self.src.read()
        if s is None:
            return None
        t = s.t
        if self.last_t is not None and t < self.last_t:
            self.restart(t)
        self.last_t = t
        if self.recorder:
            self.recorder.frame(s)

        # navigation: dead reckoning from the stepper count
        h0 = s.h0 if s.h0 is not None else (s.rf_raw or 0.0)
        h_nav = h0 - s.steps * self.src.mm_per_step
        v = self.descent_speed(t, s.steps)
        self.moving_since = (self.moving_since or t) if v > 1.0 else None
        steady = self.moving_since is not None and t - self.moving_since > self.ttc.lookback_s + 0.4

        res, tau_raw, q_raw, tau, q = self.read_camera(s, steady)
        rf = self.faults.rf(t, s.rf_raw)
        x = Inputs(t, h_nav, v, rf, tau, q)
        legacy, so = self.legacy.step(x), self.so.step(x)

        truth = s.true_alt if s.true_alt is not None else s.rf_raw
        for key, belief in (("legacy", legacy), ("so", so)):
            if truth is not None and belief.est is not None and v > 1.0:
                err = belief.est - truth
                self.score[key]["last"] = round(err, 1)
                self.score[key]["max"] = round(max(self.score[key]["max"], abs(err)), 1)

        w = so.detail["witness"]
        state = {
            "t": t, "kind": self.src.kind, "recording": self.recorder is not None,
            "truth": truth, "nav": w["nav"]["h"], "nav_raw": h_nav,
            "rf": rf, "rf_raw": s.rf_raw, "cam": w.get("cam", {}).get("h"), "v": v, "tau": tau, "q": round(q, 2),
            "tau_raw": tau_raw, "q_raw": round(q_raw, 2), "clip": self.src.info(),
            "h0": h0, "descending": s.descending,
            "legacy": {"est": legacy.est, "status": legacy.status, "excluded": legacy.excluded},
            "so": {"est": so.est, "sigma": so.sigma, "status": so.status, "excluded": so.excluded,
                   **{k: so.detail[k] for k in ("pairs", "gate", "cam_abstain", "witness")}},
            "hazard": None if res.hazard is None else np.nan_to_num(res.hazard, nan=-1).round(3).tolist(),
            "site": res.site, "hazard_shown": self.src.show_hazard, "rig": self.src.has_rig, "faults": self.faults.active, "scenario": self.runner.state(t),
            "events": legacy.events + so.events, "score": self.score,
        }
        if self.log:
            self.log.write(json.dumps({k: val for k, val in state.items() if k != "hazard"}) + "\n")
        cam = self.cfg["camera"]
        self.alt_jpeg = b""
        if s.alt_frame is not None:
            self.alt_jpeg = cv2.imencode(".jpg", s.alt_frame, [cv2.IMWRITE_JPEG_QUALITY, cam.get("jpeg_quality", 75)])[1].tobytes()
        self.jpeg = overlay.draw(s.frame, res, s.frame.shape[1] / self.ttc.width,
                                 self.src.show_hazard, cam.get("hazard_tint", 0.25), cam.get("jpeg_quality", 75))
        return state

    def restart(self, t: float):
        """Time went backwards, so a replay or clip looped. Start clean."""
        again = self.runner.spec["id"] if self.runner.spec and self.src.kind == "video" else None
        self.apply("reset", t, record=False)
        self.runner.stop()
        self.faults.clear()
        if again:                              # footage loops, so the mission replay runs again with it
            self.apply(f"scenario:{again}", t, record=False)
