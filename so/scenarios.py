"""Mission replays: timed command scripts loaded from scenarios/*.toml.

On the simulator every step runs automatically. On the real rig, physical steps
(terrain_up / terrain_down) are shown to the operator as a cue instead.
"""
from __future__ import annotations

import pathlib
import tomllib

from .config import ROOT

PHYSICAL = {"terrain_up", "terrain_down"}


def load_all(folder: str | pathlib.Path | None = None) -> dict[str, dict]:
    out = {}
    for p in sorted(pathlib.Path(folder or ROOT / "scenarios").glob("*.toml")):
        with open(p, "rb") as f:
            spec = tomllib.load(f)
        spec["steps"] = sorted(spec["steps"], key=lambda s: s["at"])
        out[spec["id"]] = spec
    return out


class ScenarioRunner:
    def __init__(self):
        self.spec: dict | None = None
        self.t0 = 0.0
        self.i = 0
        self.cue: str | None = None

    def start(self, spec: dict, t: float):
        self.spec, self.t0, self.i, self.cue = spec, t, 0, None
        # the mission's real landing broadcast, if it has been downloaded (tools/fetch_data.py broadcasts)
        b = spec.get("broadcast")
        self.broadcast = b if b and (ROOT / b).exists() else None

    def stop(self):
        self.spec, self.cue = None, None

    def due(self, t: float) -> list[str]:
        """Commands whose time has come."""
        if not self.spec:
            return []
        out = []
        steps = self.spec["steps"]
        while self.i < len(steps) and t - self.t0 >= steps[self.i]["at"]:
            step = steps[self.i]
            out += step.get("do", [])
            if step.get("cue"):
                self.cue = step["cue"]
            self.i += 1
        return out

    def state(self, t: float) -> dict | None:
        if not self.spec:
            return None
        s = self.spec
        return {"id": s["id"], "name": s["name"], "mission": s.get("mission"), "summary": s.get("summary"),
                "expect": s.get("expect"), "setup": s.get("setup"), "cue": self.cue,
                "site": s.get("site"), "site_note": s.get("site_note"),
                "broadcast": self.broadcast, "broadcast_at": s.get("broadcast_at", 0),
                "broadcast_note": s.get("broadcast_note"),
                "t": round(t - self.t0, 1), "done": self.i >= len(s["steps"])}
