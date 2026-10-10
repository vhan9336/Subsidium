#include "ttc.h"

#include <algorithm>
#include <array>
#include <cmath>

namespace so {
namespace {

struct Window {
  int x0, y0, x1, y1;
};

Window centredWindow(const GrayImage& img, double frac) {
  const int mx = static_cast<int>(std::lround(img.width * (1 - frac) / 2));
  const int my = static_cast<int>(std::lround(img.height * (1 - frac) / 2));
  return {mx, my, img.width - 1 - mx, img.height - 1 - my};
}

// Solve a 3x3 system with Cramer's rule.
std::optional<std::array<double, 3>> solve3(const std::array<double, 9>& m, const std::array<double, 3>& b) {
  const auto [a, bb, c, d, e, f, g, h, i] = m;
  const double det = a * (e * i - f * h) - bb * (d * i - f * g) + c * (d * h - e * g);
  if (std::abs(det) < 1e-12) return std::nullopt;
  const double inv = 1 / det;
  return std::array<double, 3>{
      (b[0] * (e * i - f * h) - bb * (b[1] * i - f * b[2]) + c * (b[1] * h - e * b[2])) * inv,
      (a * (b[1] * i - f * b[2]) - b[0] * (d * i - f * g) + c * (d * b[2] - b[1] * g)) * inv,
      (a * (e * b[2] - b[1] * h) - bb * (d * b[2] - b[1] * g) + b[0] * (d * h - e * g)) * inv};
}

// Warp prev so it lines up with curr. A point at x' in prev appears at
// x = (1+c)*x' + t in curr.
GrayImage warp(const GrayImage& prev, double c, double tx, double ty) {
  GrayImage out(prev.width, prev.height);
  const double cx = (prev.width - 1) / 2.0, cy = (prev.height - 1) / 2.0;
  const double s = 1 / (1 + c);
  for (int y = 0; y < prev.height; y++)
    for (int x = 0; x < prev.width; x++)
      out.at(x, y) = sample(prev, static_cast<float>((x - cx - tx) * s + cx),
                            static_cast<float>((y - cy - ty) * s + cy));
  return out;
}

struct Increment {
  double dc, dtx, dty, texture;
};

// One linearised least-squares step: rows [Ix, Iy, G] . [A, B, C] = -It.
std::optional<Increment> step(const GrayImage& prev, const GrayImage& curr, const Window& win) {
  const int w = curr.width;
  const double cx = (w - 1) / 2.0, cy = (curr.height - 1) / 2.0;
  double sxx = 0, sxy = 0, sxg = 0, syy = 0, syg = 0, sgg = 0, bx = 0, by = 0, bg = 0;
  int n = 0;
  const int x0 = std::max(1, win.x0), x1 = std::min(w - 2, win.x1);
  const int y0 = std::max(1, win.y0), y1 = std::min(curr.height - 2, win.y1);
  const float* P = prev.data.data();
  const float* Q = curr.data.data();
  for (int y = y0; y <= y1; y++) {
    const double ry = y - cy;
    for (int x = x0; x <= x1; x++) {
      const int i = y * w + x;
      const double ix = 0.25 * (Q[i + 1] - Q[i - 1] + P[i + 1] - P[i - 1]);
      const double iy = 0.25 * (Q[i + w] - Q[i - w] + P[i + w] - P[i - w]);
      const double it = Q[i] - P[i];
      const double g = (x - cx) * ix + ry * iy;
      sxx += ix * ix; sxy += ix * iy; sxg += ix * g;
      syy += iy * iy; syg += iy * g; sgg += g * g;
      bx -= ix * it; by -= iy * it; bg -= g * it;
      n++;
    }
  }
  if (n < 16) return std::nullopt;
  const auto sol = solve3({sxx, sxy, sxg, sxy, syy, syg, sxg, syg, sgg}, {bx, by, bg});
  if (!sol) return std::nullopt;
  return Increment{(*sol)[2], (*sol)[0], (*sol)[1], sgg / n};
}

// Normalise two frames with shared statistics so contrast is comparable.
void normalizePair(const GrayImage& a, const GrayImage& b, GrayImage& na, GrayImage& nb) {
  const size_t n = a.data.size();
  double mean = 0;
  for (size_t i = 0; i < n; i++) mean += a.data[i] + b.data[i];
  mean /= 2.0 * n;
  double v = 0;
  for (size_t i = 0; i < n; i++) v += (a.data[i] - mean) * (a.data[i] - mean) + (b.data[i] - mean) * (b.data[i] - mean);
  const double sd = std::sqrt(v / (2.0 * n));
  const double k = sd > 1e-9 ? 1 / sd : 1;
  na = GrayImage(a.width, a.height);
  nb = GrayImage(b.width, b.height);
  for (size_t i = 0; i < n; i++) {
    na.data[i] = static_cast<float>((a.data[i] - mean) * k);
    nb.data[i] = static_cast<float>((b.data[i] - mean) * k);
  }
}

// Mean squared difference over a window, ignoring a border where warps clamp.
double residualEnergy(const GrayImage& a, const GrayImage& b, const Window& w) {
  const int m = 4;
  double s = 0;
  int n = 0;
  for (int y = std::max(m, w.y0); y <= std::min(a.height - 1 - m, w.y1); y++)
    for (int x = std::max(m, w.x0); x <= std::min(a.width - 1 - m, w.x1); x++) {
      const double d = a.at(x, y) - b.at(x, y);
      s += d * d;
      n++;
    }
  return n ? s / n : 0;
}

}  // namespace

std::optional<ExpansionFit> fitExpansion(const GrayImage& prev, const GrayImage& curr, const FitOptions& opts) {
  if (prev.width != curr.width || prev.height != curr.height || prev.empty()) return std::nullopt;
  GrayImage np, nc;
  normalizePair(prev, curr, np, nc);
  std::vector<GrayImage> pp{blur(np)}, pc{blur(nc)};
  for (int l = 1; l < opts.levels; l++) {
    pp.push_back(blur(downsample(pp.back(), 2)));
    pc.push_back(blur(downsample(pc.back(), 2)));
  }

  const bool explicitWin = opts.x1 > opts.x0;
  auto windowAt = [&](int l) {
    if (!explicitWin) return centredWindow(pp[l], opts.windowFraction);
    const int s = 1 << l;
    return Window{opts.x0 / s, opts.y0 / s, opts.x1 / s, opts.y1 / s};
  };
  double c = opts.initC, tx = opts.initTx, ty = opts.initTy, texture = 0;
  for (int l = opts.levels - 1; l >= 0; l--) {
    const double scale = std::pow(2.0, l);
    const Window win = windowAt(l);
    for (int k = 0; k < opts.iterations; k++) {
      const auto inc = step(warp(pp[l], c, tx / scale, ty / scale), pc[l], win);
      if (!inc) return std::nullopt;
      texture = inc->texture;
      // Compose: x = (1+dc)((1+c)x' + t) + dt
      c = (1 + inc->dc) * (1 + c) - 1;
      tx = (1 + inc->dc) * tx + inc->dtx * scale;
      ty = (1 + inc->dc) * ty + inc->dty * scale;
      if (std::abs(inc->dc) < 1e-5 && std::abs(inc->dtx) < 1e-3 && std::abs(inc->dty) < 1e-3) break;
    }
  }
  if (!std::isfinite(c) || c <= -0.9) return std::nullopt;

  const Window w0 = windowAt(0);
  const double raw = residualEnergy(pp[0], pc[0], w0);
  const double resid = residualEnergy(warp(pp[0], c, tx, ty), pc[0], w0);
  ExpansionFit fit;
  fit.c = c;
  fit.tx = tx;
  fit.ty = ty;
  fit.fitQuality = raw > 1e-9 ? std::clamp(1 - resid / raw, 0.0, 1.0) : 0;
  fit.texture = texture;
  return fit;
}

std::vector<CellFit> fitCells(const GrayImage& prev, const GrayImage& curr, const ExpansionFit& global, int cols,
                              int rows) {
  std::vector<CellFit> cells(static_cast<size_t>(cols) * rows);
  if (prev.width != curr.width || prev.height != curr.height || prev.empty()) return cells;
  GrayImage np, nc;
  normalizePair(prev, curr, np, nc);
  const GrayImage bp = blur(np), bc = blur(nc);
  const GrayImage warped = warp(bp, global.c, global.tx, global.ty);

  std::vector<float> sorted = curr.data;
  std::nth_element(sorted.begin(), sorted.begin() + sorted.size() / 2, sorted.end());
  const double median = sorted[sorted.size() / 2];

  const int w = curr.width, cw = curr.width / cols, ch = curr.height / rows;
  const double cx = (w - 1) / 2.0, cy = (curr.height - 1) / 2.0;
  for (int r = 0; r < rows; r++)
    for (int k = 0; k < cols; k++) {
      CellFit& cell = cells[static_cast<size_t>(r) * cols + k];
      const int x0 = std::max(1, k * cw), x1 = std::min(w - 2, (k + 1) * cw - 1);
      const int y0 = std::max(1, r * ch), y1 = std::min(curr.height - 2, (r + 1) * ch - 1);
      double m = 0, m2 = 0, dark = 0;
      double sxx = 0, sxy = 0, syy = 0, bx = 0, by = 0;
      int n = 0;
      for (int y = y0; y <= y1; y++)
        for (int x = x0; x <= x1; x++) {
          const double v = curr.at(x, y);
          m += v;
          m2 += v * v;
          if (v < 0.4 * median) dark++;
          const int i = y * w + x;
          const double ix = 0.25 * (bc.data[i + 1] - bc.data[i - 1] + warped.data[i + 1] - warped.data[i - 1]);
          const double iy = 0.25 * (bc.data[i + w] - bc.data[i - w] + warped.data[i + w] - warped.data[i - w]);
          const double it = bc.data[i] - warped.data[i];
          sxx += ix * ix; sxy += ix * iy; syy += iy * iy;
          bx -= ix * it; by -= iy * it;
          n++;
        }
      if (n == 0) continue;
      m /= n;
      // Normalised by the image median, not the cell mean, so a uniformly
      // dark (shadowed) cell with ordinary noise doesn't look rough.
      cell.contrast = std::sqrt(std::max(0.0, m2 / n - m * m)) / std::max(0.05, median);
      cell.shadow = dark / n;
      const double det = sxx * syy - sxy * sxy;
      if (det < 1e-9) continue;
      const double du = (bx * syy - by * sxy) / det, dv = (by * sxx - bx * sxy) / det;
      // Where this cell was expected to move, in pixels.
      const double xc = (x0 + x1) / 2.0 - cx, yc = (y0 + y1) / 2.0 - cy;
      const double ex = global.c * xc + global.tx, ey = global.c * yc + global.ty;
      const double e2 = ex * ex + ey * ey;
      if (e2 < 1e-4) continue;
      cell.rho = 1 + (du * ex + dv * ey) / e2;
      // Need at least ~0.5 px of expected motion and some texture to judge depth.
      const double texture = std::min(sxx, syy) / n;
      cell.confidence = std::clamp(e2 / 0.25, 0.0, 1.0) * std::clamp(texture / 0.01, 0.0, 1.0);
    }
  return cells;
}

void TTCTracker::reset() {
  frames_.clear();
  rate_ = 0;
  hasRate_ = false;
}

std::optional<TTCEstimate> TTCTracker::push(const GrayImage& img, double t) {
  frames_.push_back({t, img});
  while (static_cast<int>(frames_.size()) > opts_.maxBaseline + 1) frames_.pop_front();
  if (frames_.size() < 2) return std::nullopt;

  // Look far enough back that the window edge moves ~targetMotionPx.
  const double halfDiag = 0.5 * std::hypot(img.width, img.height) * opts_.windowFraction;
  const double frameDt = std::max(1e-3, t - frames_[frames_.size() - 2].t);
  int k = 3;
  if (hasRate_) {
    const double perFrame = std::max(rate_, 1e-6) * frameDt * halfDiag;
    k = static_cast<int>(std::lround(opts_.targetMotionPx / perFrame));
  }
  k = std::clamp(k, 1, std::min<int>(static_cast<int>(frames_.size()) - 1, opts_.maxBaseline));

  const Frame& ref = frames_[frames_.size() - 1 - k];
  const double dt = t - ref.t;
  FitOptions fo;
  fo.windowFraction = opts_.windowFraction;
  const auto fit = fitExpansion(ref.img, img, fo);
  if (!fit || dt <= 0) return std::nullopt;
  lastRef_ = ref.img;
  lastFit_ = *fit;
  lastDt_ = dt;

  // Scale change s = 1+c over dt gives an instantaneous rate of ln(s)/dt.
  const double rate = std::log(1 + fit->c) / dt;
  const double textureOk = std::min(1.0, fit->texture / opts_.minTexture);
  const double confidence = std::clamp(fit->fitQuality * textureOk, 0.0, 1.0);

  // Confidence-weighted exponential smoothing.
  const double alpha = 1 - std::exp(-frameDt / opts_.smoothing);
  if (!hasRate_) {
    rate_ = rate;
    hasRate_ = true;
  } else {
    rate_ += alpha * confidence * (rate - rate_);
  }

  TTCEstimate e;
  e.t = t;
  if (rate_ > 1e-4) e.ttc = 1 / rate_;
  e.rate = rate;
  e.smoothedRate = rate_;
  e.confidence = confidence;
  e.baseline = k;
  e.tx = fit->tx;
  e.ty = fit->ty;
  return e;
}

}  // namespace so
