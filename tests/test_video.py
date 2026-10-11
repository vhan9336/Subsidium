"""Real footage through the whole pipeline. Skipped unless the clip has been downloaded
(python tools/fetch_data.py blue_ghost)."""
import pytest

from so.config import ROOT
from so.pipeline import Pipeline
from so.sources.hybrid import HybridSource
from so.sources.sim import SimSource
from so.sources.video import VideoSource

from .common import CFG, MMPS

pytestmark = pytest.mark.skipif(not (ROOT / "footage" / "blue_ghost_m1_landing_scalpss.mp4").exists(),
                                reason="footage not downloaded")


def video_pipeline() -> Pipeline:
    return Pipeline(CFG, VideoSource(MMPS, "blue_ghost", realtime=False), log_path=None)


def hybrid_pipeline() -> Pipeline:
    src = HybridSource(VideoSource(MMPS, "blue_ghost", realtime=False), SimSource(MMPS, realtime=False))
    return Pipeline(CFG, src, log_path=None)


def run_clip(fault: tuple[str, float] | None = None) -> list[dict]:
    """Play the clip once, optionally breaking a sensor at a given time."""
    pipe, states, last = video_pipeline(), [], -1.0
    while (st := pipe.tick())["t"] >= last:        # time goes backwards when the clip loops
        last = st["t"]
        if fault and st["t"] >= fault[1]:
            pipe.command("fault:" + fault[0])
            fault = None
        states.append({**st, "score": {k: dict(v) for k, v in st["score"].items()}})
    return states


def run_replay(sid: str, seconds: float = 12.0, **override) -> list[dict]:
    """Run a mission replay on the hybrid source, optionally overriding fields of its scenario."""
    pipe = hybrid_pipeline()
    pipe.scenarios[sid] = {**pipe.scenarios[sid], **override}
    pipe.command(f"scenario:{sid}")
    states = []
    while not states or states[-1]["scenario"]["t"] < seconds:
        states.append(pipe.tick())
    return states


def test_camera_locks_on_real_footage_and_all_three_agree():
    states = run_clip()
    locked = [s for s in states if s["cam"] is not None]
    assert len(locked) > 0.5 * len([s for s in states if s["descending"]])
    assert states[-1]["score"]["so"]["max"] < 15
    assert not any(s["so"]["excluded"] for s in states)


def test_frozen_rangefinder_is_outvoted_on_real_footage():
    states = run_clip(("rf_freeze", 3.0))
    assert any("rf_fault" in s["events"] for s in states)
    end = states[-1]["score"]
    assert abs(end["so"]["last"]) < 15 < abs(end["legacy"]["last"])


def test_replay_flies_on_real_footage_when_it_can():
    states = run_replay("athena_im2")
    assert {s["kind"] for s in states} == {"video"}
    assert any("cam_fault" in s["events"] for s in states)
    assert states[-1]["so"]["excluded"] == ["cam"]


def test_replay_marked_not_for_footage_flies_on_the_simulator():
    states = run_replay("hakuto_r_m1", footage=False)
    assert {s["kind"] for s in states} == {"sim"}
    assert any("terrain_change" in s["events"] for s in states)


def test_replay_runs_again_when_the_footage_loops():
    pipe = hybrid_pipeline()
    pipe.command("scenario:odysseus_im1")
    st, last = pipe.tick(), -1.0
    while st["t"] >= last:                         # until the clip loops
        last, st = st["t"], pipe.tick()
    while st["t"] < 2.0:
        st = pipe.tick()
    assert st["scenario"]["id"] == "odysseus_im1"
    assert st["faults"] == ["rf_drop"]


def test_lagging_rangefinder_does_not_replay_readings_from_before_a_reset():
    # Found on the broadcast replays: after HAKUTO-R (about 2500 mm) a lagging rangefinder in
    # the next replay briefly reported HAKUTO-R's altitudes.
    pipe = Pipeline(CFG, SimSource(MMPS, realtime=False), log_path=None)
    pipe.faults.hist.extend((t / 30, 5000.0) for t in range(60))    # readings from an earlier, much higher flight
    for name in ("reset", "descend", "fault:rf_lag"):
        pipe.command(name)
    assert all(st["rf"] < 1000 for st in (pipe.tick() for _ in range(200)))


def test_hakuto_r_on_its_own_broadcast_telemetry():
    states = run_replay("hakuto_r_m1", seconds=30.0)
    end = states[-1]
    assert end["clip"]["id"] == "hakuto_r"
    assert any("terrain_change" in s["events"] for s in states)
    assert abs(end["so"]["est"] - end["truth"]) < 25            # Subsidium is back on the true altitude
    assert end["truth"] - end["legacy"]["est"] > 2400           # the legacy gate is 5 km (2500 mm) low
