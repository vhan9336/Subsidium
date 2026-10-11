"""The real rig: an Arduino over serial, plus a USB webcam.

Arduino to laptop, about 20 times a second:  R,<millis>,<range_mm or -1>,<steps>
Laptop to Arduino, one character:            d descend, u up, s stop, z zero the step counter
"""
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
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)      # focus hunting looks like the image growing, so turn it off
        self.latest = {"rf": None, "steps": 0}
        self.recent_rf = collections.deque(maxlen=40)
        self.descending = False
        self.lock = threading.Lock()
        threading.Thread(target=self.read_serial, daemon=True).start()
        time.sleep(2.0)                               # the Arduino reboots whenever the port opens
        self.command("zero")

    def read_serial(self):
        """Runs on its own thread and keeps the newest reading ready."""
        while True:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
                tag, _ms, rng, steps = line.split(",")
                if tag != "R":
                    continue
                rf = float(rng)
                with self.lock:
                    self.latest = {"rf": rf if rf > 0 else None, "steps": int(steps)}
                    if rf > 0:
                        self.recent_rf.append(rf)
            except serial.SerialException:
                time.sleep(0.5)
            except ValueError:                        # a half-finished or non-data line; wait for the next
                pass

    def command(self, name: str):
        if name in ("descend", "up", "stop"):
            self.ser.write({"descend": b"d", "up": b"u", "stop": b"s"}[name])
            self.descending = name == "descend"
        elif name in ("zero", "reset"):
            if name == "reset":
                self.ser.write(b"s")
                self.descending = False
            self.ser.write(b"z")
            time.sleep(0.15)
            # whatever the rangefinder says right now becomes the starting altitude
            with self.lock:
                recent = list(self.recent_rf)[-10:]
            self.h0 = float(np.median(recent)) if recent else self.h0

    def read(self) -> Sample | None:
        ok, frame = self.cap.read()
        if not ok:
            return None
        with self.lock:
            d = dict(self.latest)
        return Sample(time.monotonic(), frame, d["rf"], d["steps"], None, self.descending, self.h0)

    def close(self):
        self.cap.release()
        self.ser.close()
