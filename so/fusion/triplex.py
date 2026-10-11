"""Subsidium: three altitude witnesses vote, and the odd one out gets ignored.

    NAV  inertial     smooth, but drifts, and it can't see the ground change under it
    RF   rangefinder  precise, but can degrade, lag, freeze or go silent
    CAM  camera       altitude = time to contact x speed. Fails in low contrast or harsh shadow

Every pair gets a normalised error test, using each sensor's own noise level:

    r2(a, b) = (h_a - h_b)^2 / (sigma_a^2 + sigma_b^2)

An r2 above the gate (9, which is 3 sigma) means the two disagree by more than noise explains.
Then it's triplex parity voting, like redundant sensors in a fly-by-wire jet. The broken
sensor is the one that shows up in both failing pairs while the third pair still agrees:

    NAV-RF fails, NAV-CAM fails, RF-CAM agrees   inertial is wrong (real terrain change), re-anchor it
    NAV-RF fails, RF-CAM fails, NAV-CAM agrees   rangefinder is wrong, ignore it
    NAV-CAM fails, RF-CAM fails, NAV-RF agrees   camera is wrong, ignore it
    all three fail                               nobody to blame, so assume the closest ground

With only two witnesses (camera abstaining, rangefinder silent) a disagreement can be spotted
but not pinned on anyone. The monitor says that instead of guessing.
"""
import collections
import math

from .types import Belief, Inputs

PAIRS = (("nav", "rf"), ("nav", "cam"), ("rf", "cam"))
STATUS = {
    "NOMINAL": "NOMINAL",
    "RF": "RANGEFINDER EXCLUDED",
    "CAM": "CAMERA EXCLUDED",
    "RF_LOST": "RANGEFINDER SILENT",
    "UNRESOLVED": "UNRESOLVED · ASSUMING CLOSEST GROUND",
}
# the event announced when the monitor moves into each mode
EVENT = {"RF": "rf_fault", "CAM": "cam_fault", "RF_LOST": "rf_dropout",
         "UNRESOLVED": "unresolved", "NOMINAL": "recovered"}


class TriplexMonitor:
    def __init__(self, cfg: dict):
        s, m = cfg["sensors"], cfg["monitor"]
        self.rf_sigma, self.rf_rel = s["rf_sigma_mm"], s["rf_sigma_rel"]
        self.cam_rel = s["cam_sigma_rel"]
        self.nav_sigma, self.nav_drift = s["nav_sigma_mm"], s["nav_drift_mm_s"]
        self.window, self.gate, self.persist = m["window_s"], m["chi2_gate"], m["persist_s"]
        self.min_quality = cfg["camera"]["min_quality"]
        self.reset()

    def reset(self):
        self.offset = 0.0              # correction added to inertial after a confirmed terrain change
        self.t_anchor = None           # when inertial was last corrected; its drift is counted from here
        self.mode = "NOMINAL"
        self.cam_abstain = True        # the camera sits out until it first locks on
        self.cam_flip_t = None         # when the camera started to change its mind
        self.cam_seen = False
        self.hist = collections.deque()          # (time, {pair: r2}) over the averaging window
        self.cand, self.cand_t = None, 0.0       # the verdict we're waiting to confirm, and since when

    def witnesses(self, x: Inputs):
        """Each available sensor as (altitude, sigma), and whether the camera can be used."""
        drift = self.nav_drift * (x.t - self.t_anchor)
        w = {"nav": (x.h_nav + self.offset, math.hypot(self.nav_sigma, drift))}
        if x.rf is not None and x.rf > 0:
            w["rf"] = (x.rf, self.rf_sigma + self.rf_rel * x.rf)
        cam_ok = x.tau is not None and x.cam_q >= self.min_quality and x.v > 1.0
        if cam_ok:
            h = x.tau * x.v
            w["cam"] = (h, self.cam_rel * h / max(x.cam_q, 0.3))
        return w, cam_ok

    def pair_stats(self, t: float) -> dict:
        """Each pair's r2 averaged over the last window. None if there isn't enough data yet."""
        while self.hist and t - self.hist[0][0] > self.window:
            self.hist.popleft()
        out = {}
        for p in PAIRS:
            vals = [r2[p] for _, r2 in self.hist if p in r2]
            out[p] = sum(vals) / len(vals) if len(vals) >= max(3, len(self.hist) // 2) else None
        return out

    def confirmed(self, cand: str, t: float) -> bool:
        """A verdict only counts once it has held for `persist` seconds, so one bad frame can't flip it."""
        if cand != self.cand:
            self.cand, self.cand_t = cand, t
        return t - self.cand_t >= self.persist

    @staticmethod
    def fuse(w: dict, use):
        """Average the chosen sensors, trusting the more certain ones more (inverse variance)."""
        den = sum(1 / w[k][1] ** 2 for k in use)
        if not den:
            return None, None
        return sum(w[k][0] / w[k][1] ** 2 for k in use) / den, math.sqrt(1 / den)

    def debounce_camera(self, x: Inputs, cam_ok: bool, events: list):
        """The camera has to stay gone for `persist` seconds to count as abstaining. Coming back is instant."""
        if cam_ok != self.cam_abstain:
            self.cam_flip_t = None
            return
        self.cam_flip_t = self.cam_flip_t or x.t
        if x.t - self.cam_flip_t >= (0.0 if cam_ok else self.persist):
            self.cam_abstain = not cam_ok
            self.cam_flip_t = None
            if x.v > 1.0:
                events.append("cam_abstain" if self.cam_abstain else ("cam_back" if self.cam_seen else "cam_lock"))
            self.cam_seen = self.cam_seen or cam_ok

    def candidate(self, w: dict, bad: dict, have: dict):
        """Today's verdict from the pair tests, or None to keep the current one."""
        if "rf" not in w:
            return "RF_LOST"
        if all(have.values()):
            nr, nc, rc = bad[("nav", "rf")], bad[("nav", "cam")], bad[("rf", "cam")]
            return {(0, 0, 0): "NOMINAL", (1, 1, 0): "NAV", (1, 0, 1): "RF",
                    (0, 1, 1): "CAM", (1, 1, 1): "UNRESOLVED"}.get((nr, nc, rc))   # one failing pair: still unfolding
        if have[("nav", "rf")]:       # camera sitting out: we can see a disagreement but not blame anyone
            if bad[("nav", "rf")] and self.mode != "RF":
                return "UNRESOLVED"
            return self.mode if self.mode in ("RF", "CAM") else "NOMINAL"

    def step(self, x: Inputs) -> Belief:
        events: list[str] = []
        if self.t_anchor is None:
            self.t_anchor = x.t
            if x.rf is not None:                    # start out anchored to the rangefinder
                self.offset = x.rf - x.h_nav
        w, cam_ok = self.witnesses(x)
        self.debounce_camera(x, cam_ok, events)

        r2 = {(a, b): (w[a][0] - w[b][0]) ** 2 / (w[a][1] ** 2 + w[b][1] ** 2)
              for a, b in PAIRS if a in w and b in w}
        self.hist.append((x.t, r2))
        stats = self.pair_stats(x.t)
        bad = {p: int(v is not None and v > self.gate) for p, v in stats.items()}
        have = {p: v is not None for p, v in stats.items()}

        cand = self.candidate(w, bad, have)
        if cand is None or cand == self.mode:
            self.cand = None
        elif self.confirmed(cand, x.t):
            prev = self.mode
            if cand == "NAV":
                # camera and rangefinder outvote inertial: shift inertial onto them and restart its drift clock
                fused, _ = self.fuse(w, ("rf", "cam"))
                self.offset += fused - w["nav"][0]
                self.t_anchor = x.t
                self.hist.clear()
                w["nav"] = (fused, self.nav_sigma)
                self.mode = "NOMINAL"
                events.append("terrain_change")
            else:
                self.mode = cand
                events.append("rf_back" if cand == "NOMINAL" and prev == "RF_LOST" else EVENT[cand])
            self.cand = None

        excluded = {"RF": ["rf"], "CAM": ["cam"], "RF_LOST": ["rf"]}.get(self.mode, [])
        if self.mode == "UNRESOLVED":
            # nobody to blame, so brake for the lowest reading: hitting the ground early beats late
            est = min(h for h, _ in w.values())
            sigma = max(h for h, _ in w.values()) - est
        else:
            est, sigma = self.fuse(w, [k for k in w if k not in excluded])
        status = STATUS[self.mode] + (" · CAMERA ABSTAINING" if self.cam_abstain else "")
        detail = {
            "witness": {k: {"h": h, "sigma": s} for k, (h, s) in w.items()},
            "pairs": {f"{a}-{b}": None if stats[(a, b)] is None else round(stats[(a, b)], 2) for a, b in PAIRS},
            "gate": self.gate,
            "cam_abstain": self.cam_abstain,
        }
        return Belief(est, sigma, status, excluded, events, detail)
