#pragma once
// Drawing helpers for the visualizer: camera feed with hazard overlay, the
// side-on profile of both landers, plots, sensor health and the event log.
#include <SDL3/SDL.h>

#include <optional>
#include <vector>

#include "core/fusion.h"
#include "core/hazard.h"
#include "core/image.h"
#include "imgui.h"
#include "sim/simulation.h"

namespace so::app {

namespace colors {
inline const ImVec4 so{0.30f, 0.86f, 0.64f, 1.f};       // Second Opinion
inline const ImVec4 base{0.97f, 0.47f, 0.30f, 1.f};     // baseline
inline const ImVec4 truth{0.80f, 0.82f, 0.86f, 1.f};
inline const ImVec4 range{0.98f, 0.82f, 0.30f, 1.f};    // rangefinder
inline const ImVec4 camera{0.62f, 0.55f, 1.0f, 1.f};    // camera estimate
inline const ImVec4 dim{0.55f, 0.58f, 0.64f, 1.f};
inline const ImVec4 good{0.36f, 0.85f, 0.45f, 1.f};
inline const ImVec4 warn{0.98f, 0.76f, 0.28f, 1.f};
inline const ImVec4 bad{0.96f, 0.36f, 0.36f, 1.f};
}  // namespace colors

// Streaming SDL texture for a grayscale image.
class GrayTexture {
 public:
  ~GrayTexture();
  void update(SDL_Renderer* renderer, const GrayImage& img);
  SDL_Texture* texture() const { return tex_; }
  bool valid() const { return tex_ != nullptr; }

 private:
  SDL_Texture* tex_ = nullptr;
  int w_ = 0, h_ = 0;
  std::vector<uint8_t> rgba_;
};

struct CameraOverlay {
  const HazardMap* hazard = nullptr;
  bool showHazard = true;
  std::optional<double> ttc;
  double confidence = 0;
  bool siteVisible = false;
  double siteNX = 0, siteNY = 0;  // -1..1
  bool rangeOk = true;
};

void drawCameraView(const GrayTexture& tex, ImVec2 size, const CameraOverlay& ov);
void drawProfile(const sim::Simulation& sim, ImVec2 size);
void drawAltitudePlot(const sim::Simulation& sim, float height);
void drawTTCPlot(const sim::Simulation& sim, float height);
void drawHealth(const FusionOutput& nav, bool hasCamera);
void drawEvents(const char* id, const std::vector<FusionEvent>& events, float height);
void drawOutcome(const char* who, const ImVec4& color, const sim::Lander& lander);

ImU32 toU32(const ImVec4& c, float alpha = 1.f);

}  // namespace so::app
