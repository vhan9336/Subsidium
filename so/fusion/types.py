from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Inputs:
    """One tick of everything the flight software sees."""
    t: float
    h_nav: float             # inertial / dead-reckoned altitude (mm). Rig: stepper count. Lander: IMU.
    v: float                 # descent rate (mm/s, + = down). Rig: stepper rate. Lander: IMU / Doppler radar.
    rf: float | None         # rangefinder altitude (mm); None = no echo
    tau: float | None        # camera time-to-contact (s); None = no lock
    cam_q: float = 0.0       # camera lock quality 0..1


@dataclass
class Belief:
    est: float | None
    sigma: float | None
    status: str
    excluded: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)
