"""The flight loop: source -> camera tau -> faults -> both brains -> state for the UI.

Everything runs on the source's timeline (real time on the rig, virtual time in fast
simulation, recorded time in replay), so results are reproducible.
"""
from __future__ import annotations

import collections
import json
import pathlib
import queue
import time

import cv2
import numpy as np

from .config import ROOT
from .fusion.faults import FaultInjector
from .fusion.legacy import LegacyGate
from .fusion.triplex import TriplexMonitor
from .fusion.types import Inputs
from .scenarios import ScenarioRunner, load_all
from .sources.base import Sample, Source
from .sources.replay import Recorder, ReplaySource
from .vision.ttc import TTCEstimator


class Pipeline:
    def __init__(self, cfg: dict, source: Source, log_path: str | None = "flight_log.jsonl"):
        self.cfg, self.src = cfg, source
        c = cfg["camera"]
        self.ttc = TTCEstimator(lookback_s=c["lookback_s"], grid=c["grid"])
        self.legacy, self.so = LegacyGate(cfg), TriplexMonitor(cfg)
        self.faults = FaultInjector(cfg)
        self.scenarios = load_all()
        self.runner = ScenarioRunner()
        self.cmdq: queue.Queue[str] = queue.Queue()
        self.recorder: Recorder | None = None
        self.steps_hist: collections.deque = collections.deque()
        self.moving_since: float | None = None
        self.last_t: float | None = None
        self.jpeg = b""
        self.log = open(log_path, "a") if log_path else None
        self._reset_score()

    # ---- commands --------------------------------------------------------------------------
    def command(self, name: str):
        """Thread-safe: queued and applied at the start of the next tick."""
        self.cmdq.put(name)

    def start_recording(self, folder: str):
        self.cmdq.put(f"record:{folder}")

    def _apply(self, name: str, t: float, record: bool):
        if record and self.recorder and not name.startswith("record"):
            self.recorder.command(t, name)
        if name.startswith("record:"):
            self.recorder = Recorder(name[7:], {"mm_per_step": self.src.mm_per_step, "h0": self.src.h0,
                                                "source": self.src.kind})
        elif name == "record_stop":
            if self.recorder:
                self.recorder.close()
            self.recorder = None
        elif name.startswith("fault:"):
            self.faults.set(name[6:], t)
        elif name.startswith("scenario:"):
            sid = name[9:]
            if sid == "stop":
                self.runner.stop()
            elif sid in self.scenarios:
                spec = self.scenarios[sid]
                # a mission replay descends over the orbiter image of where that lander really came down
                site = ROOT / spec["site"] if spec.get("site") else None
                self.src.command("texture:" + (str(site) if site and site.exists() else ""))
                if hasattr(self.src, "use"):          # footage + simulator: pick the one this replay can run on
                    self.src.use(spec.get("footage", True))
                self.runner.start(spec, t)
        elif name == "reset":
            self.src.command("reset")
            self.ttc.reset()
            self.legacy.reset()
            self.so.reset()
            self.steps_hist.clear()
            self.moving_since = None
            self._reset_score()
        else:
            self.src.command(name)

    def _reset_score(self):
        self.score = {"legacy": {"max": 0.0, "last": None}, "so": {"max": 0.0, "last": None}}

    # ---- one tick --------------------------------------------------------------------------
    def tick(self) -> dict | None:
        # commands first (stamped with the previous tick's time), so this tick's reading reflects them
        tp = self.last_t
        if isinstance(self.src, ReplaySource) and tp is not None:
            for n in self.src.due_commands(tp):
                self._apply(n, tp, record=False)
        while not self.cmdq.empty():
            self._apply(self.cmdq.get(), tp or 0.0, record=True)
        for n in self.runner.due(tp or 0.0):
            self._apply(n, tp or 0.0, record=False)
        s: Sample | None = self.src.read()
        if s is None:
            return None
        t = s.t
        if tp is not None and t < tp:                 # replay looped: start clean
            again = self.runner.spec["id"] if self.runner.spec and self.src.kind == "video" else None
            self._apply("reset", t, record=False)
            self.runner.stop()
            self.faults.clear()
            if again:                                 # footage loops, so the mission replay runs again with it
                self._apply(f"scenario:{again}", t, record=False)
        self.last_t = t
        if self.recorder:
            self.recorder.frame(s)

        # navigation: dead reckoning from the stepper ("IMU"), descent rate from its slope
        mmps = self.src.mm_per_step
        h0 = s.h0 if s.h0 is not None else (s.rf_raw or 0.0)
        h_nav = h0 - s.steps * mmps
        self.steps_hist.append((t, s.steps))
        while t - self.steps_hist[0][0] > 0.6:
            self.steps_hist.popleft()
        (ta, sa), (tb, sb) = self.steps_hist[0], self.steps_hist[-1]
        v = (sb - sa) * mmps / (tb - ta) if tb - ta > 0.2 else 0.0

        # camera: only meaningful once the whole look-back window is in steady descent
        self.moving_since = (self.moving_since or t) if v > 1.0 else None
        steady = self.moving_since is not None and t - self.moving_since > self.ttc.lookback_s + 0.4
        res = self.ttc.update(t, s.frame)
        gain = getattr(self.src, "tau_gain", 1.0)     # tilted-camera calibration (real footage)
        tau_raw = None if res.tau is None else res.tau * gain
        tau, q = self.faults.cam(tau_raw if steady else None, res.quality if steady else 0.0)
        rf = self.faults.rf(t, s.rf_raw)

        x = Inputs(t, h_nav, v, rf, tau, q)
        lb, sb_ = self.legacy.step(x), self.so.step(x)
        truth = s.true_alt if s.true_alt is not None else s.rf_raw
        for key, b in (("legacy", lb), ("so", sb_)):
            if truth is not None and b.est is not None and v > 1.0:
                e = b.est - truth
                self.score[key]["last"] = round(e, 1)
                self.score[key]["max"] = round(max(self.score[key]["max"], abs(e)), 1)

        cam_h = sb_.detail["witness"].get("cam", {}).get("h")
        state = {
            "t": t, "kind": self.src.kind, "recording": self.recorder is not None,
            "truth": truth, "nav": sb_.detail["witness"]["nav"]["h"], "nav_raw": h_nav,
            "rf": rf, "rf_raw": s.rf_raw, "cam": cam_h, "v": v, "tau": tau, "q": round(q, 2),
            "tau_raw": tau_raw, "q_raw": round(res.quality, 2),
            "clip": self.src.info() if hasattr(self.src, "info") else None,
            "h0": h0, "descending": s.descending,
            "legacy": {"est": lb.est, "status": lb.status, "excluded": lb.excluded},
            "so": {"est": sb_.est, "sigma": sb_.sigma, "status": sb_.status, "excluded": sb_.excluded,
                   **{k: sb_.detail[k] for k in ("pairs", "gate", "cam_abstain", "witness")}},
            "hazard": None if res.hazard is None else np.nan_to_num(res.hazard, nan=-1).round(3).tolist(),
            "site": res.site, "faults": self.faults.active, "scenario": self.runner.state(t),
            "events": lb.events + sb_.events, "score": self.score,
        }
        if self.log:
            self.log.write(json.dumps({k: v for k, v in state.items() if k != "hazard"}) + "\n")
        self.jpeg = self._overlay(s.frame, res)
        return state

    def _overlay(self, frame, res) -> bytes:
        img = frame.copy()
        h, w = img.shape[:2]
        # the hazard map assumes a camera looking straight down; a source can switch it off
        if res.hazard is not None and getattr(self.src, "show_hazard", True):
            G = res.hazard.shape[0]
            tint = img.copy()
            for i in range(G):
                for j in range(G):
                    hz = res.hazard[i, j]
                    if np.isnan(hz):
                        continue
                    a = float(np.clip(abs(hz) / 0.08, 0, 1))   # 8% of altitude = full red; tune on the rig
                    cv2.rectangle(tint, (j * w // G, i * h // G), ((j + 1) * w // G, (i + 1) * h // G),
                                  (40, int(190 * (1 - a)), int(255 * a)), -1)
            a = float(self.cfg["camera"].get("hazard_tint", 0.25))
            img = cv2.addWeighted(tint, a, img, 1 - a, 0)
            if res.site is not None:
                i, j = res.site
                cx, cy = int((j + 0.5) * w / G), int((i + 0.5) * h / G)
                cv2.circle(img, (cx, cy), 24, (255, 255, 255), 2)
                cv2.line(img, (cx - 34, cy), (cx + 34, cy), (255, 255, 255), 1)
                cv2.line(img, (cx, cy - 34), (cx, cy + 34), (255, 255, 255), 1)
        if res.points is not None:
            k = w / self.ttc.width
            for p in res.points[::2]:
                cv2.circle(img, (int(p[0] * k), int(p[1] * k)), 2, (255, 210, 120), -1)
        quality = int(self.cfg["camera"].get("jpeg_quality", 75))
        return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])[1].tobytes()
