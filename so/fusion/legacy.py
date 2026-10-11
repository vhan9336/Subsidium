"""The textbook altimeter gate — the logic pattern ispace reported for HAKUTO-R Mission 1.

Trust the inertial estimate; accept the rangefinder only when it is close to what the inertial
estimate expects; if it keeps disagreeing, declare it failed. ispace: the measured altitude
"rose sharply" passing a ~3 km crater rim, the software judged it abnormal and filtered it out,
and the lander believed it was at the surface while ~5 km up.

The same gate also follows a slowly degrading sensor, because each small step looks plausible.
"""
from __future__ import annotations

from .types import Belief, Inputs


class LegacyGate:
    name = "Legacy gate"

    def __init__(self, cfg: dict):
        self.gate = cfg["legacy"]["gate_mm"]
        self.alpha = cfg["legacy"]["alpha"]
        self.fail_after = cfg["legacy"]["fail_after"]
        self.reset()

    def reset(self):
        self.est = None
        self.prev_nav = None
        self.rejects = 0
        self.rf_failed = False
        self.status = "NOMINAL"

    def step(self, x: Inputs) -> Belief:
        events = []
        if self.est is None:
            self.est = x.rf if x.rf is not None else x.h_nav
            self.prev_nav = x.h_nav
        self.est += x.h_nav - self.prev_nav          # propagate with the inertial estimate
        self.prev_nav = x.h_nav
        if not self.rf_failed and x.rf is not None:
            if abs(x.rf - self.est) < self.gate:
                self.est += self.alpha * (x.rf - self.est)
                self.rejects = 0
                self.status = "NOMINAL"
            else:
                self.rejects += 1
                self.status = "RF REJECTED"
                if self.rejects >= self.fail_after:
                    self.rf_failed = True
                    events.append("legacy_rf_failed")
        if self.rf_failed:
            self.status = "RF DECLARED FAILED"
        return Belief(self.est, None, self.status, ["rf"] if self.rf_failed else [], events)
