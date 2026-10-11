"""Synthetic rig + camera: build and test everything with no hardware.

Ground is a textured plane (procedural, or any image such as an LRO NAC frame via --texture);
boulders are textured discs that stick up. `terrain_up` / `terrain_down` put a 60 mm plateau
under the lander or take it away (the rig's slide-in / slide-out box).
"""
from __future__ import annotations

import time

import cv2
import numpy as np

from .base import Sample, Source


def make_texture(size: int = 1400, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.zeros((size, size), np.float32)
    for k, amp in ((3, 0.5), (9, 0.3), (25, 0.2)):
        n = rng.random((size // k + 1, size // k + 1)).astype(np.float32)
        t += amp * cv2.resize(n, (size, size), interpolation=cv2.INTER_CUBIC)
    for _ in range(140):  # craters
        c = rng.integers(0, size, 2)
        r = int(rng.integers(6, 50))
        cv2.circle(t, (int(c[0]), int(c[1])), r, float(rng.random() * 0.6), 2)
    t = cv2.normalize(t, None, 0, 255, cv2.NORM_MINMAX)
    return t.astype(np.uint8)


def load_texture(path: str, size: int = 1400) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(path)
    h, w = img.shape
    s = min(h, w)
    img = img[(h - s) // 2:(h + s) // 2, (w - s) // 2:(w + s) // 2]
    return cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)


class SimScene:
    """Renders what a down-looking camera sees at distance Z (mm) above the ground plane."""

    def __init__(self, f_px: float = 260.0, out=(320, 240), mm_per_texel: float = 0.5, seed: int = 0,
                 boulders=((0.25, -0.15, 22.0, 30.0), (-0.35, 0.25, 18.0, 22.0)), texture: str | None = None):
        self.tex = load_texture(texture) if texture else make_texture(seed=seed)
        self.f, self.out, self.mmpt = f_px, out, mm_per_texel
        self.boulders = boulders     # (x, y as fraction of 200 mm from centre, radius mm, height mm)
        self.rng = np.random.default_rng(seed + 1)

    def _layer(self, Z: float) -> np.ndarray:
        k = self.f * self.mmpt / Z
        cx, cy = self.tex.shape[1] / 2, self.tex.shape[0] / 2
        M = np.float32([[k, 0, self.out[0] / 2 - k * cx], [0, k, self.out[1] / 2 - k * cy]])
        return cv2.warpAffine(self.tex, M, self.out, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    def render(self, Z: float, noise: float = 2.0) -> np.ndarray:
        img = self._layer(Z).astype(np.float32)
        for bx, by, r_mm, h_mm in self.boulders:
            Zb = max(Z - h_mm, 5.0)
            top = self._layer(Zb).astype(np.float32)
            u = self.out[0] / 2 + self.f * bx * 200 / Zb
            v = self.out[1] / 2 + self.f * by * 200 / Zb
            mask = np.zeros(self.out[::-1], np.float32)
            cv2.circle(mask, (int(u), int(v)), int(self.f * r_mm / Zb), 1.0, -1)
            img = img * (1 - mask) + (top * 0.8 + 40) * mask
        img += self.rng.normal(0, noise, img.shape)
        return cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


class SimSource(Source):
    kind = "sim"

    def __init__(self, mm_per_step: float, h0: float = 450.0, speed: float = 30.0, floor: float = 70.0,
                 plateau_mm: float = 60.0, texture: str | None = None, realtime: bool = True,
                 fps: float = 30.0, seed: int = 0, render: tuple[int, int] = (320, 240)):
        # `render` only changes image size (same field of view): larger is sharper on the dashboard
        self.scene = SimScene(f_px=260.0 * render[0] / 320, out=render, texture=texture, seed=seed)
        self._default_tex = self.scene.tex
        self.mm_per_step, self.h0, self.speed, self.floor = mm_per_step, h0, speed, floor
        self.plateau, self.realtime, self.fps = plateau_mm, realtime, fps
        self.rng = np.random.default_rng(seed + 7)
        self.t = 0.0 if not realtime else time.monotonic()
        self.ground = 0.0
        self._reset_rig()

    def _reset_rig(self):
        self.sled, self.moving = self.h0, 0          # terrain stays as the operator left it
        self.anchor = self.h0 - self.ground          # like calibrating on the rangefinder at reset

    def command(self, name: str):
        if name == "descend":
            self.moving = 1
        elif name == "up":
            self.moving = -1
        elif name == "stop":
            self.moving = 0
        elif name == "reset":
            self._reset_rig()
        elif name == "terrain_up":
            self.ground = self.plateau
        elif name == "terrain_down":
            self.ground = 0.0
        elif name.startswith("texture:"):            # fly over another ground image ("" = the default)
            self.scene.tex = load_texture(name[8:]) if name[8:] else self._default_tex

    def read(self) -> Sample:
        dt = 1.0 / self.fps
        if self.realtime:
            time.sleep(max(0.0, self.t + dt - time.monotonic()))
            now = time.monotonic()
            dt, self.t = now - self.t, now
        else:
            self.t += dt
        if self.moving == 1 and self.sled - self.ground > self.floor:
            self.sled -= self.speed * dt
        elif self.moving == -1 and self.sled < self.h0:
            self.sled = min(self.h0, self.sled + self.speed * dt)
        if self.sled - self.ground <= self.floor:
            self.moving = 0 if self.moving == 1 else self.moving
        steps = int(round((self.h0 - self.sled) / self.mm_per_step))
        alt = self.sled - self.ground
        return Sample(self.t, self.scene.render(max(alt, 20.0)), float(alt + self.rng.normal(0, 1.5)),
                      steps, float(alt), self.moving == 1, self.anchor)
