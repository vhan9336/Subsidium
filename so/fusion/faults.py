"""Breaks the sensor data on purpose, the way flight software gets tested.

The untouched readings are kept elsewhere as the answer key, so both brains can be scored.

  rf_lag     the rangefinder falls further and further behind (Resilience)
  rf_freeze  the rangefinder gets stuck on one value
  rf_drop    no echo at all (Odysseus)
  cam_bias   the camera misjudges time to contact by a fixed factor (Athena)
  cam_blind  the camera loses its lock, same as switching the lamp off on the rig
"""
import collections

RF_FAULTS = ("rf_lag", "rf_freeze", "rf_drop")
CAM_FAULTS = ("cam_bias", "cam_blind")


class FaultInjector:
    def __init__(self, cfg: dict):
        f = cfg["faults"]
        self.lag_s, self.ramp_s, self.bias = f["lag_s"], f["lag_ramp_s"], f["cam_bias"]
        self.hist = collections.deque(maxlen=4000)      # recent (time, rangefinder) pairs, for the lag
        self.clear()

    def clear(self):
        self.rf_mode = self.cam_mode = None
        self.t_rf = 0.0
        self.frozen = None

    def set(self, mode: str, t: float):
        if mode == "clear":
            self.clear()
        elif mode in RF_FAULTS:
            self.rf_mode, self.t_rf, self.frozen = mode, t, None
        elif mode in CAM_FAULTS:
            self.cam_mode = mode
        else:
            raise ValueError(mode)

    @property
    def active(self) -> list[str]:
        return [m for m in (self.rf_mode, self.cam_mode) if m]

    def rf(self, t: float, rf: float | None) -> float | None:
        if rf is not None:
            self.hist.append((t, rf))
        if self.rf_mode == "rf_lag":
            # the delay grows from zero to lag_s over ramp_s, so it creeps in instead of jumping
            lag = self.lag_s * min(1.0, (t - self.t_rf) / self.ramp_s)
            old = [r for ti, r in self.hist if ti <= t - lag]
            return old[-1] if old else rf
        if self.rf_mode == "rf_freeze":
            if self.frozen is None:
                self.frozen = rf
            return self.frozen
        return None if self.rf_mode == "rf_drop" else rf

    def cam(self, tau: float | None, q: float) -> tuple[float | None, float]:
        if self.cam_mode == "cam_bias" and tau is not None:
            return tau * self.bias, q
        if self.cam_mode == "cam_blind":
            return None, 0.0
        return tau, q
