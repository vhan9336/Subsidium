"""Headless check: every mission replay through both brains, as fast as the CPU allows.

  python -m so check
"""
from .pipeline import Pipeline
from .sources.sim import SimSource

# The event Subsidium has to raise in each replay. Athena needs none: with the camera as noisy as
# the real footage measured (10%), its 35% bias can't be proven wrong, but the camera only votes
# and doesn't feed the estimate, so the answer still has to stay accurate.
EXPECT = {
    "nominal": set(),
    "hakuto_r_m1": {"terrain_change"},
    "resilience": {"rf_fault"},
    "odysseus_im1": {"rf_dropout"},
    "athena_im2": set(),
}


def run_one(cfg, mm_per_step, sid, seconds=13.0):
    """Run one replay. Returns the last state and a list of (time, event)."""
    pipe = Pipeline(cfg, SimSource(mm_per_step, realtime=False), log_path=None)
    pipe.command(f"scenario:{sid}")
    events = []
    while True:
        st = pipe.tick()
        events += [(round(st["t"], 1), e) for e in st["events"]]
        if st["t"] > seconds or (st["t"] > 2 and not st["descending"]):
            return st, events


def passed(st, events, want) -> bool:
    return want <= {e for _, e in events} and abs(st["score"]["so"]["last"] or 0) < 12


def run_all(cfg, mm_per_step) -> bool:
    ok_all = True
    print(f"{'scenario':14s} {'legacy max/final err':>22s}   {'Subsidium max/final':>26s}   events")
    for sid, want in EXPECT.items():
        st, events = run_one(cfg, mm_per_step, sid)
        sc, ok = st["score"], passed(st, events, want)
        ok_all &= ok
        print(f"{sid:14s} {sc['legacy']['max']:9.0f} / {sc['legacy']['last']:+6.0f} mm   "
              f"{sc['so']['max']:11.0f} / {sc['so']['last']:+6.0f} mm   "
              f"{'OK ' if ok else 'BAD'} {[e for e in events if not e[1].startswith('cam_lock')]}")
    print("PASS" if ok_all else "FAIL")
    return ok_all
