"""Real hardware: Arduino rig over serial + USB webcam.

Arduino -> laptop, ~20 Hz:   R,<millis>,<range_mm or -1>,<steps>
Laptop  -> Arduino, 1 char:  d = descend, u = up, s = stop, z = zero step counter
"""
from __future__ import annotations

import collections
import threading
import time

import cv2
import numpy as np
import serial

from .base import Sample, Source


class LiveSource(Source):
    kind = "live"

    def __init__(self, port: str, mm_per_step: float, cam_index: int = 0, width: int = 640, height: int = 480,
                 baud: int = 115200):
        self.mm_per_step = mm_per_step
        self.ser = serial.Serial(port, baud, timeout=0.1)
        self.cap = cv2.VideoCapture(cam_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)      # focus breathing looks like expansion: lock it
        self.latest = {"rf": None, "steps": 0}
        self.rf_hist: collections.deque = collections.deque(maxlen=40)
        self.descending = False
        self._lock = threading.Lock()
        threading.Thread(target=self._reader, daemon=True).start()
        time.sleep(2.0)                               # Arduino resets when the port opens
        self.command("zero")

    def _reader(self):
        while True:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
            except serial.SerialException:
                time.sleep(0.5)
                continue
            if not line.startswith("R,"):
                continue
            try:
                _, _ms, rng, steps = line.split(",")
                rf = float(rng)
                with self._lock:
                    self.latest = {"rf": rf if rf > 0 else None, "steps": int(steps)}
                    if rf > 0:
                        self.rf_hist.append(rf)
            except ValueError:
                pass

    def command(self, name: str):
        c = {"descend": "d", "up": "u", "stop": "s"}.get(name)
        if c:
            self.ser.write(c.encode())
            self.descending = name == "descend"
        elif name in ("zero", "reset"):
            # calibrate: the current rangefinder reading becomes the navigation anchor
            if name == "reset":
                self.ser.write(b"s")
                self.descending = False
            self.ser.write(b"z")
            time.sleep(0.15)
            with self._lock:
                recent = list(self.rf_hist)[-10:]
            self.h0 = float(np.median(recent)) if recent else self.h0

    def read(self) -> Sample | None:
        ok, frame = self.cap.read()
        if not ok:
            return None
        with self._lock:
            d = dict(self.latest)
        return Sample(time.monotonic(), frame, d["rf"], d["steps"], None, self.descending, self.h0)

    def close(self):
        self.cap.release()
        self.ser.close()
