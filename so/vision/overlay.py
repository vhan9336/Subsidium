"""Draws the hazard grid and tracked points on a camera frame and returns it as a JPEG."""
import cv2
import numpy as np


def draw(frame, res, points_scale: float, show_hazard: bool, tint: float, jpeg_quality: int) -> bytes:
    img = frame.copy()
    h, w = img.shape[:2]
    if res.hazard is not None and show_hazard:
        n = res.hazard.shape[0]
        colour = img.copy()
        for i in range(n):
            for j in range(n):
                if np.isnan(res.hazard[i, j]):
                    continue
                a = float(np.clip(abs(res.hazard[i, j]) / 0.08, 0, 1))   # 8% of altitude is fully red
                cv2.rectangle(colour, (j * w // n, i * h // n), ((j + 1) * w // n, (i + 1) * h // n),
                              (40, int(190 * (1 - a)), int(255 * a)), -1)
        img = cv2.addWeighted(colour, tint, img, 1 - tint, 0)
        for k in range(1, n):                                            # tile edges, so it reads as a grid
            cv2.line(img, (k * w // n, 0), (k * w // n, h), (20, 20, 20), 1)
            cv2.line(img, (0, k * h // n), (w, k * h // n), (20, 20, 20), 1)
        if res.site is not None:                                         # crosshair on the safest tile
            i, j = res.site
            cx, cy = int((j + 0.5) * w / n), int((i + 0.5) * h / n)
            cv2.circle(img, (cx, cy), 24, (255, 255, 255), 2)
            cv2.line(img, (cx - 34, cy), (cx + 34, cy), (255, 255, 255), 1)
            cv2.line(img, (cx, cy - 34), (cx, cy + 34), (255, 255, 255), 1)
    if res.points is not None:
        for p in res.points[::2]:
            cv2.circle(img, (int(p[0] * points_scale), int(p[1] * points_scale)), 2, (255, 210, 120), -1)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])[1].tobytes()
