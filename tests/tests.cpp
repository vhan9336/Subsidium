// Self-contained tests (no framework needed): `ctest` or run so_tests directly.
#include <cmath>
#include <cstdio>
#include <functional>
#include <string>
#include <vector>

#include "core/fusion.h"
#include "core/ttc.h"
#include "sim/simulation.h"

using namespace so;

static int failures = 0;
#define CHECK(cond)                                                       \
  do {                                                                    \
    if (!(cond)) {                                                        \
      std::printf("    FAILED %s:%d: %s\n", __FILE__, __LINE__, #cond);   \
      failures++;                                                         \
    }                                                                     \
  } while (0)
#define CHECK_NEAR(a, b, tol)                                                                       \
  do {                                                                                              \
    const double a_ = (a), b_ = (b);                                                                \
    if (!(std::abs(a_ - b_) <= (tol))) {                                                            \
      std::printf("    FAILED %s:%d: %s = %g, expected %g +- %g\n", __FILE__, __LINE__, #a, a_, b_, \
                  static_cast<double>(tol));                                                        \
      failures++;                                                                                   \
    }                                                                                               \
  } while (0)

// Smooth procedural ground texture and a pinhole camera looking straight down.
static double ground(double X, double Y) {
  return 0.5 + 0.2 * std::sin(X * 1.3 + std::cos(Y * 0.7)) + 0.15 * std::sin(Y * 2.1 + X * 0.4) +
         0.1 * std::sin((X + Y) * 3.7) + 0.05 * std::cos(X * 6.1 - Y * 5.3);
}
static GrayImage render(double Z, double offX = 0, double offY = 0, int w = 160, int h = 120, double f = 140) {
  GrayImage img(w, h);
  for (int y = 0; y < h; y++)
    for (int x = 0; x < w; x++)
      img.at(x, y) = static_cast<float>(ground((x - (w - 1) / 2.0) * Z / f + offX, (y - (h - 1) / 2.0) * Z / f + offY));
  return img;
}

static void testExpansion() {
  const double cases[][2] = {{10, 9.9}, {10, 9.5}, {10, 9}, {3, 2.8}};
  for (auto& c : cases) {
    const auto fit = fitExpansion(render(c[0]), render(c[1]));
    CHECK(fit.has_value());
    if (!fit) continue;
    CHECK_NEAR(fit->c, c[0] / c[1] - 1, 0.005);
    CHECK(fit->fitQuality > 0.9);
  }
}

static void testDrift() {
  const auto fit = fitExpansion(render(10), render(9.8, 0.1, -0.05));
  CHECK(fit.has_value());
  if (!fit) return;
  CHECK_NEAR(fit->c, 10 / 9.8 - 1, 0.005);
  CHECK(std::abs(fit->tx) > 0.5);
}

static void testTracker() {
  TTCTracker tr;
  const double v = 2, dt = 0.05;
  std::optional<TTCEstimate> est;
  for (int i = 0; i < 40; i++) est = tr.push(render(20 - v * i * dt), i * dt);
  const double Z = 20 - v * 39 * dt;
  CHECK(est && est->ttc);
  if (est && est->ttc) CHECK_NEAR(*est->ttc, Z / v, 0.1 * Z / v);
}

// Scripted descent: true altitude h(t), with a camera estimate we control.
static TTCEstimate cam(double ttc, double conf = 0.9) {
  TTCEstimate e;
  e.ttc = ttc;
  e.confidence = conf;
  return e;
}

static void testFusionAcceptsTerrainChange() {
  // Ground drops 30 m at t=2 (crater rim); the camera follows ~0.4 s later.
  SecondOpinion so;
  BaselineEstimator base;
  const double v = 5;
  FusionOutput o, b;
  for (double t = 0; t < 5; t += 0.05) {
    const double h = 60 - v * t + (t >= 2 ? 30 : 0);
    const double hCam = 60 - v * t + (t >= 2.4 ? 30 : 0);
    FusionInput in{t, h, v, cam(hCam / v)};
    o = so.update(in);
    in.camera.reset();
    b = base.update(in);
  }
  const double truth = 60 - v * 4.95 + 30;
  CHECK_NEAR(o.altitude, truth, 1.5);
  CHECK(o.rangeStatus != SensorStatus::Failed);
  CHECK(b.altitude < truth - 20);  // baseline threw the reading away
}

static void testFusionRejectsCoveredSensor() {
  // Sensor covered at t=1: reads 3 cm. Camera and motion say otherwise.
  SecondOpinion so;
  const double v = 0.03;
  FusionOutput o;
  for (double t = 0; t < 6; t += 0.05) {
    const double h = 0.5 - v * t;
    o = so.update({t, t >= 1 ? 0.03 : h, v, cam(h / v)});
  }
  CHECK(o.rangeStatus == SensorStatus::Failed);
  CHECK(o.source == AltSource::Camera);
  CHECK_NEAR(o.altitude, 0.5 - v * 5.95, 0.05);
}

static void testFusionCameraOnlyWithPriorError() {
  // No rangefinder, navigation starts 20 m high: the camera should pull it in.
  FusionParams p;
  p.initialAltitude = 80;
  SecondOpinion so(p);
  const double v = 6;
  FusionOutput o;
  for (double t = 0; t < 6; t += 0.05) {
    const double h = 60 - v * t;
    o = so.update({t, std::nullopt, v, cam(h / v)});
  }
  CHECK_NEAR(o.altitude, 60 - v * 5.95, 2.0);
}

static void testScenarios() {
  using namespace so::sim;
  struct Expect {
    const char* id;
    bool baselineFails;
  };
  const Expect expect[] = {
      {"nominal", false}, {"ispace-m1", true}, {"ispace-m2", true}, {"im1-odysseus", true}, {"im2-athena", true}};
  for (const auto& e : expect) {
    const Scenario* sc = nullptr;
    for (const auto& s : builtinScenarios())
      if (s.id == e.id) sc = &s;
    CHECK(sc != nullptr);
    if (!sc) continue;
    Simulation sim(*sc);
    while (!sim.finished() && sim.time() < 200) sim.step();
    const auto& so = sim.secondOpinion().outcome;
    const auto& base = sim.baseline().outcome;
    std::printf("    %-13s baseline: %-11s | second opinion: %s\n", e.id, toString(base.kind), toString(so.kind));
    CHECK(so.kind == Outcome::Kind::Landed);
    if (e.baselineFails) CHECK(base.kind != Outcome::Kind::Landed);
    else CHECK(base.kind == Outcome::Kind::Landed);
  }
}

int main() {
  const std::vector<std::pair<const char*, std::function<void()>>> tests = {
      {"expansion fit recovers scale change", testExpansion},
      {"expansion fit separates drift", testDrift},
      {"tracker follows time-to-contact", testTracker},
      {"fusion accepts camera-confirmed terrain change", testFusionAcceptsTerrainChange},
      {"fusion rejects a covered rangefinder", testFusionRejectsCoveredSensor},
      {"fusion corrects prior error with camera only", testFusionCameraOnlyWithPriorError},
      {"scenarios: Second Opinion lands, baseline repeats history", testScenarios},
  };
  for (const auto& [name, fn] : tests) {
    const int before = failures;
    std::printf("  %s\n", name);
    fn();
    std::printf("  -> %s\n", failures == before ? "ok" : "FAILED");
  }
  std::printf("%s (%d failure%s)\n", failures ? "FAILED" : "PASSED", failures, failures == 1 ? "" : "s");
  return failures ? 1 : 0;
}
