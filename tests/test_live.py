"""The live rig code against a pretend Arduino (tools/fake_rig.py) and a video file standing in for the webcam."""
import sys
import time

import cv2
import pytest

from so.sources.live import LiveSource
from so.sources.sim import SimScene

sys.path.insert(0, "tools")
from fake_rig import MM_PER_TENTH, FakeRig  # noqa: E402


@pytest.fixture
def rig(tmp_path):
    fake = FakeRig()
    video = str(tmp_path / "cam.mp4")                     # a short descent, standing in for the webcam
    scene, writer = SimScene(), cv2.VideoWriter(video, cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 240))
    for k in range(90):
        writer.write(scene.render(300 - k))
    writer.release()
    source = LiveSource(fake.port, MM_PER_TENTH, video)
    yield source, fake
    source.close()
    fake.stop.set()


def read_for(source, seconds):
    samples, end = [], time.monotonic() + seconds
    while time.monotonic() < end:
        samples.append(source.read())
    return [s for s in samples if s]


def test_it_calibrates_on_the_sensor_at_the_top(rig):
    source, _ = rig
    read_for(source, 1.5)
    assert abs(source.h0 - 220) < 5


def test_descending_lowers_the_angle_and_the_range(rig):
    source, _ = rig
    read_for(source, 1.0)
    source.command("descend")
    samples = read_for(source, 3.0)
    assert samples[-1].steps > samples[0].steps + 100       # the angle went up (the sled went down)
    assert samples[-1].rf_raw < samples[0].rf_raw - 15      # and the sensor sees the floor getting closer
    assert any(s.descending for s in samples)


def test_engine_cut_jumps_to_the_bottom_and_reset_comes_back(rig):
    source, _ = rig
    read_for(source, 0.5)
    source.command("cut")
    cut = read_for(source, 0.5)
    assert cut[-1].steps >= 1700
    source.command("reset")
    read_for(source, 5.0)
    assert source.read().steps <= 5


def test_without_a_motor_the_steps_follow_the_ultrasonic(tmp_path):
    fake = FakeRig(motor=False)                           # the Arduino always reports 0 for the angle
    video = str(tmp_path / "cam.mp4")
    scene, writer = SimScene(), cv2.VideoWriter(video, cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 240))
    for k in range(60):
        writer.write(scene.render(300 - k))
    writer.release()
    source = LiveSource(fake.port, MM_PER_TENTH, video, motor=False)
    try:
        read_for(source, 1.5)
        source.command("descend")                          # the fake sensor sees the floor come closer
        samples = read_for(source, 3.0)
        assert samples[-1].steps > 100 and samples[-1].rf_raw < samples[0].rf_raw - 15
        assert any(s.descending for s in samples)
    finally:
        source.close()
        fake.stop.set()
