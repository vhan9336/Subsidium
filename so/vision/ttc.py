"""Time-to-contact (tau) from image expansion — the camera's independent altitude check.

Physics: a camera descending at speed v toward ground at distance Z sees the ground
image grow. Between two frames dt apart the image scales by s = Z_old / Z_new, so

    tau_new = Z_new / v = dt / (s - 1)

tau needs no map, no known scale and no lidar. Gannets time their dive with it
(Lee & Reddish, Nature 1981). Multiply by the descent rate from navigation and you
get an altitude that shares no hardware with the rangefinder:  h_vis = tau * v.

Hazards come from the same math: a boulder is closer than the ground around it, so
its patch of image expands faster. Per-tile expansion -> per-tile relative height.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class TTCResult:
    tau: float | None            # seconds to contact (None = not approaching / no lock)
    scale: float | None          # image scale between compared frames
    dt: float                    # seconds between compared frames
    n_inliers: int
    quality: float               # 0..1 (inlier ratio, penalised for few points)
    hazard: np.ndarray | None = None      # GxG relative height above ground, fraction of altitude (nan = no data)
    site: tuple[int, int] | None = None   # (row, col) of safest tile
    points: np.ndarray | None = field(default=None, repr=False)  # inlier points (new frame) for overlay


class TTCEstimator:
    def __init__(self, width: int = 320, lookback_s: float = 0.5, grid: int = 6,
                 max_corners: int = 400, smooth: int = 5):
        self.width = width
        self.lookback_s = lookback_s
        self.grid = grid
        self.max_corners = max_corners
        self.buf: collections.deque[tuple[float, np.ndarray]] = collections.deque(maxlen=120)
        self.taus: collections.deque[tuple[float, float]] = collections.deque(maxlen=smooth)
        self.hazard_avg: np.ndarray | None = None

    def reset(self):
        self.buf.clear()
        self.taus.clear()
        self.hazard_avg = None

    def _prep(self, frame: np.ndarray) -> np.ndarray:
        g = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = g.shape
        if w != self.width:
            g = cv2.resize(g, (self.width, int(h * self.width / w)), interpolation=cv2.INTER_AREA)
        return cv2.equalizeHist(g)

    def update(self, t: float, frame: np.ndarray) -> TTCResult:
        g = self._prep(frame)
        self.buf.append((t, g))
        # pick the newest buffered frame that is at least lookback_s old
        old = None
        for tb, gb in self.buf:
            if t - tb >= self.lookback_s:
                old = (tb, gb)
            else:
                break
        if old is None:
            return TTCResult(None, None, 0.0, 0, 0.0)
        t0, g0 = old
        dt = t - t0
        return self._compare(g0, g, dt)

    def _compare(self, g0: np.ndarray, g1: np.ndarray, dt: float) -> TTCResult:
        p0 = cv2.goodFeaturesToTrack(g0, self.max_corners, 0.01, 6, blockSize=7)
        if p0 is None or len(p0) < 12:
            return TTCResult(None, None, dt, 0, 0.0)
        p1, st, _ = cv2.calcOpticalFlowPyrLK(g0, g1, p0, None, winSize=(21, 21), maxLevel=3,
                                             criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
        ok = st.reshape(-1) == 1
        a, b = p0.reshape(-1, 2)[ok], p1.reshape(-1, 2)[ok]
        if len(a) < 12:
            return TTCResult(None, None, dt, int(len(a)), 0.0)
        M, inl = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=1.5,
                                             maxIters=2000, confidence=0.995)
        if M is None:
            return TTCResult(None, None, dt, 0, 0.0)
        inl = inl.reshape(-1).astype(bool)
        s = float(np.hypot(M[0, 0], M[1, 0]))
        n = int(inl.sum())
        quality = float(inl.mean()) * min(1.0, n / 60)
        tau = None
        if s < 0.995 and quality > 0.25 and self.taus:
            # the ground fell away (e.g. flew past a crater rim / plateau removed): restart the window
            last = self.buf[-1]
            self.buf.clear(); self.buf.append(last); self.taus.clear(); self.hazard_avg = None
            return TTCResult(None, s, dt, n, quality)
        if s > 1.0005 and quality > 0.25 and self.taus:
            t_now = self.buf[-1][0]
            prev = float(np.median([tt - (t_now - ti) for ti, tt in self.taus]))
            if dt / (s - 1.0) < 0.4 * prev:
                # the ground jumped (e.g. a crater rim slid under): frames before the jump are a
                # different surface, so restart the look-back window instead of averaging across it
                last = self.buf[-1]
                self.buf.clear(); self.buf.append(last); self.taus.clear(); self.hazard_avg = None
                return TTCResult(None, s, dt, n, quality)
        if s > 1.0005 and quality > 0.25:
            self.taus.append((self.buf[-1][0], dt / (s - 1.0)))
            t_now = self.buf[-1][0]
            # tau shrinks 1 s per s: age-correct older samples before taking the median
            tau = float(np.median([tt - (t_now - ti) for ti, tt in self.taus]))
        hazard, site = self._hazard(a, b, g1.shape, s, M)
        return TTCResult(tau, s, dt, n, quality, hazard, site, b[inl])

    def _hazard(self, a, b, shape, s_global, M):
        """Per-tile expansion -> height above the dominant ground plane (fraction of altitude)."""
        if s_global <= 1.0005:
            return None, None
        G = self.grid
        h, w = shape
        # Focus of expansion of the global similarity: fixed point x = Mx
        A = M[:, :2] - np.eye(2)
        try:
            foe = np.linalg.solve(A, -M[:, 2])
        except np.linalg.LinAlgError:
            return None, None
        r0 = np.linalg.norm(a - foe, axis=1)
        r1 = np.linalg.norm(b - foe, axis=1)
        good = r0 > 8  # radial ratio is unstable near the FoE
        ratio = np.full(len(a), np.nan)
        ratio[good] = r1[good] / r0[good]
        # inverse depth ∝ (s - 1);  Z_tile / Z_ground = (s_g - 1) / (s_tile - 1)
        haz = np.full((G, G), np.nan)
        ci = np.clip((b[:, 1] / h * G).astype(int), 0, G - 1)
        cj = np.clip((b[:, 0] / w * G).astype(int), 0, G - 1)
        for i in range(G):
            for j in range(G):
                m = (ci == i) & (cj == j) & good
                if m.sum() >= 4:
                    st = float(np.percentile(ratio[m], 85))  # a boulder rarely fills a whole tile
                    if st > 1.0:
                        haz[i, j] = 1.0 - (s_global - 1.0) / (st - 1.0)  # >0 = sticks up
        if self.hazard_avg is None or self.hazard_avg.shape != haz.shape:
            self.hazard_avg = haz
        else:  # temporal smoothing that tolerates missing tiles
            both = ~np.isnan(haz) & ~np.isnan(self.hazard_avg)
            self.hazard_avg = np.where(both, 0.5 * self.hazard_avg + 0.5 * haz,
                                       np.where(np.isnan(haz), self.hazard_avg, haz))
        return self.hazard_avg.copy(), self._pick_site(self.hazard_avg)

    @staticmethod
    def _pick_site(haz: np.ndarray):
        """Safest tile = smallest worst-case |height| over its 3x3 neighbourhood, slight bias to centre."""
        G = haz.shape[0]
        best, best_score = None, np.inf
        for i in range(G):
            for j in range(G):
                nb = haz[max(0, i - 1):i + 2, max(0, j - 1):j + 2]
                if np.isnan(haz[i, j]) or np.isnan(nb).sum() > 3:
                    continue
                score = np.nanmax(np.abs(nb)) + 0.01 * np.hypot(i - (G - 1) / 2, j - (G - 1) / 2)
                if score < best_score:
                    best, best_score = (i, j), score
        return best
