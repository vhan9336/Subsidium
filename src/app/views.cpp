#include "views.h"

#include <algorithm>
#include <cmath>
#include <cstdio>

#include "implot.h"

namespace so::app {

ImU32 toU32(const ImVec4& c, float alpha) { return ImGui::GetColorU32(ImVec4(c.x, c.y, c.z, c.w * alpha)); }

GrayTexture::~GrayTexture() {
  if (tex_) SDL_DestroyTexture(tex_);
}

void GrayTexture::update(SDL_Renderer* renderer, const GrayImage& img) {
  if (img.empty()) return;
  if (!tex_ || w_ != img.width || h_ != img.height) {
    if (tex_) SDL_DestroyTexture(tex_);
    tex_ = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA32, SDL_TEXTUREACCESS_STREAMING, img.width, img.height);
    SDL_SetTextureScaleMode(tex_, SDL_SCALEMODE_LINEAR);
    w_ = img.width;
    h_ = img.height;
  }
  rgba_.resize(img.data.size() * 4);
  for (size_t i = 0; i < img.data.size(); i++) {
    const uint8_t v = static_cast<uint8_t>(std::clamp(img.data[i], 0.f, 1.f) * 255);
    rgba_[4 * i] = rgba_[4 * i + 1] = rgba_[4 * i + 2] = v;
    rgba_[4 * i + 3] = 255;
  }
  SDL_UpdateTexture(tex_, nullptr, rgba_.data(), w_ * 4);
}

void drawCameraView(const GrayTexture& tex, ImVec2 size, const CameraOverlay& ov) {
  const ImVec2 p0 = ImGui::GetCursorScreenPos();
  const ImVec2 p1(p0.x + size.x, p0.y + size.y);
  ImDrawList* dl = ImGui::GetWindowDrawList();
  if (tex.valid())
    dl->AddImage((ImTextureID)(intptr_t)tex.texture(), p0, p1);
  else
    dl->AddRectFilled(p0, p1, IM_COL32(20, 22, 26, 255));

  if (ov.showHazard && ov.hazard && ov.hazard->valid) {
    const HazardMap& h = *ov.hazard;
    const float cw = size.x / h.cols, ch = size.y / h.rows;
    for (int r = 0; r < h.rows; r++)
      for (int k = 0; k < h.cols; k++) {
        const double s = h.score[r * h.cols + k];
        const ImVec2 a(p0.x + k * cw, p0.y + r * ch), b(a.x + cw, a.y + ch);
        if (s > 0.5)
          dl->AddRectFilled(a, b, toU32(colors::bad, static_cast<float>(0.15 + 0.35 * (s - 0.5) / 0.5)));
        dl->AddRect(a, b, IM_COL32(255, 255, 255, 18));
      }
    if (h.siteFound) {
      const ImVec2 a(p0.x + h.siteCol * cw, p0.y + h.siteRow * ch);
      dl->AddRect(a, ImVec2(a.x + cw, a.y + ch), toU32(colors::good, 0.8f), 0, 0, 2);
    }
  }
  // Landing target the guidance is flying to.
  if (ov.siteVisible) {
    const ImVec2 c(p0.x + (static_cast<float>(ov.siteNX) + 1) / 2 * size.x,
                   p0.y + (static_cast<float>(ov.siteNY) + 1) / 2 * size.y);
    dl->AddCircle(c, 14, toU32(colors::good), 0, 2.5f);
    dl->AddLine(ImVec2(c.x - 20, c.y), ImVec2(c.x - 8, c.y), toU32(colors::good), 2);
    dl->AddLine(ImVec2(c.x + 8, c.y), ImVec2(c.x + 20, c.y), toU32(colors::good), 2);
    dl->AddLine(ImVec2(c.x, c.y - 20), ImVec2(c.x, c.y - 8), toU32(colors::good), 2);
    dl->AddLine(ImVec2(c.x, c.y + 8), ImVec2(c.x, c.y + 20), toU32(colors::good), 2);
    dl->AddText(ImVec2(c.x + 16, c.y - 26), toU32(colors::good), "target");
  }
  // Rangefinder footprint at the image centre.
  const ImVec2 mid((p0.x + p1.x) / 2, (p0.y + p1.y) / 2);
  const ImU32 rc = toU32(ov.rangeOk ? colors::range : colors::bad, 0.9f);
  dl->AddCircle(mid, 6, rc, 0, 2);
  dl->AddLine(ImVec2(mid.x - 12, mid.y), ImVec2(mid.x - 6, mid.y), rc, 1.5f);
  dl->AddLine(ImVec2(mid.x + 6, mid.y), ImVec2(mid.x + 12, mid.y), rc, 1.5f);

  // Readout.
  char buf[96];
  if (ov.ttc)
    std::snprintf(buf, sizeof buf, "time to impact %.1f s   confidence %.0f%%", *ov.ttc, ov.confidence * 100);
  else
    std::snprintf(buf, sizeof buf, "time to impact --   confidence %.0f%%", ov.confidence * 100);
  const ImVec2 ts = ImGui::CalcTextSize(buf);
  dl->AddRectFilled(ImVec2(p0.x + 6, p0.y + 6), ImVec2(p0.x + 14 + ts.x, p0.y + 10 + ts.y), IM_COL32(0, 0, 0, 150), 4);
  dl->AddText(ImVec2(p0.x + 10, p0.y + 8), IM_COL32(255, 255, 255, 230), buf);
  dl->AddRect(p0, p1, IM_COL32(255, 255, 255, 40));
  ImGui::Dummy(size);
}

namespace {

void drawLanderGlyph(ImDrawList* dl, ImVec2 c, float scale, ImU32 col, bool flame) {
  const float w = 9 * scale, h = 7 * scale;
  dl->AddRectFilled(ImVec2(c.x - w, c.y - h), ImVec2(c.x + w, c.y + h * 0.3f), col, 2);
  dl->AddLine(ImVec2(c.x - w * 0.7f, c.y), ImVec2(c.x - w * 1.4f, c.y + h * 1.2f), col, 2);
  dl->AddLine(ImVec2(c.x + w * 0.7f, c.y), ImVec2(c.x + w * 1.4f, c.y + h * 1.2f), col, 2);
  if (flame)
    dl->AddTriangleFilled(ImVec2(c.x - w * 0.35f, c.y + h * 0.3f), ImVec2(c.x + w * 0.35f, c.y + h * 0.3f),
                          ImVec2(c.x, c.y + h * 1.5f), IM_COL32(255, 180, 80, 200));
}

}  // namespace

void drawProfile(const sim::Simulation& sim, ImVec2 size) {
  const sim::Lander& so = sim.secondOpinion();
  const sim::Lander& base = sim.baseline();
  const sim::Terrain& terrain = sim.terrain();
  const ImVec2 p0 = ImGui::GetCursorScreenPos();
  const ImVec2 p1(p0.x + size.x, p0.y + size.y);
  ImDrawList* dl = ImGui::GetWindowDrawList();
  dl->PushClipRect(p0, p1, true);
  dl->AddRectFilledMultiColor(p0, p1, IM_COL32(8, 10, 18, 255), IM_COL32(8, 10, 18, 255), IM_COL32(22, 24, 32, 255),
                              IM_COL32(22, 24, 32, 255));

  // World window: keep both landers in view, slice the terrain along
  // Second Opinion's track (y), x horizontal.
  const double y = so.y;
  const double xMid = (so.x + base.x) / 2;
  const double half = std::max(45.0, std::abs(so.x - base.x) / 2 + 30);
  const double x0 = xMid - half, x1 = xMid + half;
  const int N = 240;
  std::vector<double> gz(N + 1);
  double zMin = 1e9, zMax = -1e9;
  for (int i = 0; i <= N; i++) {
    gz[i] = terrain.height(x0 + (x1 - x0) * i / N, y);
    zMin = std::min(zMin, gz[i]);
    zMax = std::max(zMax, gz[i]);
  }
  const double highest = std::max({so.z, base.z, zMax + 10.0});
  const double top = highest + 0.22 * (highest - zMin) + 4;
  const double bottom = zMin - 0.08 * (top - zMin);
  auto X = [&](double wx) { return p0.x + static_cast<float>((wx - x0) / (x1 - x0)) * size.x; };
  auto Z = [&](double wz) { return p1.y - static_cast<float>((wz - bottom) / (top - bottom)) * size.y; };

  // Ground.
  for (int i = 0; i < N; i++) {
    const float xa = X(x0 + (x1 - x0) * i / N), xb = X(x0 + (x1 - x0) * (i + 1) / N);
    dl->AddQuadFilled(ImVec2(xa, Z(gz[i])), ImVec2(xb, Z(gz[i + 1])), ImVec2(xb, p1.y), ImVec2(xa, p1.y),
                      IM_COL32(70, 72, 78, 255));
    dl->AddLine(ImVec2(xa, Z(gz[i])), ImVec2(xb, Z(gz[i + 1])), IM_COL32(160, 162, 170, 255), 1.5f);
  }

  // Altitude scale.
  const double span = top - bottom;
  const double stepM = span > 150 ? 50 : span > 60 ? 20 : span > 25 ? 10 : 5;
  for (double m = std::ceil(bottom / stepM) * stepM; m < top; m += stepM) {
    dl->AddLine(ImVec2(p0.x, Z(m)), ImVec2(p0.x + 6, Z(m)), IM_COL32(255, 255, 255, 60));
  }

  // Labels go on the outer side of each lander so they stay readable when
  // the landers overlap or drift apart.
  auto drawLander = [&](const sim::Lander& l, const ImVec4& col, const char* label, bool left) {
    const ImU32 c = toU32(col);
    const ImVec2 pos(X(l.x), Z(l.z));
    const bool flying = l.outcome.kind == sim::Outcome::Kind::Flying;
    // Rangefinder beam.
    if (flying) {
      if (l.nav.range)
        dl->AddLine(pos, ImVec2(pos.x, Z(l.z - *l.nav.range)), toU32(colors::range, 0.55f), 1.5f);
      else
        dl->AddLine(pos, ImVec2(pos.x, pos.y + 12), toU32(colors::bad, 0.7f), 1.5f);
      // Where this lander believes the ground is.
      const float believed = Z(l.z - l.nav.altitude);
      dl->AddLine(ImVec2(pos.x - 22, believed), ImVec2(pos.x + 22, believed), c, 2.5f);
      const char* note = &l == &base ? "baseline thinks ground is here" : "Second Opinion thinks ground is here";
      const float nw = ImGui::CalcTextSize(note).x;
      const float nx = std::clamp(left ? pos.x - 28 - nw : pos.x + 28, p0.x + 4, p1.x - nw - 4);
      dl->AddText(ImVec2(nx, believed - 8), toU32(col, 0.9f), note);
    }
    drawLanderGlyph(dl, pos, 1.2f, c, flying && l.engineOn);
    char buf[160];
    const double trueAlt = l.z - terrain.height(l.x, l.y);
    if (flying)
      std::snprintf(buf, sizeof buf, "%s  true %.1f m / thinks %.1f m", label, trueAlt, l.nav.altitude);
    else
      std::snprintf(buf, sizeof buf, "%s: %s", label, sim::toString(l.outcome.kind));
    const float bw = ImGui::CalcTextSize(buf).x;
    dl->AddText(ImVec2(std::clamp(left ? pos.x - 30 - bw : pos.x + 30, p0.x + 4, p1.x - bw - 4), pos.y - 10), c, buf);
  };
  const bool baseOnLeft = base.x <= so.x;
  drawLander(base, colors::base, "Baseline", baseOnLeft);
  drawLander(so, colors::so, "Second Opinion", !baseOnLeft);
  dl->AddText(ImVec2(p0.x + 8, p0.y + 6), IM_COL32(255, 255, 255, 110), "Side view, slice along Second Opinion's track");
  dl->PopClipRect();
  dl->AddRect(p0, p1, IM_COL32(255, 255, 255, 40));
  ImGui::Dummy(size);
}

namespace {

void line(const char* label, const std::vector<sim::Sample>& h, const double sim::Sample::*field, const ImVec4& col,
          float weight = 2.f) {
  if (h.empty()) return;
  ImPlot::SetNextLineStyle(col, weight);
  ImPlot::PlotLine(label, &h[0].t, &(h[0].*field), static_cast<int>(h.size()), 0, 0, sizeof(sim::Sample));
}

}  // namespace

void drawAltitudePlot(const sim::Simulation& sim, float height) {
  const auto& so = sim.secondOpinion().history;
  const auto& base = sim.baseline().history;
  if (ImPlot::BeginPlot("Altitude", ImVec2(-1, height))) {
    // Scale to the true and estimated altitudes; raw sensor glitches
    // (a covered sensor, a camera spike) shouldn't squash the plot.
    double yMax = 10;
    for (const auto* hist : {&so, &base})
      for (const auto& smp : *hist) yMax = std::max({yMax, smp.trueAlt, smp.estAlt});
    ImPlot::SetupAxes("time (s)", "altitude (m)", ImPlotAxisFlags_AutoFit, 0);
    ImPlot::SetupAxisLimits(ImAxis_Y1, -0.03 * yMax, 1.15 * yMax, ImGuiCond_Always);
    ImPlot::SetupLegend(ImPlotLocation_NorthEast);
    line("true altitude", so, &sim::Sample::trueAlt, colors::truth, 1.5f);
    if (!so.empty()) {
      ImPlot::SetNextMarkerStyle(ImPlotMarker_Circle, 1.8f, colors::range, 0);
      ImPlot::PlotScatter("rangefinder", &so[0].t, &so[0].range, static_cast<int>(so.size()), 0, 0, sizeof(sim::Sample));
    }
    line("camera (TTC x speed)", so, &sim::Sample::cameraAlt, colors::camera, 1.5f);
    line("Second Opinion estimate", so, &sim::Sample::estAlt, colors::so, 2.5f);
    line("baseline estimate", base, &sim::Sample::estAlt, colors::base, 2.5f);
    ImVec4 faded = colors::base;
    faded.w = 0.45f;
    line("baseline true altitude", base, &sim::Sample::trueAlt, faded, 1.5f);
    ImPlot::EndPlot();
  }
}

void drawTTCPlot(const sim::Simulation& sim, float height) {
  const auto& so = sim.secondOpinion().history;
  if (ImPlot::BeginPlot("Time to impact", ImVec2(-1, height))) {
    ImPlot::SetupAxes("time (s)", "seconds", ImPlotAxisFlags_AutoFit, 0);
    ImPlot::SetupAxisLimits(ImAxis_Y1, 0, 25, ImGuiCond_Always);
    ImPlot::SetupLegend(ImPlotLocation_NorthEast);
    line("true", so, &sim::Sample::trueTTC, colors::truth, 1.5f);
    line("rangefinder / speed", so, &sim::Sample::rangeTTC, colors::range, 1.5f);
    line("camera (image expansion)", so, &sim::Sample::cameraTTC, colors::camera, 2.f);
    ImPlot::EndPlot();
  }
}

namespace {

ImVec4 statusColor(SensorStatus s) {
  switch (s) {
    case SensorStatus::Ok: return colors::good;
    case SensorStatus::Suspect: return colors::warn;
    case SensorStatus::Failed: return colors::bad;
  }
  return colors::dim;
}

void healthBar(const char* name, double health, SensorStatus status) {
  char overlay[64];
  std::snprintf(overlay, sizeof overlay, "%s  %s", name, toString(status));
  ImGui::PushStyleColor(ImGuiCol_PlotHistogram, statusColor(status));
  ImGui::ProgressBar(static_cast<float>(health), ImVec2(-1, 0), overlay);
  ImGui::PopStyleColor();
}

}  // namespace

void drawHealth(const FusionOutput& nav, bool hasCamera) {
  healthBar("Rangefinder", nav.rangeHealth, nav.rangeStatus);
  if (hasCamera) healthBar("Camera", nav.cameraHealth, nav.cameraStatus);
  ImGui::TextColored(colors::dim, "Altitude from:");
  ImGui::SameLine();
  ImGui::TextUnformatted(toString(nav.source));
  if (!nav.verdict.empty()) {
    ImGui::PushTextWrapPos(0);
    ImGui::TextColored(nav.jumpPending ? colors::warn : colors::truth, "%s", nav.verdict.c_str());
    ImGui::PopTextWrapPos();
  }
}

void drawEvents(const char* id, const std::vector<FusionEvent>& events, float height) {
  ImGui::BeginChild(id, ImVec2(-1, height), ImGuiChildFlags_Borders);
  for (const auto& e : events) {
    ImVec4 c = colors::truth;
    if (e.kind == FusionEvent::Kind::Good) c = colors::good;
    if (e.kind == FusionEvent::Kind::Warn) c = colors::warn;
    if (e.kind == FusionEvent::Kind::Fault) c = colors::bad;
    ImGui::TextColored(colors::dim, "%6.2f", e.t);
    ImGui::SameLine();
    ImGui::PushTextWrapPos(0);
    ImGui::TextColored(c, "%s", e.text.c_str());
    ImGui::PopTextWrapPos();
  }
  if (ImGui::GetScrollY() >= ImGui::GetScrollMaxY() - 4) ImGui::SetScrollHereY(1.0f);
  ImGui::EndChild();
}

void drawOutcome(const char* who, const ImVec4& color, const sim::Lander& l) {
  ImGui::TextColored(color, "%s", who);
  ImGui::SameLine();
  ImVec4 c = colors::dim;
  const char* label = "descending";
  switch (l.outcome.kind) {
    case sim::Outcome::Kind::Flying: break;
    case sim::Outcome::Kind::Landed: c = colors::good; label = "LANDED"; break;
    case sim::Outcome::Kind::Crashed: c = colors::bad; label = "CRASHED"; break;
    case sim::Outcome::Kind::Tipped: c = colors::bad; label = "TIPPED OVER"; break;
  }
  ImGui::TextColored(c, "%s", label);
  if (!l.outcome.text.empty()) {
    ImGui::PushTextWrapPos(0);
    ImGui::TextColored(colors::dim, "%s", l.outcome.text.c_str());
    ImGui::PopTextWrapPos();
  }
}

}  // namespace so::app
