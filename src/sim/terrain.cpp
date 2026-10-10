#include "terrain.h"

#include <algorithm>
#include <cmath>
#include <random>

namespace so::sim {
namespace {

uint32_t hash(int x, int y, uint32_t seed) {
  uint32_t h = static_cast<uint32_t>(x) * 374761393u + static_cast<uint32_t>(y) * 668265263u + seed * 2246822519u;
  h = (h ^ (h >> 13)) * 1274126177u;
  return h ^ (h >> 16);
}

// Smooth value noise in [0, 1].
double valueNoise(double x, double y, uint32_t seed) {
  const double fx = std::floor(x), fy = std::floor(y);
  const int ix = static_cast<int>(fx), iy = static_cast<int>(fy);
  double tx = x - fx, ty = y - fy;
  tx = tx * tx * (3 - 2 * tx);
  ty = ty * ty * (3 - 2 * ty);
  const auto v = [&](int a, int b) { return (hash(a, b, seed) & 0xffff) / 65535.0; };
  const double a = v(ix, iy) + (v(ix + 1, iy) - v(ix, iy)) * tx;
  const double b = v(ix, iy + 1) + (v(ix + 1, iy + 1) - v(ix, iy + 1)) * tx;
  return a + (b - a) * ty;
}

double craterProfile(double d, double r, double depth) {
  // Bowl with a raised rim that fades out to ~1.6 radii.
  const double q = d / r;
  if (q < 1) return -depth * (1 - q * q) + 0.25 * depth * q * q * q * q;
  if (q < 1.6) {
    const double t = (q - 1) / 0.6;
    return 0.25 * depth * (1 - t) * (1 - t);
  }
  return 0;
}

}  // namespace

Terrain::Terrain(const TerrainSpec& spec) : spec_(spec) {
  n_ = static_cast<int>(spec.size / spec.resolution) + 1;
  h_.assign(static_cast<size_t>(n_) * n_, 0.f);
  std::mt19937 rng(spec.seed);
  std::uniform_real_distribution<double> U(0, 1);
  const double half = spec.size / 2;

  // Gentle rolling base.
  for (int j = 0; j < n_; j++)
    for (int i = 0; i < n_; i++) {
      const double x = i * spec.resolution - half, y = j * spec.resolution - half;
      double z = 0, amp = 1.5, freq = 1 / 60.0;
      for (int o = 0; o < 4; o++, amp *= 0.45, freq *= 2.3) z += amp * (valueNoise(x * freq, y * freq, spec.seed + o) - 0.5);
      if (spec.cliff) z -= spec.cliffDepth * std::clamp((x - spec.cliffX) / spec.cliffWidth + 0.5, 0.0, 1.0);
      h_[static_cast<size_t>(j) * n_ + i] = static_cast<float>(z);
    }

  std::vector<Crater> craters = spec.extraCraters;
  for (int k = 0; k < spec.craters; k++) {
    // Power law: many small craters, few big ones.
    const double r = 1.0 + (spec.maxCraterRadius - 1.0) * std::pow(U(rng), 3.0);
    craters.push_back({(U(rng) - 0.5) * spec.size, (U(rng) - 0.5) * spec.size, r, r * (0.15 + 0.1 * U(rng))});
  }
  for (const Crater& c : craters) {
    const double reach = c.radius * 1.6;
    const int i0 = std::max(0, static_cast<int>((c.x - reach + half) / spec.resolution));
    const int i1 = std::min(n_ - 1, static_cast<int>((c.x + reach + half) / spec.resolution) + 1);
    const int j0 = std::max(0, static_cast<int>((c.y - reach + half) / spec.resolution));
    const int j1 = std::min(n_ - 1, static_cast<int>((c.y + reach + half) / spec.resolution) + 1);
    for (int j = j0; j <= j1; j++)
      for (int i = i0; i <= i1; i++) {
        const double d = std::hypot(i * spec.resolution - half - c.x, j * spec.resolution - half - c.y);
        h_[static_cast<size_t>(j) * n_ + i] += static_cast<float>(craterProfile(d, c.radius, c.depth));
      }
  }

  std::vector<Boulder> boulders;
  for (int k = 0; k < spec.boulders; k++)
    boulders.push_back({(U(rng) - 0.5) * spec.size, (U(rng) - 0.5) * spec.size, 0.2 + 0.8 * std::pow(U(rng), 3.0)});
  for (const auto& f : spec.boulderFields)
    for (int k = 0; k < f.count; k++) {
      const double a = U(rng) * 2 * M_PI, d = f.radius * std::sqrt(U(rng));
      boulders.push_back({f.x + d * std::cos(a), f.y + d * std::sin(a), 0.3 + 1.2 * std::pow(U(rng), 2.0)});
    }
  for (const Boulder& b : boulders) {
    const int i0 = std::max(0, static_cast<int>((b.x - b.radius + half) / spec.resolution));
    const int i1 = std::min(n_ - 1, static_cast<int>((b.x + b.radius + half) / spec.resolution) + 1);
    const int j0 = std::max(0, static_cast<int>((b.y - b.radius + half) / spec.resolution));
    const int j1 = std::min(n_ - 1, static_cast<int>((b.y + b.radius + half) / spec.resolution) + 1);
    for (int j = j0; j <= j1; j++)
      for (int i = i0; i <= i1; i++) {
        const double d = std::hypot(i * spec.resolution - half - b.x, j * spec.resolution - half - b.y);
        if (d < b.radius) {
          const double hgt = 0.8 * std::sqrt(b.radius * b.radius - d * d);
          float& cell = h_[static_cast<size_t>(j) * n_ + i];
          cell = std::max(cell, static_cast<float>(gridSample(h_, b.x, b.y) + hgt));
        }
      }
  }
  shade_.assign(h_.size(), 0.f);
  computeShade(0, 0, n_ - 1, n_ - 1);
}

void Terrain::computeShade(int x0, int y0, int x1, int y1) {
  const double el = spec_.sunElevationDeg * M_PI / 180, az = spec_.sunAzimuthDeg * M_PI / 180;
  const double sx = std::cos(el) * std::cos(az), sy = std::cos(el) * std::sin(az), sz = std::sin(el);
  const double res = spec_.resolution;
  const double tanEl = std::tan(el);
  const int maxSteps = 120;
  const float maxH = *std::max_element(h_.begin(), h_.end());
  for (int j = std::max(1, y0); j <= std::min(n_ - 2, y1); j++)
    for (int i = std::max(1, x0); i <= std::min(n_ - 2, x1); i++) {
      const size_t idx = static_cast<size_t>(j) * n_ + i;
      const double dzdx = (h_[idx + 1] - h_[idx - 1]) / (2 * res);
      const double dzdy = (h_[idx + n_] - h_[idx - n_]) / (2 * res);
      const double nl = std::sqrt(dzdx * dzdx + dzdy * dzdy + 1);
      double lambert = (-dzdx * sx - dzdy * sy + sz) / nl;
      lambert = std::max(0.0, lambert);
      // March towards the sun to find cast shadows, with growing steps.
      double lit = 1;
      double dist = res;
      for (int s = 0; s < maxSteps && lambert > 0; s++) {
        const double px = i + std::cos(az) * dist / res, py = j + std::sin(az) * dist / res;
        if (px < 0 || py < 0 || px >= n_ - 1 || py >= n_ - 1) break;
        const double rayZ = h_[idx] + dist * tanEl + 0.02;
        if (rayZ > maxH) break;  // above every peak: nothing can block the sun
        const double hz = h_[static_cast<size_t>(py) * n_ + static_cast<size_t>(px)];
        if (hz > rayZ) {
          lit = 0;
          break;
        }
        dist += res * (1 + s * 0.08);
      }
      // Earthshine/scatter keeps shadows from being pure black.
      shade_[idx] = static_cast<float>(0.06 + 0.94 * lambert * lit / sz * 0.75);
    }
}

double Terrain::gridSample(const std::vector<float>& g, double x, double y) const {
  const double half = spec_.size / 2;
  double gx = std::clamp((x + half) / spec_.resolution, 0.0, n_ - 1.001);
  double gy = std::clamp((y + half) / spec_.resolution, 0.0, n_ - 1.001);
  const int ix = static_cast<int>(gx), iy = static_cast<int>(gy);
  const double fx = gx - ix, fy = gy - iy;
  const size_t i = static_cast<size_t>(iy) * n_ + ix;
  const double a = g[i] + (g[i + 1] - g[i]) * fx;
  const double b = g[i + n_] + (g[i + n_ + 1] - g[i + n_]) * fx;
  return a + (b - a) * fy;
}

double Terrain::height(double x, double y) const { return gridSample(h_, x, y); }
double Terrain::shade(double x, double y) const { return gridSample(shade_, x, y); }

double Terrain::albedo(double x, double y, double footprint) const {
  // Octaves from 6 m down to 2 cm; each fades out once it gets close to the pixel size.
  double a = 0.55, wsum = 0;
  double wavelength = 6.0, amp = 0.22;
  for (int o = 0; o < 9; o++, wavelength *= 0.5, amp *= 0.8) {
    const double w = std::clamp((wavelength / footprint - 2.0) / 2.0, 0.0, 1.0);
    if (w <= 0) break;
    a += w * amp * (valueNoise(x / wavelength, y / wavelength, spec_.seed * 31 + o) - 0.5);
    wsum += w;
  }
  (void)wsum;
  return std::clamp(a, 0.05, 1.0);
}

void Terrain::siteQuality(double x, double y, double radius, double& slopeDeg, double& roughness) const {
  // Least-squares plane through samples on a disc.
  double sxx = 0, sxy = 0, syy = 0, sxz = 0, syz = 0, sz = 0;
  int n = 0;
  std::vector<double> zs;
  const int k = 6;
  for (int j = -k; j <= k; j++)
    for (int i = -k; i <= k; i++) {
      const double dx = radius * i / k, dy = radius * j / k;
      if (dx * dx + dy * dy > radius * radius) continue;
      const double z = height(x + dx, y + dy);
      sxx += dx * dx; sxy += dx * dy; syy += dy * dy;
      sxz += dx * z; syz += dy * z; sz += z;
      n++;
      zs.push_back(z);
    }
  const double det = sxx * syy - sxy * sxy;
  const double a = (sxz * syy - syz * sxy) / det, b = (syz * sxx - sxz * sxy) / det;
  const double c = sz / n;
  slopeDeg = std::atan(std::hypot(a, b)) * 180 / M_PI;
  roughness = 0;
  int idx = 0;
  for (int j = -k; j <= k; j++)
    for (int i = -k; i <= k; i++) {
      const double dx = radius * i / k, dy = radius * j / k;
      if (dx * dx + dy * dy > radius * radius) continue;
      roughness = std::max(roughness, std::abs(zs[idx++] - (c + a * dx + b * dy)));
    }
}

void Terrain::addBlock(double x0, double y0, double x1, double y1, double hgt) {
  const double half = spec_.size / 2;
  const int i0 = std::max(0, static_cast<int>((x0 + half) / spec_.resolution));
  const int i1 = std::min(n_ - 1, static_cast<int>((x1 + half) / spec_.resolution));
  const int j0 = std::max(0, static_cast<int>((y0 + half) / spec_.resolution));
  const int j1 = std::min(n_ - 1, static_cast<int>((y1 + half) / spec_.resolution));
  float top = -1e9f;
  for (int j = j0; j <= j1; j++)
    for (int i = i0; i <= i1; i++) top = std::max(top, h_[static_cast<size_t>(j) * n_ + i]);
  top += static_cast<float>(hgt);
  for (int j = j0; j <= j1; j++)
    for (int i = i0; i <= i1; i++) h_[static_cast<size_t>(j) * n_ + i] = top;
  const int pad = 1 + static_cast<int>(hgt / spec_.resolution / std::tan(spec_.sunElevationDeg * M_PI / 180));
  computeShade(i0 - pad, j0 - pad, i1 + pad, j1 + pad);
}

}  // namespace so::sim
