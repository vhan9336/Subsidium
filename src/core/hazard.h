#pragma once
// Landing-hazard map from the downward camera.
//
// The image is split into a grid. Each cell gets its own expansion fit,
// seeded with the global one. A cell that expands faster than the image as a
// whole is closer to the camera (a boulder top); a steady change in expansion
// across neighbouring cells is a slope. Strong shading contrast (shadows,
// rocks, crater walls) adds roughness. Scores are smoothed over time and the
// safest cell near the centre becomes the landing site.
#include <vector>

#include "image.h"
#include "ttc.h"

namespace so {

struct HazardParams {
  int cols = 8, rows = 6;
  double focalPx = 140;       // camera focal length in pixels (at the analysed resolution)
  double smoothing = 0.5;     // s
  double maxSafeSlopeDeg = 12;
  double maxRelHeight = 0.04;  // fraction of altitude
  double centrePenalty = 0.25;
  double safeThreshold = 0.5;
};

struct HazardMap {
  int cols = 0, rows = 0;
  std::vector<double> score;      // 0 = safe, 1 = hazardous
  std::vector<double> relHeight;  // + = closer than average (rock), fraction of altitude
  std::vector<double> slopeDeg;
  std::vector<double> roughness;
  bool siteFound = false;
  int siteCol = -1, siteRow = -1;
  // Site position in normalised image coords, -1..1 (x right, y down).
  double siteX = 0, siteY = 0;
  bool valid = false;
};

class HazardMapper {
 public:
  explicit HazardMapper(HazardParams p = {}) : p_(p) {}
  void reset() { map_ = {}; }
  // prev/curr are the frames the TTC tracker compared; c/tx/ty its global fit.
  const HazardMap& update(const GrayImage& prev, const GrayImage& curr, double c, double tx, double ty, double dt);
  const HazardMap& map() const { return map_; }

 private:
  HazardParams p_;
  HazardMap map_;
};

}  // namespace so
