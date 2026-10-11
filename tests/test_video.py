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


def hybrid(sid: str, seconds: float = 12.0, **override):
    from so.sources.hybrid import HybridSource
    from so.sources.sim import SimSource
    from so.sources.video import VideoSource
    cfg = load()
    mmps = math.pi * cfg["rig"]["spool_mm"] / cfg["rig"]["steps_per_rev"]
    src = HybridSource(VideoSource(mmps, "blue_ghost", realtime=False), SimSource(mmps, realtime=False))
    pipe = Pipeline(cfg, src, log_path=None)
    pipe.scenarios[sid] = {**pipe.scenarios[sid], **override}
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


def test_replay_marked_not_for_footage_flies_on_the_simulator():
    states = hybrid("hakuto_r_m1", footage=False)
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


def test_lagging_rangefinder_does_not_replay_readings_from_before_a_reset():
    # found on the broadcast replays: after HAKUTO-R (about 2500 mm) a lagging rangefinder in the
    # next replay briefly reported HAKUTO-R's altitudes
    from so.sources.sim import SimSource
    cfg = load()
    mmps = math.pi * cfg["rig"]["spool_mm"] / cfg["rig"]["steps_per_rev"]
    pipe = Pipeline(cfg, SimSource(mmps, realtime=False), log_path=None)
    pipe.faults.hist.extend((t / 30, 5000.0) for t in range(60))    # readings from an earlier, much higher flight
    for name in ("reset", "descend", "fault:rf_lag"):
        pipe.command(name)
    assert all(st["rf"] < 1000 for st in (pipe.tick() for _ in range(200)))


def test_hakuto_r_on_its_own_broadcast_telemetry():
    states = hybrid("hakuto_r_m1", seconds=30.0)
    assert states[-1]["clip"]["id"] == "hakuto_r"
    assert any("terrain_change" in s["events"] for s in states)
    end = states[-1]
    assert abs(end["so"]["est"] - end["truth"]) < 25            # Second Opinion is back on the true altitude
    assert end["truth"] - end["legacy"]["est"] > 2400           # the legacy gate is 5 km (2500 mm) low
