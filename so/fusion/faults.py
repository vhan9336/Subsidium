"""Software fault injection on the live sensor stream (the way flight software is tested).

The raw readings are kept untouched as ground truth for scoring both brains.

  rf_lag    readings arrive later and later (ramps up): Resilience-style degraded rangefinder
  rf_freeze rangefinder stuck on one value
  rf_drop   no echo at all
  cam_bias  camera misjudges time-to-contact by a constant factor: Athena-style lighting trouble
  cam_blind camera loses lock entirely (equivalent to switching the lamp off on the rig)
"""
from __future__ import annotations

import collections

RF_FAULTS = ("rf_lag", "rf_freeze", "rf_drop")
CAM_FAULTS = ("cam_bias", "cam_blind")


class FaultInjector:
    def __init__(self, cfg: dict):
        f = cfg["faults"]
        self.lag_s, self.ramp_s, self.bias = f["lag_s"], f["lag_ramp_s"], f["cam_bias"]
        self.hist: collections.deque = collections.deque(maxlen=4000)
        self.clear()

    def clear(self):
        self.rf_mode = self.cam_mode = None
        self.t_rf = self.t_cam = 0.0
        self.frozen = None

    def set(self, mode: str | None, t: float):
        if mode is None or mode == "clear":
            self.clear()
        elif mode in RF_FAULTS:
            self.rf_mode, self.t_rf, self.frozen = mode, t, None
        elif mode in CAM_FAULTS:
            self.cam_mode, self.t_cam = mode, t
        else:
            raise ValueError(mode)

    @property
    def active(self) -> list[str]:
        return [m for m in (self.rf_mode, self.cam_mode) if m]

    def rf(self, t: float, rf: float | None) -> float | None:
        if rf is not None:
            self.hist.append((t, rf))
        if self.rf_mode == "rf_lag":
            lag = self.lag_s * min(1.0, (t - self.t_rf) / self.ramp_s)
            past = None
            for ti, r in self.hist:
                if ti <= t - lag:
                    past = r
                else:
                    break
            return past if past is not None else rf
        if self.rf_mode == "rf_freeze":
            if self.frozen is None:
                self.frozen = rf
            return self.frozen
        if self.rf_mode == "rf_drop":
            return None
        return rf

    def cam(self, tau: float | None, q: float) -> tuple[float | None, float]:
        if self.cam_mode == "cam_bias" and tau is not None:
            return tau * self.bias, q
        if self.cam_mode == "cam_blind":
            return None, 0.0
        return tau, q
