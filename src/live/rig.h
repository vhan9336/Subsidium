#pragma once
// The physical demo: a webcam and an ultrasonic sensor on a stepper-driven
// carriage lowered over a 3D-printed moonscape. The Arduino streams
//
//     R,<millis>,<range_mm or -1>,<speed_mm_s>,<position_mm>
//
// and accepts D<mm_s> (descend), U<mm_s> (ascend), S (stop), Z (zero).
#include <deque>
#include <optional>
#include <string>

#include "core/fusion.h"
#include "core/hazard.h"
#include "core/ttc.h"
#include "serial.h"
#include "webcam.h"

namespace so::live {

struct RigSample {
  double t;
  double range;  // NaN if missing
  double cameraAlt;
  double fused;
  double speed;
};

class Rig {
 public:
  Rig();
  bool connectSerial(const std::string& path);
  bool connectCamera(const std::string& device);
  void disconnect();
  // Call every UI frame.
  void poll(double now);
  void resetEstimator();
  void command(const std::string& cmd) { serial_.writeLine(cmd); }

  SerialPort serial_;
  Webcam webcam_;
  GrayImage frame;  // analysed (160x120)
  std::optional<TTCEstimate> ttc;
  FusionOutput nav;
  HazardMap hazard;
  std::optional<double> range;  // m
  double speed = 0;             // m/s, positive = descending
  double position = 0;          // m
  std::deque<RigSample> history;
  std::string lastLine;
  std::string status;
  const std::vector<FusionEvent>& events() const { return fusion_.events(); }

 private:
  FusionParams params_;
  SecondOpinion fusion_;
  TTCTracker tracker_;
  HazardMapper hazardMapper_;
  double lastSerial_ = -1;
  bool haveTelemetry_ = false;
};

}  // namespace so::live
