"""Subsidium: 2-of-3 integrity monitor over three *dissimilar* altitude witnesses.

    NAV  inertial / dead-reckoned altitude      drifts; blind to terrain changes
    RF   rangefinder                            precise; can degrade, lag, freeze, drop out
    CAM  camera time-to-contact x descent rate  scale-free; fails in low contrast / harsh shadow

Each pair is checked with a normalised residual (a chi-square test) using each sensor's own
noise model, averaged over a short window:

    r²(a, b) = (h_a - h_b)² / (σ_a² + σ_b²)

Isolation is triplex parity voting, as in redundant fly-by-wire sensors: the faulty witness is
the one that appears in both failing pairs while the third pair still agrees.

    NAV-RF ✗  NAV-CAM ✗  RF-CAM ✓   ->  inertial is wrong (real terrain change): re-anchor it
    NAV-RF ✗  RF-CAM ✗   NAV-CAM ✓  ->  rangefinder fault: exclude it
    NAV-CAM ✗ RF-CAM ✗   NAV-RF ✓   ->  camera fault: exclude it
    all ✗                            ->  unresolved: assume the closest ground (fail-safe)

With only two witnesses (camera abstaining, or rangefinder silent) a disagreement can be
*detected* but not *isolated*, and the monitor says so instead of guessing.
"""
from __future__ import annotations

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


class TriplexMonitor:
    name = "Subsidium"

    def __init__(self, cfg: dict):
        s, m = cfg["sensors"], cfg["monitor"]
        self.rf_s, self.rf_rel = s["rf_sigma_mm"], s["rf_sigma_rel"]
        self.cam_rel, self.nav_s, self.nav_drift = s["cam_sigma_rel"], s["nav_sigma_mm"], s["nav_drift_mm_s"]
        self.window, self.gate, self.persist = m["window_s"], m["chi2_gate"], m["persist_s"]
        self.min_q = cfg["camera"]["min_quality"]
        self.reset()

    def reset(self):
        self.offset = 0.0              # correction added to NAV after a confirmed terrain change
        self.t_anchor = None
        self.mode = "NOMINAL"
        self.cam_abstain = True        # until the camera first locks on
        self._cam_flip_t = None
        self._cam_ever = False
        self.hist: collections.deque = collections.deque()
        self._cand, self._cand_t = None, 0.0
        self.last_est = None

    # ---- helpers -------------------------------------------------------------------------
    def _witnesses(self, x: Inputs):
        w = {"nav": (x.h_nav + self.offset,
                     math.hypot(self.nav_s, self.nav_drift * (x.t - self.t_anchor)))}
        if x.rf is not None and x.rf > 0:
            w["rf"] = (x.rf, self.rf_s + self.rf_rel * x.rf)
        cam_ok = x.tau is not None and x.cam_q >= self.min_q and x.v > 1.0
        if cam_ok:
            h = x.tau * x.v
            w["cam"] = (h, self.cam_rel * h / max(x.cam_q, 0.3))
        return w, cam_ok

    def _pair_stats(self, t: float):
        while self.hist and t - self.hist[0][0] > self.window:
            self.hist.popleft()
        out = {}
        n = len(self.hist)
        for p in PAIRS:
            vals = [h[1][p] for h in self.hist if p in h[1]]
            out[p] = sum(vals) / len(vals) if n and len(vals) >= max(3, n // 2) else None
        return out

    def _vote(self, cand: str, t: float) -> bool:
        if cand != self._cand:
            self._cand, self._cand_t = cand, t
        return t - self._cand_t >= self.persist

    @staticmethod
    def _fuse(w: dict, use):
        num = den = 0.0
        for k in use:
            h, s = w[k]
            num += h / s ** 2
            den += 1 / s ** 2
        return (num / den, math.sqrt(1 / den)) if den else (None, None)

    # ---- main ----------------------------------------------------------------------------
    def step(self, x: Inputs) -> Belief:
        events: list[str] = []
        if self.t_anchor is None:
            self.t_anchor = x.t
            if x.rf is not None:                       # start anchored to the rangefinder
                self.offset = x.rf - x.h_nav
        w, cam_ok = self._witnesses(x)

        if cam_ok == self.cam_abstain:                  # camera availability changing: debounce it
            self._cam_flip_t = self._cam_flip_t or x.t
            if x.t - self._cam_flip_t >= (0.0 if cam_ok else self.persist):
                self.cam_abstain = not cam_ok
                self._cam_flip_t = None
                if x.v > 1.0:
                    events.append("cam_abstain" if self.cam_abstain else
                                  ("cam_back" if self._cam_ever else "cam_lock"))
                self._cam_ever = self._cam_ever or cam_ok
        else:
            self._cam_flip_t = None

        r2 = {}
        for a, b in PAIRS:
            if a in w and b in w:
                (ha, sa), (hb, sb) = w[a], w[b]
                r2[(a, b)] = (ha - hb) ** 2 / (sa ** 2 + sb ** 2)
        self.hist.append((x.t, r2))
        stats = self._pair_stats(x.t)
        bad = {p: (v is not None and v > self.gate) for p, v in stats.items()}
        have = {p: stats[p] is not None for p in PAIRS}

        # ---- candidate verdict ----
        cand = None
        if "rf" not in w:
            cand = "RF_LOST"
        elif all(have.values()):
            nr, nc, rc = bad[("nav", "rf")], bad[("nav", "cam")], bad[("rf", "cam")]
            if not (nr or nc or rc):
                cand = "NOMINAL"
            elif nr and nc and not rc:
                cand = "NAV"
            elif nr and rc and not nc:
                cand = "RF"
            elif nc and rc and not nr:
                cand = "CAM"
            elif nr and nc and rc:
                cand = "UNRESOLVED"
            # exactly one pair failing: still developing -> hold the current verdict
        elif have[("nav", "rf")]:                        # camera abstaining: detect, can't isolate
            cand = "UNRESOLVED" if bad[("nav", "rf")] and self.mode != "RF" else (
                self.mode if self.mode in ("RF", "CAM") else "NOMINAL")

        if cand is None or cand == self.mode:
            self._cand = None
        elif self._vote(cand, x.t):
            prev = self.mode
            if cand == "NAV":
                fused, _ = self._fuse(w, ("rf", "cam"))
                self.offset += fused - w["nav"][0]       # camera + rangefinder outvote inertial
                self.t_anchor = x.t
                self.hist.clear()
                w["nav"] = (fused, self.nav_s)
                self.mode = "NOMINAL"
                events.append("terrain_change")
            else:
                self.mode = cand
                events.append({"RF": "rf_fault", "CAM": "cam_fault", "RF_LOST": "rf_dropout",
                               "UNRESOLVED": "unresolved", "NOMINAL": "recovered"}[cand])
                if cand == "NOMINAL" and prev == "RF_LOST":
                    events[-1] = "rf_back"
            self._cand = None

        excluded = {"RF": ["rf"], "CAM": ["cam"], "RF_LOST": ["rf"]}.get(self.mode, [])
        use = [k for k in w if k not in excluded]
        if self.mode == "UNRESOLVED":
            est = min(h for h, _ in w.values())          # fail-safe: brake for the closest ground
            sig = max(h for h, _ in w.values()) - est
        else:
            est, sig = self._fuse(w, use)
        self.last_est = est
        status = STATUS[self.mode] + (" · CAMERA ABSTAINING" if self.cam_abstain else "")
        detail = {
            "witness": {k: {"h": h, "sigma": s} for k, (h, s) in w.items()},
            "pairs": {f"{a}-{b}": (None if stats[(a, b)] is None else round(stats[(a, b)], 2)) for a, b in PAIRS},
            "gate": self.gate,
            "cam_abstain": self.cam_abstain,
        }
        return Belief(est, sig, status, excluded, events, detail)
