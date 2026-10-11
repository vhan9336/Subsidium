"""Mission replays: timed command scripts loaded from scenarios/*.toml.

On the simulator every step runs by itself. On the real rig, the physical steps
(terrain_up, terrain_down) show up as a cue for the operator to carry out by hand.
"""
import pathlib
import tomllib

from .config import ROOT

# what the dashboard gets to know about the running scenario
SHOWN = ("id", "name", "mission", "summary", "expect", "setup", "site", "site_note", "broadcast_note")


def load_all() -> dict[str, dict]:
    out = {}
    for p in sorted((ROOT / "scenarios").glob("*.toml")):
        with open(p, "rb") as f:
            spec = tomllib.load(f)
        spec["steps"] = sorted(spec["steps"], key=lambda s: s["at"])
        out[spec["id"]] = spec
    return out


class ScenarioRunner:
    def __init__(self):
        self.spec = None
        self.t0 = 0.0
        self.i = 0               # next step to run
        self.cue = None
        self.broadcast = None

    def start(self, spec: dict, t: float):
        self.spec, self.t0, self.i, self.cue = spec, t, 0, None
        # the mission's own broadcast, if it has been downloaded (tools/fetch_data.py broadcasts)
        b = spec.get("broadcast")
        self.broadcast = b if b and (ROOT / b).exists() else None

    def stop(self):
        self.spec = self.cue = None

    def due(self, t: float) -> list[str]:
        """Commands whose time has come."""
        out = []
        steps = self.spec["steps"] if self.spec else []
        while self.i < len(steps) and t - self.t0 >= steps[self.i]["at"]:
            out += steps[self.i].get("do", [])
            self.cue = steps[self.i].get("cue", self.cue)
            self.i += 1
        return out

    def state(self, t: float) -> dict | None:
        if not self.spec:
            return None
        s = self.spec
        return {**{k: s.get(k) for k in SHOWN}, "cue": self.cue, "broadcast": self.broadcast,
                "broadcast_at": s.get("broadcast_at", 0), "t": round(t - self.t0, 1),
                "done": self.i >= len(s["steps"])}
