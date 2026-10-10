#include "hazard.h"

#include <algorithm>
#include <cmath>

namespace so {

const HazardMap& HazardMapper::update(const GrayImage& prev, const GrayImage& curr, double c, double tx, double ty,
                                      double dt) {
  const int cols = p_.cols, rows = p_.rows, n = cols * rows;
  if (!map_.valid || map_.cols != cols || map_.rows != rows) {
    map_ = {};
    map_.cols = cols;
    map_.rows = rows;
    map_.score.assign(n, 0.5);
    map_.relHeight.assign(n, 0);
    map_.slopeDeg.assign(n, 0);
    map_.roughness.assign(n, 0);
  }
  const int cw = curr.width / cols, ch = curr.height / rows;

  ExpansionFit global;
  global.c = c;
  global.tx = tx;
  global.ty = ty;
  const std::vector<CellFit> cells = fitCells(prev, curr, global, cols, rows);

  // Median contrast is "normal ground"; rougher than that is suspicious.
  std::vector<double> sorted;
  for (const auto& cell : cells) sorted.push_back(cell.contrast);
  std::nth_element(sorted.begin(), sorted.begin() + n / 2, sorted.end());
  const double medContrast = std::max(1e-3, sorted[n / 2]);

  // Relative height of each cell as a fraction of altitude (+ = sticks up).
  // Each new measurement is folded in according to its confidence.
  const double alpha = 1 - std::exp(-dt / p_.smoothing);
  for (int i = 0; i < n; i++) {
    const double rel = std::clamp(1 - 1 / std::max(cells[i].rho, 0.2), -0.5, 0.5);
    // Cells the camera can't currently judge (no texture, e.g. in shadow)
    // fade back to "level" instead of keeping stale readings around.
    const double conf = cells[i].confidence;
    map_.relHeight[i] += alpha * (conf * (rel - map_.relHeight[i]) - (1 - conf) * 0.5 * map_.relHeight[i]);
  }
  // Local relief: how far a cell sticks out from its neighbours. Comparing
  // with the whole image would flag every cell when the view spans two
  // levels (a cliff edge); a rock stands out from what surrounds it.
  std::vector<double> relief(n, 0);
  for (int r = 0; r < rows; r++)
    for (int k = 0; k < cols; k++) {
      double nb[9];
      int cnt = 0;
      for (int dr = -1; dr <= 1; dr++)
        for (int dk = -1; dk <= 1; dk++) {
          const int rr = r + dr, kk = k + dk;
          if ((dr || dk) && rr >= 0 && rr < rows && kk >= 0 && kk < cols) nb[cnt++] = map_.relHeight[rr * cols + kk];
        }
      std::nth_element(nb, nb + cnt / 2, nb + cnt);
      relief[r * cols + k] = map_.relHeight[r * cols + k] - nb[cnt / 2];
    }

  // Slope from a plane fit to inverse depth over each 3x3 neighbourhood:
  // a ground plane tilted by theta changes rho by tan(theta)/f per pixel.
  for (int r = 0; r < rows; r++)
    for (int k = 0; k < cols; k++) {
      double sx = 0, sy = 0, sxx = 0, syy = 0, sxr = 0, syr = 0, sr = 0;
      int cnt = 0;
      for (int dr = -1; dr <= 1; dr++)
        for (int dk = -1; dk <= 1; dk++) {
          const int rr = r + dr, kk = k + dk;
          if (rr < 0 || rr >= rows || kk < 0 || kk >= cols) continue;
          const double px = dk * cw, py = dr * ch;
          const double rho = 1 / (1 - map_.relHeight[rr * cols + kk]);
          sx += px; sy += py; sxx += px * px; syy += py * py;
          sxr += px * rho; syr += py * rho; sr += rho;
          cnt++;
        }
      const double gx = (sxr - sx * sr / cnt) / std::max(1e-9, sxx - sx * sx / cnt);
      const double gy = (syr - sy * sr / cnt) / std::max(1e-9, syy - sy * sy / cnt);
      const double slope = std::atan(std::hypot(gx, gy) * p_.focalPx) * 180 / M_PI;
      const int i = r * cols + k;
      map_.slopeDeg[i] += alpha * (slope - map_.slopeDeg[i]);
      // Partly shadowed cells are rocks or crater rims casting shadows. A
      // fully dark cell is just in shadow: we can't judge it, so it's never
      // picked as a site, but it isn't painted as a rock field either.
      // Next to a fully dark cell, a half-dark cell is the edge of a large
      // shadow (a cliff or crater wall), not a rock: treat it like the shadow.
      const double sh = cells[i].shadow;
      bool shadowEdge = false;
      for (int dr = -1; dr <= 1; dr++)
        for (int dk = -1; dk <= 1; dk++) {
          const int rr = r + dr, kk = k + dk;
          if (rr >= 0 && rr < rows && kk >= 0 && kk < cols && cells[rr * cols + kk].shadow > 0.8) shadowEdge = true;
        }
      const double rough =
          shadowEdge ? 0.0 : std::max(0.0, cells[i].contrast / medContrast - 1) + 2 * std::min(sh, 1 - sh);
      map_.roughness[i] += alpha * (rough - map_.roughness[i]);
      double s = std::max({std::abs(relief[i]) / p_.maxRelHeight, map_.slopeDeg[i] / p_.maxSafeSlopeDeg,
                           map_.roughness[i] / 0.6});
      if (sh > 0.8 || (shadowEdge && sh > 0.2)) s = std::max(s, 0.55);
      map_.score[i] = std::clamp(s, 0.0, 1.0);
    }

  // Landing site: a cell whose whole neighbourhood is safe (the lander has
  // legs), preferring the centre so we don't divert further than needed.
  double best = 1e9;
  map_.siteFound = false;
  for (int r = 0; r < rows; r++)
    for (int k = 0; k < cols; k++) {
      double worst = 0;
      for (int dr = -1; dr <= 1; dr++)
        for (int dk = -1; dk <= 1; dk++) {
          const int rr = std::clamp(r + dr, 0, rows - 1), kk = std::clamp(k + dk, 0, cols - 1);
          worst = std::max(worst, map_.score[rr * cols + kk] * (dr == 0 && dk == 0 ? 1.0 : 0.7));
        }
      const double nx = (k + 0.5) / cols * 2 - 1, ny = (r + 0.5) / rows * 2 - 1;
      const double cost = worst + p_.centrePenalty * std::hypot(nx, ny);
      if (cost < best) {
        best = cost;
        map_.siteCol = k;
        map_.siteRow = r;
        map_.siteX = nx;
        map_.siteY = ny;
        map_.siteFound = worst < p_.safeThreshold;
      }
    }
  map_.valid = true;
  return map_;
}

}  // namespace so
