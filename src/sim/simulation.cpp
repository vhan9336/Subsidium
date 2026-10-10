#include "simulation.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <limits>

namespace so::sim {
namespace {
constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();

std::string fmt(const char* f, double a, double b = 0) {
  char buf[256];
  std::snprintf(buf, sizeof buf, f, a, b);
  return buf;
}
}  // namespace

const char* toString(Outcome::Kind k) {
  switch (k) {
    case Outcome::Kind::Flying: return "Flying";
    case Outcome::Kind::Landed: return "Landed";
    case Outcome::Kind::Crashed: return "Crashed";
    case Outcome::Kind::Tipped: return "Tipped over";
  }
  return "?";
}

const std::vector<Scenario>& builtinScenarios() {
  static const std::vector<Scenario> all = [] {
    std::vector<Scenario> v;
    {
      Scenario s;
      s.id = "nominal";
      s.title = "Nominal descent";
      s.story = "No faults. Both landers should agree and land. Use the fault buttons to break things live.";
      s.realOutcome = "Control case.";
      s.terrain.seed = 5;
      s.x0 = -30;
      s.vx0 = 3;
      s.altitude0 = 60;
      s.descent0 = 5;
      v.push_back(s);
    }
    {
      Scenario s;
      s.id = "ispace-m1";
      s.title = "ispace Mission 1 (Apr 2023): crater rim";
      s.story =
          "Flying over the rim of Atlas crater, the ground suddenly dropped away and the rangefinder reading jumped. "
          "The software judged the jump abnormal, threw out the correct reading, and believed its own calculated "
          "altitude. It thought it had landed while still about 5 km up, ran out of fuel and crashed.";
      s.realOutcome = "Crashed. Correct altitude reading rejected after a crater rim.";
      s.terrain.size = 400;
      s.terrain.resolution = 0.2;
      s.terrain.seed = 11;
      s.terrain.cliff = true;
      s.terrain.cliffX = 0;
      s.terrain.cliffDepth = 30;
      s.terrain.cliffWidth = 2;
      s.terrain.craters = 90;
      s.x0 = -60;
      s.vx0 = 12;
      s.altitude0 = 70;
      s.descent0 = 6;
      s.cruiseUntilAlt = 20;
      v.push_back(s);
    }
    {
      Scenario s;
      s.id = "ispace-m2";
      s.title = "ispace Resilience (Jun 2025): rangefinder too late";
      s.story =
          "The laser rangefinder degraded and its readings arrived too late. Without a measured altitude the lander "
          "kept descending too fast and could not slow down in time.";
      s.realOutcome = "Crashed. Valid altitude readings came too late to brake.";
      s.terrain.seed = 21;
      s.altitude0 = 80;
      s.descent0 = 7;
      s.x0 = 10;
      s.vx0 = 2;
      s.priorAltError = 25;
      s.faults.push_back({0, {RangeFault::Late, 10}});
      v.push_back(s);
    }
    {
      Scenario s;
      s.id = "im1-odysseus";
      s.title = "Intuitive Machines Odysseus (Feb 2024): no rangefinder";
      s.story =
          "The laser rangefinders were unusable (a safety switch had been left on). The lander came down on "
          "estimated altitude, caught a foot on a slope and tipped over.";
      s.realOutcome = "Landed tipped over on a slope.";
      s.terrain.seed = 31;
      s.terrain.extraCraters.push_back({6, 0, 9, 2.4});
      s.altitude0 = 60;
      s.descent0 = 5;
      s.priorAltError = 12;
      s.faults.push_back({0, {RangeFault::Dropout, 0}});
      v.push_back(s);
    }
    {
      Scenario s;
      s.id = "im2-athena";
      s.title = "Intuitive Machines Athena (Mar 2025): noisy altimeter, rough site";
      s.story =
          "The altimeter gave unreliable readings during descent, and the lander came down in rough terrain inside a "
          "crater and ended up on its side.";
      s.realOutcome = "Landed on its side.";
      s.terrain.seed = 41;
      s.terrain.boulderFields.push_back({0, 0, 7, 70});
      s.altitude0 = 60;
      s.descent0 = 5;
      s.faults.push_back({0, {RangeFault::Noisy, 0.3}});
      v.push_back(s);
    }
    return v;
  }();
  return all;
}

Lander::Lander(Brain b, const Scenario& sc, const Terrain& terrain, uint32_t seed)
    : brain(b), rangefinder(seed + 1), sc_(sc), rng_(seed) {
  x = sc.x0;
  y = sc.y0;
  z = terrain.height(x, y) + sc.altitude0;
  vx = sc.vx0;
  vy = sc.vy0;
  vz = sc.descent0;
  FusionParams p;
  p.initialAltitude = sc.altitude0 + sc.priorAltError;
  so_ = SecondOpinion(p);
  base_ = BaselineEstimator(p);
  HazardParams hp;
  hazardMapper_ = HazardMapper(hp);
  // Same small IMU scale-factor error for both landers.
  velBias_ = 1.01;
}

const std::vector<FusionEvent>& Lander::events() const {
  return brain == Brain::SecondOpinion ? so_.events() : base_.events();
}

void Lander::step(const Terrain& terrain, const CameraModel& cam, double t, double dt) {
  if (outcome.kind != Outcome::Kind::Flying) return;

  // Sensors.
  FusionInput in;
  in.t = t;
  in.range = rangefinder.measure(terrain, x, y, z, t);
  std::normal_distribution<double> N(0, 1);
  in.descentRate = vz * velBias_ + 0.02 * N(rng_);
  if (brain == Brain::SecondOpinion) {
    frame = renderCamera(terrain, cam, x, y, z, rng_);
    ttc = tracker_.push(frame, t);
    in.camera = ttc;
    if (ttc) {
      const ExpansionFit& f = tracker_.lastFit();
      hazard = hazardMapper_.update(tracker_.lastReference(), frame, f.c, f.tx, f.ty, dt);
    }
    nav = so_.update(in);
  } else {
    nav = base_.update(in);
  }

  guidance(t, dt, cam);

  // Dynamics.
  const double trueAlt = z - terrain.height(x, y);
  Sample s{};
  s.t = t;
  s.x = x;
  s.z = z;
  s.trueAlt = trueAlt;
  s.estAlt = nav.altitude;
  s.range = in.range.value_or(kNaN);
  s.cameraAlt = nav.cameraAltitude.value_or(kNaN);
  s.trueTTC = vz > 0.05 ? trueAlt / vz : kNaN;
  s.cameraTTC = nav.cameraTTC.value_or(kNaN);
  s.rangeTTC = nav.rangeTTC.value_or(kNaN);
  s.descent = vz;
  s.rangeHealth = nav.rangeHealth;
  s.cameraHealth = nav.cameraHealth;
  history.push_back(s);

  checkContact(terrain, t);
}

void Lander::guidance(double t, double dt, const CameraModel& cam) {
  const double h = nav.altitude;
  if (engineOn && h <= 0.15) {
    // The navigation thinks we are down: cut the engine.
    engineOn = false;
  }

  double az = cfg_.gravity;  // downward acceleration
  if (engineOn) {
    const double vTarget = h > 3 ? std::clamp(0.15 * h, 1.0, 12.0) : 0.8;
    const double want = (vTarget - vz) / 0.8;
    az = std::clamp(want, -cfg_.maxUpAccel, cfg_.gravity);
  }
  vz += az * dt;

  // Landing-site selection from the camera's hazard map.
  if (brain == Brain::SecondOpinion && sc_.hazardAvoidance && hazard.valid && h > 8 && h < 40 &&
      t - lastSiteUpdate_ > 1.0) {
    lastSiteUpdate_ = t;
    const double pxPerM = cam.focalPx / std::max(h, 0.1);
    bool keep = false;
    if (siteLocked) {
      // Is the current target still in view and still safe?
      const double nx = (siteX - x) * pxPerM / (cam.width / 2.0);
      const double ny = (siteY - y) * pxPerM / (cam.height / 2.0);
      if (std::abs(nx) < 1 && std::abs(ny) < 1) {
        const int k = std::clamp(static_cast<int>((nx + 1) / 2 * hazard.cols), 0, hazard.cols - 1);
        const int r = std::clamp(static_cast<int>((ny + 1) / 2 * hazard.rows), 0, hazard.rows - 1);
        keep = hazard.score[r * hazard.cols + k] < 0.5;
      }
    }
    if (!keep && hazard.siteFound) {
      siteX = x + hazard.siteX * (cam.width / 2.0) / pxPerM;
      siteY = y + hazard.siteY * (cam.height / 2.0) / pxPerM;
      siteLocked = true;
    }
  }

  // Horizontal: cruise, then either stop or fly to the chosen site.
  double vxT = 0, vyT = 0;
  if (h > sc_.cruiseUntilAlt) {
    vxT = sc_.vx0;
    vyT = sc_.vy0;
  } else if (siteLocked && engineOn) {
    vxT = std::clamp(0.4 * (siteX - x), -3.0, 3.0);
    vyT = std::clamp(0.4 * (siteY - y), -3.0, 3.0);
  }
  if (!engineOn) {
    vxT = vx;
    vyT = vy;
  }
  const double maxDv = cfg_.maxLatAccel * dt;
  vx += std::clamp(vxT - vx, -maxDv, maxDv);
  vy += std::clamp(vyT - vy, -maxDv, maxDv);

  x += vx * dt;
  y += vy * dt;
  z -= vz * dt;
}

void Lander::checkContact(const Terrain& terrain, double t) {
  const double ground = terrain.height(x, y);
  if (!engineOn && outcome.cutoffAltitude < 0) outcome.cutoffAltitude = std::max(0.0, z + vz * 0.05 - ground);
  if (z > ground) {
    if (t > 180) {
      outcome.kind = Outcome::Kind::Crashed;
      outcome.text = "Ran out of fuel hovering.";
    }
    return;
  }
  z = ground;
  outcome.impactSpeed = std::hypot(vz, 0.3 * std::hypot(vx, vy));
  terrain.siteQuality(x, y, cfg_.footprint, outcome.slopeDeg, outcome.roughness);
  std::string prefix;
  if (outcome.cutoffAltitude > 0.5)
    prefix = fmt("Thought it had landed %.1f m up and cut the engine. ", outcome.cutoffAltitude);
  if (vz > cfg_.safeImpact) {
    outcome.kind = Outcome::Kind::Crashed;
    outcome.text = prefix + fmt("Hit the ground at %.1f m/s.", vz);
  } else if (outcome.slopeDeg > cfg_.maxSlopeDeg || outcome.roughness > cfg_.maxRoughness) {
    outcome.kind = Outcome::Kind::Tipped;
    outcome.text = prefix + fmt("Touched down at %.1f m/s on a %.0f deg slope", vz, outcome.slopeDeg) +
                   fmt(" with %.2f m rocks and tipped over.", outcome.roughness);
  } else {
    outcome.kind = Outcome::Kind::Landed;
    outcome.text = prefix + fmt("Landed at %.1f m/s on a %.0f deg slope.", vz, outcome.slopeDeg);
  }
  vz = vx = vy = 0;
}

Simulation::Simulation(const Scenario& sc, uint32_t seed) : sc_(sc) {
  terrain_ = std::make_unique<Terrain>(sc_.terrain);
  landers_[0] = std::make_unique<Lander>(Brain::SecondOpinion, sc_, *terrain_, seed);
  landers_[1] = std::make_unique<Lander>(Brain::Baseline, sc_, *terrain_, seed);
}

void Simulation::step() {
  while (nextFault_ < sc_.faults.size() && sc_.faults[nextFault_].t <= t_) setFault(sc_.faults[nextFault_++].fault);
  for (auto& l : landers_) l->step(*terrain_, cam_, t_, dt_);
  t_ += dt_;
}

bool Simulation::finished() const {
  return landers_[0]->outcome.kind != Outcome::Kind::Flying && landers_[1]->outcome.kind != Outcome::Kind::Flying;
}

void Simulation::setFault(RangeFaultState f) {
  for (auto& l : landers_) l->rangefinder.fault = f;
}

void Simulation::dropBlock(double heightFraction) {
  const Lander& l = *landers_[0];
  const double alt = l.z - terrain_->height(l.x, l.y);
  const double hgt = std::max(0.3, heightFraction * alt);
  const double half = std::max(4.0, 0.4 * alt);
  terrain_->addBlock(l.x - half, l.y - half, l.x + half, l.y + half, hgt);
}

}  // namespace so::sim
