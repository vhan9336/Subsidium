"""End-to-end: every mission replay in fast simulation, plus record -> replay determinism."""
import math

from so.check import EXPECT, run_one
from so.config import load
from so.pipeline import Pipeline
from so.sources.replay import ReplaySource
from so.sources.sim import SimSource

CFG = load()
MMPS = math.pi * CFG["rig"]["spool_mm"] / CFG["rig"]["steps_per_rev"]


def test_all_mission_replays():
    for sid, want in EXPECT.items():
        st, events = run_one(CFG, MMPS, sid)
        assert want <= {e for _, e in events}, (sid, events)
        assert abs(st["score"]["so"]["last"]) < 12, sid


def test_record_then_replay_gives_same_verdicts(tmp_path):
    pipe = Pipeline(CFG, SimSource(MMPS, realtime=False), log_path=None)
    pipe.start_recording(str(tmp_path / "s"))
    pipe.command("scenario:resilience")
    live = []
    while True:
        st = pipe.tick()
        live += st["events"]
        if st["t"] > 9:
            break
    pipe.command("record_stop")
    pipe.tick()
    rep = Pipeline(CFG, ReplaySource(tmp_path / "s", realtime=False), log_path=None)
    replayed = []
    while (st := rep.tick()) is not None:
        replayed += st["events"]
    assert "rf_fault" in live and "rf_fault" in replayed
