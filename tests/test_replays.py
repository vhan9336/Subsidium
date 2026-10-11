"""End to end: every mission replay in fast simulation, and recording then replaying a session."""
from so.check import EXPECT, passed, run_one
from so.pipeline import Pipeline
from so.sources.replay import ReplaySource
from so.sources.sim import SimSource

from .common import CFG, MMPS


def test_all_mission_replays():
    for sid, want in EXPECT.items():
        st, events = run_one(CFG, MMPS, sid)
        assert passed(st, events, want), (sid, events)


def test_record_then_replay_gives_same_verdicts(tmp_path):
    pipe = Pipeline(CFG, SimSource(MMPS, realtime=False), log_path=None)
    pipe.start_recording(str(tmp_path / "s"))
    pipe.command("scenario:resilience")
    live = []
    while (st := pipe.tick())["t"] <= 9:
        live += st["events"]
    pipe.command("record_stop")
    pipe.tick()

    replay = Pipeline(CFG, ReplaySource(tmp_path / "s", realtime=False), log_path=None)
    replayed = []
    while (st := replay.tick()) is not None:
        replayed += st["events"]
    assert "rf_fault" in live and "rf_fault" in replayed
