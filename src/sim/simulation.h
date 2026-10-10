#pragma once
// Runs two identical landers over the same terrain with the same sensor
// faults. One navigates with Second Opinion, the other with the baseline
// logic that rejects jumps and trusts dead reckoning.
#include <memory>
#include <optional>
#include <random>
#include <string>
#include <vector>

#include "../core/fusion.h"
#include "../core/hazard.h"
#include "../core/ttc.h"
#include "sensors.h"
#include "terrain.h"

namespace so::sim {

struct ScenarioFault {
  double t;
  RangeFaultState fault;
};

struct Scenario {
  std::string id;
  std::string title;
  std::string story;        // what happened to the real mission
  std::string realOutcome;  // one line
  TerrainSpec terrain;
  double x0 = 0, y0 = 0;
  double altitude0 = 60;        // above the ground under the lander
  double vx0 = 0, vy0 = 0;      // m/s
  double descent0 = 5;          // m/s, positive down
  double priorAltError = 0;     // navigation's starting error, + = thinks it is higher
  double cruiseUntilAlt = 25;   // keep horizontal speed until this estimated altitude
  bool hazardAvoidance = true;  // Second Opinion may divert to a safer spot
  std::vector<ScenarioFault> faults;
};

const std::vector<Scenario>& builtinScenarios();

enum class Brain { SecondOpinion, Baseline };

struct Outcome {
  enum class Kind { Flying, Landed, Crashed, Tipped };
  Kind kind = Kind::Flying;
  double impactSpeed = 0;
  double slopeDeg = 0;
  double roughness = 0;
  double cutoffAltitude = -1;  // true altitude when the engine was cut, if before contact
  std::string text;
};
const char* toString(Outcome::Kind k);

struct Sample {
  double t;
  double x, z;
  double trueAlt;
  double estAlt;
  double range;      // NaN when missing
  double cameraAlt;  // NaN when unavailable
  double trueTTC, cameraTTC, rangeTTC;  // NaN when unavailable
  double descent;
  double rangeHealth, cameraHealth;
};

struct LanderConfig {
  double gravity = 1.62;
  double maxUpAccel = 3.0;    // net deceleration capability
  double maxLatAccel = 1.5;
  double safeImpact = 3.0;    // m/s
  double maxSlopeDeg = 12;
  double maxRoughness = 0.4;  // m
  double footprint = 2.0;     // m, leg radius
};

class Lander {
 public:
  Lander(Brain brain, const Scenario& sc, const Terrain& terrain, uint32_t seed);
  void step(const Terrain& terrain, const CameraModel& cam, double t, double dt);

  Brain brain;
  double x, y, z, vx, vy, vz;  // vz positive = descending
  bool engineOn = true;
  Outcome outcome;
  Rangefinder rangefinder;
  FusionOutput nav;
  std::optional<TTCEstimate> ttc;
  GrayImage frame;
  HazardMap hazard;
  bool siteLocked = false;
  double siteX = 0, siteY = 0;
  std::vector<Sample> history;
  const std::vector<FusionEvent>& events() const;

 private:
  void guidance(double t, double dt, const CameraModel& cam);
  void checkContact(const Terrain& terrain, double t);
  const Scenario& sc_;
  LanderConfig cfg_;
  SecondOpinion so_;
  BaselineEstimator base_;
  TTCTracker tracker_;
  HazardMapper hazardMapper_;
  std::mt19937 rng_;
  double velBias_;
  double lastSiteUpdate_ = -1e9;
};

class Simulation {
 public:
  explicit Simulation(const Scenario& sc, uint32_t seed = 7);
  void step();
  bool finished() const;
  double time() const { return t_; }
  double dt() const { return dt_; }
  const Scenario& scenario() const { return sc_; }
  const Terrain& terrain() const { return *terrain_; }
  const CameraModel& camera() const { return cam_; }
  Lander& secondOpinion() { return *landers_[0]; }
  Lander& baseline() { return *landers_[1]; }
  const Lander& secondOpinion() const { return *landers_[0]; }
  const Lander& baseline() const { return *landers_[1]; }

  // Live fault injection from the UI (applies to both landers).
  void setFault(RangeFaultState f);
  // Drop a flat block under the landers: the demo's cardboard "crater rim".
  void dropBlock(double heightFraction = 0.3);

 private:
  Scenario sc_;
  std::unique_ptr<Terrain> terrain_;
  CameraModel cam_;
  std::unique_ptr<Lander> landers_[2];
  double t_ = 0, dt_ = 0.05;
  size_t nextFault_ = 0;
};

}  // namespace so::sim
