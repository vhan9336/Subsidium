"""The real rig: an Arduino with a servo winch and an ultrasonic sensor, plus a webcam.

Arduino to laptop, 20 times a second:  R,<millis>,<range_mm or -1>,<angle_tenths>
Laptop to Arduino, one character:      d demo descent, u up, s stop, C engine cut, Z back to the top
(Anything the Arduino prints that starts with # is for humans, and we skip it.)

The servo angle plays the part of the inertial unit: tenths of a degree turned, times how many mm
of cord each tenth lets out (config.toml, rig.mm_per_tenth), is how far the sled has gone down. It's
the *commanded* angle, not a measured one, which is fine while the sled follows the servo.
"""
import collections
import glob
import statistics
import threading
import time

import cv2
import serial
import serial.tools.list_ports

from .base import Sample, Source

FRAME_INTERVAL_S = 1 / 30      # a webcam paces itself, but a video file standing in for one would race
COMMANDS = {"descend": b"d", "up": b"u", "stop": b"s", "cut": b"C"}
ARDUINO_IDS = (0x2341, 0x2A03, 0x1A86, 0x0403)     # USB vendor ids: Arduino, clones with CH340 or FTDI chips


def find_serial_port() -> str:
    """Looks for a connected Arduino, so you don't have to know what the port is called."""
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if p.vid in ARDUINO_IDS or "arduino" in (p.description or "").lower():
            return p.device
    usb = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*") + glob.glob("/dev/tty.usbmodem*"))
    if usb:
        return usb[0]
    raise FileNotFoundError("no Arduino found: plug it in, or give the port, like --rig COM3 or --rig /dev/ttyACM0")


class LiveSource(Source):
    kind = "live"

    def __init__(self, port: str, mm_per_step: float, cam=0, width: int = 640, height: int = 480, baud: int = 115200):
        self.mm_per_step = mm_per_step                 # here a "step" is one tenth of a degree of servo
        self.ser = serial.Serial(find_serial_port() if port == "auto" else port, baud, timeout=0.1)
        self.cap = cv2.VideoCapture(cam)               # a camera number, or a video file to test with
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)        # focus hunting looks like the image growing, so turn it off
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)       # always the newest frame, not one from a second ago
        self.latest = {"rf": None, "steps": 0}
        self.recent_rf = collections.deque(maxlen=40)
        self.recent_steps = collections.deque()        # (time, angle), to tell whether the sled is moving down
        self.calibrating = False
        self.closed = False
        self.next_frame = 0.0
        self.lock = threading.Lock()
        threading.Thread(target=self.read_serial, daemon=True).start()
        time.sleep(2.0)                                # the Arduino reboots whenever the port opens
        self.command("reset")

    def read_serial(self):
        """Runs on its own thread and keeps the newest reading ready."""
        while not self.closed:
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
            except ValueError:                         # a comment line, or one cut off halfway
                pass
            except (TypeError, OSError):               # the port was closed under us
                return

    def command(self, name: str):
        if name in COMMANDS:
            self.ser.write(COMMANDS[name])
        elif name == "reset":
            # Go back to the top. Once the sled arrives, whatever the sensor reads there becomes the
            # starting altitude (see read), which is what the angle counts down from.
            self.ser.write(b"Z")
            with self.lock:
                self.recent_rf.clear()
            self.recent_steps.clear()
            self.h0, self.calibrating = None, True

    def moving_down(self, now: float, steps: int) -> bool:
        """True while the servo has turned down in the last half second."""
        self.recent_steps.append((now, steps))
        while now - self.recent_steps[0][0] > 0.5:
            self.recent_steps.popleft()
        return steps - self.recent_steps[0][1] >= 3

    def read(self) -> Sample | None:
        wait = self.next_frame - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.next_frame = time.monotonic() + FRAME_INTERVAL_S
        ok, frame = self.cap.read()
        if not ok and self.cap.get(cv2.CAP_PROP_FRAME_COUNT) > 0:      # a test video ran out: start it over
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()
        if not ok:
            return None
        now = time.monotonic()
        with self.lock:
            d = dict(self.latest)
            recent = list(self.recent_rf)[-10:]
        if self.calibrating and d["steps"] <= 5 and len(recent) >= 5:
            self.h0, self.calibrating = statistics.median(recent), False
        return Sample(now, frame, d["rf"], d["steps"], None, self.moving_down(now, d["steps"]), self.h0)

    def close(self):
        self.closed = True
        self.cap.release()
        self.ser.close()
