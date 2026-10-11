"""Real footage through the whole pipeline. Skipped when the clip has not been downloaded
(python tools/fetch_data.py blue_ghost)."""
import math

import pytest

from so.config import ROOT, load
from so.pipeline import Pipeline

CLIP = ROOT / "footage" / "blue_ghost_m1_landing_scalpss.mp4"
pytestmark = pytest.mark.skipif(not CLIP.exists(), reason="footage not downloaded")


def run(fault: tuple[str, float] | None = None):
    from so.sources.video import VideoSource
    cfg = load()
    mmps = math.pi * cfg["rig"]["spool_mm"] / cfg["rig"]["steps_per_rev"]
    pipe = Pipeline(cfg, VideoSource(mmps, "blue_ghost", realtime=False), log_path=None)
    states, last = [], -1.0
    while True:
        st = pipe.tick()
        if st["t"] < last:               # the clip looped
            return states
        last = st["t"]
        if fault and st["t"] >= fault[1]:
            pipe.command("fault:" + fault[0])
            fault = None
        states.append({**st, "score": {k: dict(v) for k, v in st["score"].items()}})


def test_camera_locks_on_real_footage_and_all_three_agree():
    states = run()
    locked = [s for s in states if s["cam"] is not None]
    assert len(locked) > 0.5 * len([s for s in states if s["descending"]])
    assert states[-1]["score"]["so"]["max"] < 15
    assert not any(s["so"]["excluded"] for s in states)


def test_frozen_rangefinder_is_outvoted_on_real_footage():
    states = run(("rf_freeze", 3.0))
    assert any("rf_fault" in s["events"] for s in states)
    end = states[-1]["score"]
    assert abs(end["so"]["last"]) < 15 < abs(end["legacy"]["last"])


def hybrid(sid: str, seconds: float = 12.0):
    from so.sources.hybrid import HybridSource
    from so.sources.sim import SimSource
    from so.sources.video import VideoSource
    cfg = load()
    mmps = math.pi * cfg["rig"]["spool_mm"] / cfg["rig"]["steps_per_rev"]
    src = HybridSource(VideoSource(mmps, "blue_ghost", realtime=False), SimSource(mmps, realtime=False))
    pipe = Pipeline(cfg, src, log_path=None)
    pipe.command(f"scenario:{sid}")
    states = []
    while not states or states[-1]["scenario"]["t"] < seconds:
        states.append(pipe.tick())
    return states


def test_replay_flies_on_real_footage_when_it_can():
    states = hybrid("athena_im2")
    assert {s["kind"] for s in states} == {"video"}
    assert any("cam_fault" in s["events"] for s in states)
    assert states[-1]["so"]["excluded"] == ["cam"]


def test_replay_that_needs_a_moving_ground_flies_on_the_simulator():
    states = hybrid("hakuto_r_m1")
    assert {s["kind"] for s in states} == {"sim"}
    assert any("terrain_change" in s["events"] for s in states)


def test_replay_runs_again_when_the_footage_loops():
    from so.sources.hybrid import HybridSource
    from so.sources.sim import SimSource
    from so.sources.video import VideoSource
    cfg = load()
    mmps = math.pi * cfg["rig"]["spool_mm"] / cfg["rig"]["steps_per_rev"]
    src = HybridSource(VideoSource(mmps, "blue_ghost", realtime=False), SimSource(mmps, realtime=False))
    pipe = Pipeline(cfg, src, log_path=None)
    pipe.command("scenario:odysseus_im1")
    st, last = pipe.tick(), -1.0
    while st["t"] >= last:               # until the clip loops
        last, st = st["t"], pipe.tick()
    while st["t"] < 2.0:
        st = pipe.tick()
    assert st["scenario"]["id"] == "odysseus_im1"
    assert st["faults"] == ["rf_drop"]
