"""A pretend Arduino, so the live rig code can be tried with nothing plugged in.

  python tools/fake_rig.py            prints a port name, like /dev/pts/7 (add --no-motor to mimic the ultrasonic-only sketch)
  python -m so serve --video --rig /dev/pts/7 --cam footage/blue_ghost_m1_landing_scalpss.mp4

It talks the same serial protocol as firmware/rig/rig.ino: it prints R,<ms>,<range_mm>,<angle_tenths>
lines and understands d u s C Z and A<tenths>. The sled hangs START_MM above the floor at the top and
comes down 1 mm per degree, so the ultrasonic reading is that height plus a little noise.
"""
import os
import random
import threading
import time

START_MM = 220            # how high the ultrasonic sensor sits above the floor with the sled at the top
MM_PER_TENTH = 0.1
STOP_MM = 45              # the demo descent stops when the sensor reads closer than this (as in the sketch)
SLEW = 600                # tenths of a degree per second, for ordinary moves
DEMO = 100                # tenths per second for the demo descent
MAX_TENTHS = 1800


class FakeRig:
    def __init__(self, motor: bool = True):
        self.motor = motor                       # False: report angle 0 always, like firmware/ultrasonic
        self.master, slave = os.openpty()
        self.port = os.ttyname(slave)
        self._slave = slave                      # keep it open, or reads on the other end would fail
        self.target = 0.0
        self.pos = 0.0
        self.instant = False
        self.demo = False
        self.range_mm = START_MM
        self.stop = threading.Event()
        threading.Thread(target=self.run, daemon=True).start()

    def altitude(self) -> float:
        return START_MM - self.pos * MM_PER_TENTH

    def handle(self, text: str):
        if not text:
            return
        c = text[0]
        if c == "A":
            self.demo = False
            self.target = min(max(float(text[1:] or 0), 0), MAX_TENTHS)
        elif c == "d":
            self.demo = True
        elif c in "uZ":
            self.demo, self.target = False, 0.0
        elif c == "s":
            self.demo, self.target = False, self.pos
        elif c in "cC":
            self.demo, self.target, self.instant = False, float(MAX_TENTHS), True

    def run(self):
        os.set_blocking(self.master, False)
        typed = ""
        last = time.monotonic()
        last_ping = 0.0
        while not self.stop.is_set():
            try:
                typed += os.read(self.master, 256).decode(errors="ignore")
            except (BlockingIOError, OSError):
                pass
            while typed:
                if typed[0] == "A" and "\n" not in typed:
                    break                          # an A command is waiting for its newline
                end = typed.index("\n") + 1 if typed[0] == "A" else 1
                self.handle(typed[:end].strip())
                typed = typed[end:]
            now = time.monotonic()
            dt, last = now - last, now
            if self.demo:
                if 0 < self.range_mm < STOP_MM or self.target >= MAX_TENTHS:
                    self.demo, self.target = False, self.pos
                else:
                    self.target += max(1.0, DEMO * dt)
            if self.instant:
                self.pos, self.instant = self.target, False
            else:
                step = SLEW * dt
                self.pos = min(self.target, self.pos + step) if self.pos < self.target else max(self.target, self.pos - step)
            if now - last_ping >= 0.05:
                last_ping = now
                alt = self.altitude()
                self.range_mm = round(alt + random.gauss(0, 1.0)) if alt > 20 else -1
                os.write(self.master, f"R,{int(now * 1000)},{self.range_mm},{int(self.pos) if self.motor else 0}\r\n".encode())
            time.sleep(0.005)


if __name__ == "__main__":
    import sys
    rig = FakeRig(motor="--no-motor" not in sys.argv)
    print(rig.port, flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
