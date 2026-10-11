from dataclasses import asdict, dataclass

import numpy as np


@dataclass
class Sample:
    """One tick from a source: a camera frame plus the raw rig readings."""
    t: float                      # seconds. Replays keep their recorded timeline
    frame: np.ndarray             # BGR image
    rf_raw: float | None          # rangefinder reading before any injected fault, mm
    steps: int                    # stepper position, which stands in for the IMU
    true_alt: float | None        # the simulator knows the real altitude; hardware doesn't
    descending: bool
    h0: float | None = None       # altitude when the step counter was zeroed, mm
    alt_frame: np.ndarray | None = None    # a second picture to show beside the camera, like a mission broadcast

    def meta(self) -> dict:
        d = asdict(self)
        d.pop("frame")
        d.pop("alt_frame")
        return d


class Source:
    """Where samples come from: the simulator, the real rig, a recording or real footage."""
    kind = "base"
    h0: float | None = None
    mm_per_step: float = 0.03
    # Footage can change how the pipeline treats the camera. Every other source leaves these alone.
    tau_gain = 1.0                # multiplies time to contact (a tilted camera reads long)
    show_hazard = True            # the hazard grid assumes a camera looking straight down
    reconstructed_cam = False     # no descent camera in the video, so the camera reading is faked
    has_rig = False               # whether the live rig can be switched to (see HybridSource)

    def read(self) -> Sample | None:
        raise NotImplementedError

    def command(self, name: str) -> None:
        pass

    def info(self) -> dict | None:
        return None

    def resync(self) -> None:
        """Called after a pause so the source's clock doesn't count the time spent paused."""

    def close(self) -> None:
        pass
