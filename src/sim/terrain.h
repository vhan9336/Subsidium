#pragma once
// Procedural lunar terrain: a heightmap with craters and boulders, a
// precomputed sun-shading map with cast shadows, and procedural fine albedo
// detail so the camera has texture at every altitude.
#include <cstdint>
#include <vector>

namespace so::sim {

struct Crater {
  double x, y, radius, depth;
};
struct Boulder {
  double x, y, radius;
};

struct TerrainSpec {
  double size = 240;     // metres, square, centred on the origin
  double resolution = 0.12;
  uint32_t seed = 1;
  int craters = 70;
  double maxCraterRadius = 18;
  int boulders = 250;
  std::vector<Crater> extraCraters;
  // A cliff along x = cliffX: ground beyond it drops by cliffDepth.
  bool cliff = false;
  double cliffX = 0, cliffDepth = 0, cliffWidth = 2;  // scenario features (e.g. a big crater rim)
  struct Field {
    double x, y, radius;
    int count;
  };
  std::vector<Field> boulderFields;  // dense boulder patches
  double sunElevationDeg = 25;
  double sunAzimuthDeg = 120;
};

class Terrain {
 public:
  explicit Terrain(const TerrainSpec& spec);
  // Ground height at world (x, y), metres.
  double height(double x, double y) const;
  // Sun shading 0..1 (includes cast shadows).
  double shade(double x, double y) const;
  // Fine albedo detail, band-limited so it never aliases below a pixel.
  double albedo(double x, double y, double footprint) const;
  // Slope (degrees) and max height deviation within radius around (x, y).
  void siteQuality(double x, double y, double radius, double& slopeDeg, double& roughness) const;
  // Raise a flat block (the demo's cardboard "crater rim").
  void addBlock(double x0, double y0, double x1, double y1, double height);
  const TerrainSpec& spec() const { return spec_; }
  double size() const { return spec_.size; }

 private:
  double gridSample(const std::vector<float>& g, double x, double y) const;
  void computeShade(int x0, int y0, int x1, int y1);
  TerrainSpec spec_;
  int n_;
  std::vector<float> h_, shade_;
};

}  // namespace so::sim
