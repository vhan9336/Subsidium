"""The old-fashioned gate we compare against. It's the logic ispace described for HAKUTO-R Mission 1.

Follow the inertial estimate. Take a rangefinder reading only if it lands near where inertial
expects it. If readings keep getting rejected, declare the rangefinder dead for good.

When the ground really does change, inertial is the one that's wrong and the rangefinder is
right, but the gate has no way to know that. It also follows a rangefinder that degrades
slowly, because every small step still looks plausible.
"""
from .types import Belief, Inputs


class LegacyGate:
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
        # carry the estimate forward by however much inertial says we moved
        self.est += x.h_nav - self.prev_nav
        self.prev_nav = x.h_nav

        if not self.rf_failed and x.rf is not None:
            if abs(x.rf - self.est) < self.gate:
                self.est += self.alpha * (x.rf - self.est)     # nudge toward the rangefinder
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
