"""Headless regression check: every mission replay through both brains in fast simulation.

  python -m so check
"""
from __future__ import annotations

from .pipeline import Pipeline
from .sources.sim import SimSource

# what Subsidium must say for each replay
EXPECT = {
    "nominal": set(),
    "hakuto_r_m1": {"terrain_change"},
    "resilience": {"rf_fault"},
    "odysseus_im1": {"rf_dropout"},
    "athena_im2": {"cam_fault"},
}


def run_one(cfg, mmps, sid, seconds=13.0):
    pipe = Pipeline(cfg, SimSource(mmps, realtime=False), log_path=None)
    pipe.command(f"scenario:{sid}")
    events, st = [], None
    while True:
        st = pipe.tick()
        events += [(round(st["t"], 1), e) for e in st["events"]]
        if st["t"] > seconds or (st["t"] > 2 and not st["descending"]):
            break
    return st, events


def run_all(cfg, mmps) -> bool:
    ok_all = True
    print(f"{'scenario':14s} {'legacy max/final err':>22s}   {'Subsidium max/final':>26s}   events")
    for sid, want in EXPECT.items():
        st, events = run_one(cfg, mmps, sid)
        sc = st["score"]
        names = {e for _, e in events}
        ok = want <= names and abs(sc["so"]["last"] or 0) < 12
        ok_all &= ok
        print(f"{sid:14s} {sc['legacy']['max']:9.0f} / {sc['legacy']['last']:+6.0f} mm   "
              f"{sc['so']['max']:11.0f} / {sc['so']['last']:+6.0f} mm   "
              f"{'OK ' if ok else 'BAD'} {[e for e in events if not e[1].startswith('cam_lock')]}")
    print("PASS" if ok_all else "FAIL")
    return ok_all
