#include "rig.h"

#include <cmath>
#include <cstdio>
#include <limits>

namespace so::live {

namespace {
FusionParams rigParams() {
  // Rig scale: tens of centimetres at a few cm/s.
  FusionParams p;
  p.absTol = 0.01;
  p.gateAbs = 0.02;
  p.minDescentRate = 0.003;
  return p;
}
TTCTrackerOptions rigTracker() {
  TTCTrackerOptions o;
  o.maxBaseline = 30;  // up to ~1 s back at 30 fps: the rig moves slowly
  o.smoothing = 0.4;
  return o;
}
HazardParams rigHazard() {
  HazardParams h;
  h.focalPx = 140;  // typical 60 deg webcam at 160 px wide; calibrate if needed
  return h;
}
}  // namespace

Rig::Rig() : params_(rigParams()), fusion_(params_), tracker_(rigTracker()), hazardMapper_(rigHazard()) {}

bool Rig::connectSerial(const std::string& path) {
  const bool ok = serial_.open(path);
  status = ok ? "Serial connected: " + path : serial_.error();
  return ok;
}

bool Rig::connectCamera(const std::string& device) {
  const bool ok = webcam_.open(device);
  status = ok ? "Camera connected: " + device : webcam_.error();
  return ok;
}

void Rig::disconnect() {
  serial_.close();
  webcam_.close();
  status = "Disconnected";
}

void Rig::resetEstimator() {
  fusion_ = SecondOpinion(params_);
  tracker_.reset();
  hazardMapper_.reset();
  history.clear();
}

void Rig::poll(double now) {
  while (auto line = serial_.readLine()) {
    lastLine = *line;
    long ms;
    double rangeMm, speedMm, posMm;
    if (std::sscanf(line->c_str(), "R,%ld,%lf,%lf,%lf", &ms, &rangeMm, &speedMm, &posMm) == 4) {
      range = rangeMm >= 0 ? std::optional<double>(rangeMm / 1000) : std::nullopt;
      speed = speedMm / 1000;
      position = posMm / 1000;
      haveTelemetry_ = true;
      lastSerial_ = now;
    }
  }
  auto img = webcam_.grab();
  if (!img) return;
  frame = resizeArea(*img, 160, 120);
  ttc = tracker_.push(frame, now);
  if (ttc) {
    const ExpansionFit& f = tracker_.lastFit();
    hazard = hazardMapper_.update(tracker_.lastReference(), frame, f.c, f.tx, f.ty, tracker_.lastDt());
  }
  FusionInput in;
  in.t = now;
  // Without telemetry the rangefinder is simply absent.
  in.range = haveTelemetry_ && now - lastSerial_ < 0.5 ? range : std::nullopt;
  in.descentRate = speed;
  in.camera = ttc;
  nav = fusion_.update(in);
  constexpr double nan = std::numeric_limits<double>::quiet_NaN();
  history.push_back({now, in.range.value_or(nan), nav.cameraAltitude.value_or(nan), nav.altitude, speed});
  while (history.size() > 1500) history.pop_front();
}

}  // namespace so::live
