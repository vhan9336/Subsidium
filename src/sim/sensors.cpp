#include "sensors.h"

#include <algorithm>
#include <cmath>
#include <thread>
#include <vector>

namespace so::sim {

GrayImage renderCamera(const Terrain& terrain, const CameraModel& cam, double x, double y, double z, std::mt19937& rng) {
  // Supersample only while a pixel covers more ground than a heightmap cell;
  // below that the albedo noise is already band-limited per pixel.
  const double footprint = (z - terrain.height(x, y)) / cam.focalPx;
  const int ss = footprint > 1.5 * terrain.spec().resolution ? 2 : 1;
  const int W = cam.width * ss, H = cam.height * ss;
  const double f = cam.focalPx * ss;
  GrayImage hi(W, H);
  auto band = [&](int pyStart, int pyEnd) {
    for (int py = pyStart; py < pyEnd; py++) {
      double s = z - terrain.height(x, y);
      for (int px = 0; px < W; px++) {
        const double dx = (px - (W - 1) / 2.0) / f, dy = (py - (H - 1) / 2.0) / f;
        // Ray/heightfield intersection by fixed-point iteration on the drop
        // distance, starting from the neighbouring pixel's answer.
        for (int k = 0; k < 2; k++) s = std::max(0.01, z - terrain.height(x + dx * s, y + dy * s));
        const double gx = x + dx * s, gy = y + dy * s;
        const double v = terrain.albedo(gx, gy, s / f) * terrain.shade(gx, gy);
        hi.at(px, py) = static_cast<float>(std::min(1.0, v));
      }
    }
  };
  // Rows are independent: split them across cores.
  const int threads = std::clamp(static_cast<int>(std::thread::hardware_concurrency()), 1, 8);
  std::vector<std::thread> pool;
  for (int k = 1; k < threads; k++) pool.emplace_back(band, H * k / threads, H * (k + 1) / threads);
  band(0, H / threads);
  for (auto& th : pool) th.join();

  GrayImage img = ss > 1 ? downsample(hi, ss) : std::move(hi);
  std::normal_distribution<float> N(0, static_cast<float>(cam.noise));
  for (float& v : img.data) v = std::clamp(v + N(rng), 0.f, 1.f);
  return img;
}

const char* toString(RangeFault f) {
  switch (f) {
    case RangeFault::None: return "none";
    case RangeFault::Covered: return "covered";
    case RangeFault::Dropout: return "no echo";
    case RangeFault::Late: return "late";
    case RangeFault::Noisy: return "spurious returns";
    case RangeFault::Stuck: return "stuck";
    case RangeFault::Lag: return "lagging";
  }
  return "?";
}

double Rangefinder::trueRange(const Terrain& t, double x, double y, double z) const {
  const double r0 = z - t.height(x, y);
  const double radius = std::max(0.0, r0) * std::tan(halfAngle_ * M_PI / 180);
  double best = r0;
  for (int k = 0; k < 6; k++) {
    const double a = k * M_PI / 3;
    best = std::min(best, z - t.height(x + radius * std::cos(a), y + radius * std::sin(a)));
  }
  return std::max(0.0, best);
}

std::optional<double> Rangefinder::measure(const Terrain& t, double x, double y, double z, double time) {
  const double truth = trueRange(t, x, y, z);
  std::normal_distribution<double> N(0, 1);
  std::uniform_real_distribution<double> U(0, 1);
  const double noisy = std::max(0.0, truth + N(rng_) * (0.003 * truth + 0.01));
  history_.emplace_back(time, noisy);
  while (history_.size() > 400) history_.pop_front();

  std::optional<double> out = noisy;
  switch (fault.type) {
    case RangeFault::None: break;
    case RangeFault::Covered: out = 0.03 + 0.005 * N(rng_); break;
    case RangeFault::Dropout: out.reset(); break;
    case RangeFault::Late:
      if (truth > fault.param) out.reset();
      break;
    case RangeFault::Noisy:
      if (U(rng_) < fault.param) out = U(rng_) * 2.0 * truth;
      break;
    case RangeFault::Stuck:
      out = last_.value_or(noisy);
      break;
    case RangeFault::Lag: {
      out.reset();
      for (auto it = history_.rbegin(); it != history_.rend(); ++it)
        if (it->first <= time - fault.param) {
          out = it->second;
          break;
        }
      break;
    }
  }
  if (out) last_ = out;
  return out;
}

}  // namespace so::sim
