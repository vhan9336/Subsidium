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


SUN = np.array([-0.6, -0.5])            # which way the light comes from, in the image (up and to the left)
SUN_ELEVATION = 0.45                    # how high the sun is, as tan(angle): low, so shadows are long


def make_relief(size: int = 1400, seed: int = 0, craters: int = 160, r_range=(5, 70)) -> np.ndarray:
    """A patch of cratered ground, lit from the side, as light and dark shading in -1 to 1.

    The height is blobby noise plus bowl-shaped craters with raised rims, and the shading is how
    much each bit of slope faces the sun. Texture made this way keeps looking like terrain when you
    zoom in on it, where an ordinary photo just turns to mush.
    """
    rng = np.random.default_rng(seed)
    height = np.zeros((size, size), np.float32)
    for k, amp in ((4, 6.0), (12, 4.0), (40, 3.0)):
        noise = rng.random((size // k + 2, size // k + 2)).astype(np.float32)
        height += amp * cv2.resize(noise, (size, size), interpolation=cv2.INTER_CUBIC)
    for _ in range(craters):
        # many small craters, a few big ones, like real ground
        r = int(r_range[0] + (r_range[1] - r_range[0]) * rng.random() ** 3)
        cx, cy = rng.integers(0, size, 2)
        ys, xs = np.mgrid[-r * 2:r * 2 + 1, -r * 2:r * 2 + 1]
        d = np.hypot(xs, ys) / r
        bowl = np.where(d < 1, -(1 - d ** 2), 0.0) * 0.5 * r
        rim = 0.12 * r * np.exp(-((d - 1.05) / 0.12) ** 2)
        y0, y1, x0, x1 = max(cy - 2 * r, 0), min(cy + 2 * r + 1, size), max(cx - 2 * r, 0), min(cx + 2 * r + 1, size)
        height[y0:y1, x0:x1] += (bowl + rim)[y0 - cy + 2 * r:y1 - cy + 2 * r, x0 - cx + 2 * r:x1 - cx + 2 * r]
    gx, gy = cv2.Sobel(height, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(height, cv2.CV_32F, 0, 1, ksize=3)
    shade = (gx * SUN[0] + gy * SUN[1]) / (np.abs(height).std() + 1e-6) * 0.35
    return np.clip(shade, -1, 1).astype(np.float32)


def smoothstep(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


class SimScene:
    """Draws what a downward camera sees from Z mm above the ground.

    The ground is a photo (or made-up texture) with extra layers of crater detail on top. Each layer
    is finer than the one before, and fades in once the camera is close enough for it to be visible,
    so coming down shows new craters and rocks, not just a bigger blur. A coarse layer fills in when
    the view is wider than the photo. Boulders cast shadows, and the picture has the light falloff
    and grain of a real camera.
    """

    DETAIL = (3, 9, 27)          # how many times finer each detail layer is than the photo
    MACRO = (5, 25)              # how many times coarser each wide-view layer is

    def __init__(self, f_px: float = 260.0, out=(320, 240), mm_per_texel: float = 0.5, seed: int = 0,
                 boulders=((0.25, -0.15, 22.0, 30.0), (-0.35, 0.25, 18.0, 22.0)), texture: str | None = None):
        self.tex = load_texture(texture) if texture else make_texture(seed=seed)
        self.f, self.out, self.mm_per_texel = f_px, out, mm_per_texel
        self.boulders = boulders     # (x, y as a fraction of 200 mm from centre, radius mm, height mm)
        self.rng = np.random.default_rng(seed + 1)
        self.mean = float(self.tex.mean())
        self.tex_f = self.tex.astype(np.float32)
        self.fine = [make_relief(seed=seed + 10 + i, craters=120, r_range=(4, 40)) for i, _ in enumerate(self.DETAIL)]
        self.wide = [make_relief(seed=seed + 20 + i, craters=60, r_range=(30, 150)) for i, _ in enumerate(self.MACRO)]
        h, w = out[1], out[0]
        yy, xx = np.mgrid[0:h, 0:w]
        self.rows, self.cols = yy.astype(np.float32), xx.astype(np.float32)
        self.vignette = (1 - 0.28 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / 2).astype(np.float32)

    def warp(self, tex: np.ndarray, pitch: float, Z: float, window=None) -> np.ndarray:
        """A texture as seen from Z mm up. Closer means bigger. `window` is (x0, y0, x1, y1) if only a patch is needed."""
        k = self.f * pitch / Z
        cx, cy = tex.shape[1] / 2, tex.shape[0] / 2
        x0, y0, x1, y1 = window or (0, 0, *self.out)
        M = np.float32([[k, 0, self.out[0] / 2 - k * cx - x0], [0, k, self.out[1] / 2 - k * cy - y0]])
        return cv2.warpAffine(tex, M, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    def ground(self, Z: float) -> np.ndarray:
        """The ground alone: the photo, then fine detail where we're close, and wide-view detail where we're not."""
        img = self.warp(self.tex_f, self.mm_per_texel, Z)
        k = self.f * self.mm_per_texel / Z              # how many pixels one photo texel covers
        for shade, factor in zip(self.fine, self.DETAIL):
            kf = k * factor
            weight = smoothstep((kf - 1.0) / 2.0)       # only once a texel is clearly bigger than a pixel, or it just looks like static
            if weight > 0.03:
                img *= 1 + 0.45 * weight * self.warp(shade, self.mm_per_texel / factor, Z)
        wide = smoothstep((0.6 - k) / 0.5)               # the photo is shrunk below a pixel a texel: it's a wide view
        if wide > 0.03:
            for shade, factor in zip(self.wide, self.MACRO):
                layer = self.mean * (1 + 0.9 * self.warp(shade, self.mm_per_texel * factor, Z))
                img = img * (1 - 0.7 * wide) + layer * 0.7 * wide
        return img

    def render(self, Z: float, noise: float = 2.0) -> np.ndarray:
        img = self.ground(Z)
        for bx, by, radius, height in self.boulders:
            self.draw_boulder(img, Z, bx, by, radius, height)
        img = img * self.vignette + self.rng.normal(0, noise, img.shape)
        return cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)

    def draw_boulder(self, img: np.ndarray, Z: float, bx: float, by: float, radius: float, height: float):
        """A rock with its shadow, drawn into img. Only the patch around it is touched, to keep this quick."""
        W, H = self.out
        Zb = max(Z - height, 5.0)                      # the top of a boulder is closer to the camera than the ground
        u0, v0 = W / 2 + self.f * bx * 200 / Z, H / 2 + self.f * by * 200 / Z      # where it sits on the ground
        u, v = W / 2 + self.f * bx * 200 / Zb, H / 2 + self.f * by * 200 / Zb      # where its top appears
        r_ground, r_top = self.f * radius / Z, self.f * radius / Zb
        reach = self.f * height / Z / SUN_ELEVATION    # how far the shadow is thrown, in pixels
        direction = -SUN / np.linalg.norm(SUN)
        pad = reach + 3 * max(r_ground, r_top) + 6
        x0, x1 = int(max(min(u0, u) - pad, 0)), int(min(max(u0, u) + pad, W))
        y0, y1 = int(max(min(v0, v) - pad, 0)), int(min(max(v0, v) + pad, H))
        if x1 - x0 < 2 or y1 - y0 < 2:
            return                                      # it's out of view
        patch = img[y0:y1, x0:x1]
        # the shadow is soft, so draw and blur it at half size and scale it back up
        shadow = np.zeros((max((y1 - y0) // 2, 1), max((x1 - x0) // 2, 1)), np.float32)
        cv2.ellipse(shadow, (int((u0 - x0 + direction[0] * reach / 2) / 2), int((v0 - y0 + direction[1] * reach / 2) / 2)),
                    (max(int((reach / 2 + r_ground * 0.6) / 2), 1), max(int(r_ground * 0.45), 1)),
                    float(np.degrees(np.arctan2(direction[1], direction[0]))), 0, 360, 1.0, -1)
        shadow = cv2.GaussianBlur(shadow, (0, 0), max(r_ground * 0.075, 0.6))
        patch *= 1 - 0.6 * cv2.resize(shadow, (x1 - x0, y1 - y0), interpolation=cv2.INTER_LINEAR)
        yy, xx = self.rows[y0:y1, x0:x1], self.cols[y0:y1, x0:x1]
        # a rock is lit on the side facing the sun and dark on the other
        lit = 0.55 - 0.45 * np.clip(((xx - u) * SUN[0] + (yy - v) * SUN[1]) / (r_top * np.linalg.norm(SUN) + 1e-6), -1, 1)
        mask = np.zeros(patch.shape, np.float32)
        cv2.circle(mask, (int(u - x0), int(v - y0)), max(int(r_top), 1), 1.0, -1)
        top = self.warp(self.tex_f, self.mm_per_texel, Zb, (x0, y0, x1, y1))
        patch[:] = patch * (1 - mask) + (top * 0.8 + 40) * lit * mask


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

    def resync(self):
        if self.realtime:
            self.t = time.monotonic()

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
