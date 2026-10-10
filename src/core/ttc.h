#pragma once
// Time-to-contact from image expansion.
//
// Uses the "direct" method of Horn, Fang & Masaki (2007), "Time to Contact
// Relative to a Planar Surface": no feature tracking, no flow field, and no
// knowledge of altitude or scale. When a camera approaches a surface, every
// image point moves away from the centre at a rate proportional to its
// distance from the centre:
//
//     u = C*x + A,   v = C*y + B,   C = V/Z = 1/TTC
//
// Substituting into brightness constancy (Ix*u + Iy*v + It = 0) gives a
// linear least-squares problem in (A, B, C) with one equation per pixel.
// A and B absorb sideways drift; C is the expansion rate. We solve it
// coarse-to-fine with warp-and-refine iterations so the larger motions near
// touchdown don't break the linearisation.
#include <deque>
#include <optional>
#include <vector>

#include "image.h"

namespace so {

struct ExpansionFit {
  double c = 0;           // fractional scale change between frames (dt/TTC)
  double tx = 0, ty = 0;  // image translation, pixels
  double fitQuality = 0;  // 0..1, share of brightness change the model explains
  double texture = 0;     // mean squared radial gradient (can the camera see anything?)
};

struct FitOptions {
  double windowFraction = 1.0;  // centred fraction of the image to use
  int levels = 2;
  int iterations = 3;
  // Optional explicit window in pixels (overrides windowFraction when x1 > x0).
  int x0 = 0, y0 = 0, x1 = -1, y1 = -1;
  // Starting guess, e.g. the global fit when refining one cell.
  double initC = 0, initTx = 0, initTy = 0;
};

std::optional<ExpansionFit> fitExpansion(const GrayImage& prev, const GrayImage& curr,
                                         const FitOptions& opts = {});

// Per-cell depth relative to the image as a whole. After warping by the
// global fit, a cell at a different depth is left with a small residual
// motion along the direction it was expected to move: both expansion
// (c*x) and sideways parallax (t) scale with 1/depth, so
//     residual = (rho - 1) * expected,   rho = Z_global / Z_cell.
struct CellFit {
  double rho = 1;         // > 1: closer than average (rock); < 1: farther (hole)
  double confidence = 0;  // 0..1, from expected motion and texture
  double contrast = 0;    // intensity std / image median
  double shadow = 0;      // fraction of pixels much darker than the image median
};
std::vector<CellFit> fitCells(const GrayImage& prev, const GrayImage& curr, const ExpansionFit& global, int cols,
                              int rows);

struct TTCEstimate {
  double t = 0;
  std::optional<double> ttc;  // seconds to contact; empty if not approaching
  double rate = 0;            // raw expansion rate, 1/s
  double smoothedRate = 0;    // 1/s
  double confidence = 0;      // 0..1
  int baseline = 1;           // frames between compared images
  double tx = 0, ty = 0;
};

struct TTCTrackerOptions {
  double targetMotionPx = 1.0;  // pixel motion at the window edge we aim for
  int maxBaseline = 12;
  double smoothing = 0.25;      // seconds
  double windowFraction = 0.6;  // centre of the image, roughly the rangefinder's footprint
  double minTexture = 0.02;
};

// Wraps fitExpansion with a frame history so slow approaches (a stepper rig
// moving a few cm/s) still produce measurable motion: it compares against an
// older frame when the per-frame expansion is tiny.
class TTCTracker {
 public:
  explicit TTCTracker(TTCTrackerOptions opts = {}) : opts_(opts) {}
  void reset();
  std::optional<TTCEstimate> push(const GrayImage& img, double t);
  // The older frame and fit behind the most recent estimate (for hazard mapping).
  const GrayImage& lastReference() const { return lastRef_; }
  const ExpansionFit& lastFit() const { return lastFit_; }
  double lastDt() const { return lastDt_; }

 private:
  struct Frame {
    double t;
    GrayImage img;
  };
  TTCTrackerOptions opts_;
  std::deque<Frame> frames_;
  double rate_ = 0;
  bool hasRate_ = false;
  GrayImage lastRef_;
  ExpansionFit lastFit_;
  double lastDt_ = 0;
};

}  // namespace so
