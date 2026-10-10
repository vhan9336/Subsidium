#pragma once
// Altitude estimation with a cross-check between three independent sources:
//
//   1. the rangefinder (laser on a lander, ultrasonic on the demo rig),
//   2. the camera's time-to-contact multiplied by descent speed,
//   3. dead reckoning from the IMU's measured descent speed.
//
// Dead reckoning is trustworthy over a second or two but can't know when
// the ground itself changes height. So when the rangefinder jumps, we hold
// the reading as "pending" and ask the camera: if the camera's altitude moves
// to the new reading, the terrain changed (a crater rim) and we keep it. If
// the camera keeps agreeing with dead reckoning instead, the rangefinder is
// the one that's wrong. A rangefinder that keeps failing this check is
// declared failed and the lander lands on the camera estimate.
//
// BaselineEstimator reproduces the logic that doomed ispace's 2023 lander:
// reject any reading that jumps away from the prediction, and after enough
// rejections stop trusting the sensor at all.
#include <deque>
#include <optional>
#include <string>
#include <vector>

#include "ttc.h"

namespace so {

enum class SensorStatus { Ok, Suspect, Failed };
enum class AltSource { None, Rangefinder, Camera, DeadReckoning, Conservative };

const char* toString(SensorStatus s);
const char* toString(AltSource s);

struct FusionInput {
  double t = 0;
  std::optional<double> range;  // metres; empty = no echo / no data
  double descentRate = 0;       // m/s, positive when closing on the ground
  std::optional<TTCEstimate> camera;
};

struct FusionEvent {
  enum class Kind { Info, Good, Warn, Fault };
  double t;
  Kind kind;
  std::string text;
};

struct FusionParams {
  double initialAltitude = -1;  // < 0: initialise from the first sensor reading
  double relTol = 0.25;         // rangefinder vs camera agreement
  double absTol = 0.05;         // m
  double gateRel = 0.12;        // rangefinder vs dead reckoning
  double gateAbs = 0.10;        // m
  double minCamConfidence = 0.3;
  double minDescentRate = 0.005;  // m/s; below this the camera can't give altitude
  double confirmWindow = 2.0;     // s to wait for the camera before rejecting a jump
  double healthUp = 0.5;          // per second
  double healthDown = 0.8;        // per second
  double rangeBlend = 0.5;
  double cameraTau = 0.6;  // s
};

struct FusionOutput {
  double t = 0;
  double altitude = 0;
  AltSource source = AltSource::None;
  SensorStatus rangeStatus = SensorStatus::Ok;
  SensorStatus cameraStatus = SensorStatus::Ok;
  double rangeHealth = 1;
  double cameraHealth = 1;
  std::optional<double> range;
  std::optional<double> cameraAltitude;
  std::optional<double> cameraTTC;
  std::optional<double> rangeTTC;
  double deadReckoning = 0;
  bool jumpPending = false;
  std::string verdict;
};

class SecondOpinion {
 public:
  explicit SecondOpinion(FusionParams p = {}) : p_(p) {}
  FusionOutput update(const FusionInput& in);
  const std::vector<FusionEvent>& events() const { return events_; }

 private:
  void log(double t, FusionEvent::Kind k, std::string text) { events_.push_back({t, k, std::move(text)}); }
  void setRangeHealth(double t, double h);
  void setCameraHealth(double t, double h);
  bool agree(double a, double b) const;

  FusionParams p_;
  bool init_ = false;
  double h_ = 0, lastT_ = 0;
  double rangeHealth_ = 1, cameraHealth_ = 1;
  SensorStatus rangeStatus_ = SensorStatus::Ok, cameraStatus_ = SensorStatus::Ok;
  struct Pending {
    double start;
    double from;
    bool rejected = false;
  };
  std::optional<Pending> pending_;
  double disagreeTime_ = 0;
  std::deque<double> spikes_;  // times of brief spurious jumps
  bool noisy_ = false;
  bool missingLogged_ = false;
  bool blindLogged_ = false;
  std::vector<FusionEvent> events_;
};

class BaselineEstimator {
 public:
  explicit BaselineEstimator(FusionParams p = {}) : p_(p) {}
  FusionOutput update(const FusionInput& in);
  const std::vector<FusionEvent>& events() const { return events_; }

 private:
  FusionParams p_;
  bool init_ = false, lockedOut_ = false;
  double h_ = 0, lastT_ = 0, rejectTime_ = 0, lastRejectLog_ = -1e9;
  bool missingLogged_ = false;
  std::vector<FusionEvent> events_;
};

}  // namespace so
