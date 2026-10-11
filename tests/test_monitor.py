"""The voting monitor on hand-built sensor streams. No camera involved."""
import numpy as np

from so.fusion.legacy import LegacyGate
from so.fusion.triplex import TriplexMonitor
from so.fusion.types import Inputs

from .common import CFG

V = 30.0  # descent speed, mm/s


def stream(n=300, dt=1 / 30, h0=450.0, rf_fn=None, cam_fn=None, nav_fn=None, seed=0):
    rng = np.random.default_rng(seed)
    for k in range(n):
        t = k * dt
        h = h0 - V * t
        nav = nav_fn(t, h) if nav_fn else h
        rf = rf_fn(t, h) if rf_fn else h + rng.normal(0, 1.5)
        cam_h = cam_fn(t, h) if cam_fn else h * (1 + rng.normal(0, 0.01))
        yield t, h, Inputs(t, nav, V, rf, None if cam_h is None else cam_h / V, 0.9)


def run(**kw):
    m, events = TriplexMonitor(CFG), []
    for t, h, x in stream(**kw):
        b = m.step(x)
        events += b.events
    return b, h, events


def test_nominal():
    b, h, ev = run()
    assert b.status.startswith("NOMINAL") and abs(b.est - h) < 5 and "unresolved" not in ev


def test_terrain_change_reanchors_inertial():
    # ground drops 60 mm at t=3 s (HAKUTO-R direction): rangefinder and camera jump up, inertial doesn't
    up = lambda t, h: h + (60 if t > 3 else 0)
    b, h, ev = run(rf_fn=up, cam_fn=up)
    assert "terrain_change" in ev and abs(b.est - (h + 60)) < 6


def test_rangefinder_fault_isolated():
    lagged = lambda t, h: h + (V * min(2.5, (t - 3) * 0.6) if t > 3 else 0)
    b, h, ev = run(rf_fn=lagged)
    assert "rf_fault" in ev and "rf" in b.excluded and abs(b.est - h) < 6


def test_camera_fault_isolated():
    biased = lambda t, h: h * (1.35 if t > 3 else 1.0)
    b, h, ev = run(cam_fn=biased)
    assert "cam_fault" in ev and "cam" in b.excluded and abs(b.est - h) < 6


def test_camera_abstains_cannot_isolate():
    # camera gone, then rangefinder jumps: detectable, not isolatable -> fail-safe (closest ground)
    b, h, ev = run(cam_fn=lambda t, h: None, rf_fn=lambda t, h: h + (60 if t > 3 else 0))
    assert "unresolved" in ev and b.est <= h + 1


def test_legacy_rejects_true_jump():
    m = LegacyGate(CFG)
    for t, h, x in stream(rf_fn=lambda t, h: h + (60 if t > 3 else 0)):
        b = m.step(x)
    assert b.status == "RF DECLARED FAILED" and b.est < h + 60 - 50   # believes it is ~60 mm lower


def test_biased_camera_does_not_pull_the_estimate_before_it_is_excluded():
    # the camera reads 35% high from t = 3 s. Until the vote throws it out, the answer should stay put
    biased = lambda t, h: h * (1.35 if t > 3 else 1.0)
    m, worst = TriplexMonitor(CFG), 0.0
    for t, h, x in stream(cam_fn=biased):
        b = m.step(x)
        worst = max(worst, abs(b.est - h))
    assert worst < 8
