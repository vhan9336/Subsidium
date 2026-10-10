#pragma once
#include <deque>
#include <optional>
#include <random>

#include "../core/image.h"
#include "terrain.h"

namespace so::sim {

// Pinhole camera pointing straight down. Renders at 2x and box-filters down.
struct CameraModel {
  int width = 160, height = 120;
  double focalPx = 140;  // ~60 degree horizontal field of view
  double noise = 0.004;  // per-pixel sensor noise
};

GrayImage renderCamera(const Terrain& terrain, const CameraModel& cam, double x, double y, double z, std::mt19937& rng);

enum class RangeFault {
  None,
  Covered,  // something sits over the sensor: reads a few cm (the rig demo)
  Dropout,  // no echo at all (Odysseus: rangefinders unusable)
  Late,     // nothing until close to the ground (Resilience)
  Noisy,    // spurious returns (Athena)
  Stuck,    // freezes at its last value
  Lag,      // reports what it saw a while ago
};
const char* toString(RangeFault f);

struct RangeFaultState {
  RangeFault type = RangeFault::None;
  double param = 0;  // Late: altitude where readings start. Lag: seconds. Noisy: bad-sample rate.
};

class Rangefinder {
 public:
  explicit Rangefinder(uint32_t seed, double beamHalfAngleDeg = 2.0) : rng_(seed), halfAngle_(beamHalfAngleDeg) {}
  // True range to the ground (shortest return in the beam).
  double trueRange(const Terrain& t, double x, double y, double z) const;
  std::optional<double> measure(const Terrain& t, double x, double y, double z, double time);
  RangeFaultState fault;

 private:
  std::mt19937 rng_;
  double halfAngle_;
  std::optional<double> last_;
  std::deque<std::pair<double, double>> history_;
};

}  // namespace so::sim
