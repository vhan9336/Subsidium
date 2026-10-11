from dataclasses import dataclass, field


@dataclass
class Inputs:
    """Everything the flight software sees on one tick."""
    t: float
    h_nav: float             # dead-reckoned altitude, mm (the rig's stepper count; a lander's IMU)
    v: float                 # descent speed, mm/s, positive = down
    rf: float | None         # rangefinder altitude, mm. None = no echo
    tau: float | None        # camera time to contact, s. None = no lock
    cam_q: float = 0.0       # how good the camera lock is, 0 to 1


@dataclass
class Belief:
    """What one brain thinks the altitude is, and why."""
    est: float | None
    sigma: float | None
    status: str
    excluded: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)
