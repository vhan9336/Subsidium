"""A fake rig and camera, so everything can be built and tested with no hardware.

The ground is a textured plane (made up, or any image like an LRO photo). Boulders are
textured discs that stick up off it. terrain_up / terrain_down put a 60 mm plateau under the
lander or pull it out, like the box that slides in and out on the real rig.
"""
import time

import cv2
import numpy as np

from .base import Sample, Source


def make_texture(size: int = 1400, seed: int = 0) -> np.ndarray:
    """Blobby noise at three scales, with craters drawn on top."""
    rng = np.random.default_rng(seed)
    t = np.zeros((size, size), np.float32)
    for k, amp in ((3, 0.5), (9, 0.3), (25, 0.2)):
        noise = rng.random((size // k + 1, size // k + 1)).astype(np.float32)
        t += amp * cv2.resize(noise, (size, size), interpolation=cv2.INTER_CUBIC)
    for _ in range(140):
        cx, cy = rng.integers(0, size, 2)
        cv2.circle(t, (int(cx), int(cy)), int(rng.integers(6, 50)), float(rng.random() * 0.6), 2)
    return cv2.normalize(t, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)


def load_texture(path: str, size: int = 1400) -> np.ndarray:
    """Centre-crop a photo to a square and shrink it to the texture size."""
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(path)
    h, w = img.shape
    s = min(h, w)
    img = img[(h - s) // 2:(h + s) // 2, (w - s) // 2:(w + s) // 2]
    return cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)


class SimScene:
    """Draws what a downward camera sees from Z mm above the ground."""

    def __init__(self, f_px: float = 260.0, out=(320, 240), mm_per_texel: float = 0.5, seed: int = 0,
                 boulders=((0.25, -0.15, 22.0, 30.0), (-0.35, 0.25, 18.0, 22.0)), texture: str | None = None):
        self.tex = load_texture(texture) if texture else make_texture(seed=seed)
        self.f, self.out, self.mm_per_texel = f_px, out, mm_per_texel
        self.boulders = boulders     # (x, y as a fraction of 200 mm from centre, radius mm, height mm)
        self.rng = np.random.default_rng(seed + 1)

    def layer(self, Z: float) -> np.ndarray:
        """The ground texture as seen from Z mm up. Closer means bigger."""
        k = self.f * self.mm_per_texel / Z
        cx, cy = self.tex.shape[1] / 2, self.tex.shape[0] / 2
        M = np.float32([[k, 0, self.out[0] / 2 - k * cx], [0, k, self.out[1] / 2 - k * cy]])
        return cv2.warpAffine(self.tex, M, self.out, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    def render(self, Z: float, noise: float = 2.0) -> np.ndarray:
        img = self.layer(Z).astype(np.float32)
        for bx, by, radius, height in self.boulders:
            Zb = max(Z - height, 5.0)          # a boulder top is closer to the camera than the ground
            top = self.layer(Zb).astype(np.float32)
            u = self.out[0] / 2 + self.f * bx * 200 / Zb
            v = self.out[1] / 2 + self.f * by * 200 / Zb
            mask = np.zeros(self.out[::-1], np.float32)
            cv2.circle(mask, (int(u), int(v)), int(self.f * radius / Zb), 1.0, -1)
            img = img * (1 - mask) + (top * 0.8 + 40) * mask
        img += self.rng.normal(0, noise, img.shape)
        return cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


class SimSource(Source):
    kind = "sim"

    def __init__(self, mm_per_step: float, h0: float = 450.0, speed: float = 30.0, floor: float = 70.0,
                 plateau_mm: float = 60.0, texture: str | None = None, realtime: bool = True,
                 fps: float = 30.0, seed: int = 0, render: tuple[int, int] = (320, 240)):
        # `render` only changes the image size, not the field of view. Bigger looks sharper on the dashboard
        self.scene = SimScene(f_px=260.0 * render[0] / 320, out=render, texture=texture, seed=seed)
        self.default_tex = self.scene.tex
        self.mm_per_step, self.h0, self.speed, self.floor = mm_per_step, h0, speed, floor
        self.plateau, self.realtime, self.fps = plateau_mm, realtime, fps
        self.rng = np.random.default_rng(seed + 7)
        self.t = time.monotonic() if realtime else 0.0
        self.ground = 0.0                          # height of the plateau under the sled, mm
        self.reset_rig()

    def reset_rig(self):
        self.sled, self.moving = self.h0, 0        # the plateau stays however the operator left it
        self.anchor = self.h0 - self.ground        # like zeroing on the rangefinder

    def command(self, name: str):
        if name == "descend":
            self.moving = 1
        elif name == "up":
            self.moving = -1
        elif name == "stop":
            self.moving = 0
        elif name == "reset":
            self.reset_rig()
        elif name == "terrain_up":
            self.ground = self.plateau
        elif name == "terrain_down":
            self.ground = 0.0
        elif name.startswith("texture:"):          # fly over a different ground photo ("" = back to the default)
            self.scene.tex = load_texture(name[8:]) if name[8:] else self.default_tex

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
        if self.sled - self.ground <= self.floor and self.moving == 1:
            self.moving = 0                        # touched down
        alt = self.sled - self.ground
        steps = int(round((self.h0 - self.sled) / self.mm_per_step))
        return Sample(self.t, self.scene.render(max(alt, 20.0)), float(alt + self.rng.normal(0, 1.5)),
                      steps, float(alt), self.moving == 1, self.anchor)
