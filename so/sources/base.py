from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass
class Sample:
    """One synchronized tick: a camera frame plus the raw rig readings."""
    t: float                      # seconds (monotonic; replays keep the recorded timeline)
    frame: np.ndarray             # BGR image
    rf_raw: float | None          # rangefinder reading before any injected fault (mm)
    steps: int                    # stepper position (navigation / "IMU")
    true_alt: float | None        # simulator ground truth; None on hardware
    descending: bool
    h0: float | None = None       # navigation anchor at this moment (mm)

    def meta(self) -> dict:
        d = asdict(self)
        d.pop("frame")
        return d


class Source:
    kind = "base"
    h0: float | None = None       # navigation anchor: sled altitude when steps == 0
    mm_per_step: float = 0.03

    def read(self) -> Sample | None:
        raise NotImplementedError

    def command(self, name: str) -> None:
        pass

    def close(self) -> None:
        pass
