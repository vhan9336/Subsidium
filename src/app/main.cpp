// Second Opinion visualizer.
//
//   second_opinion [--scenario <id>] [--live] [--camera /dev/video0] [--serial /dev/ttyACM0]
//                  [--screenshot out.png --seconds N]
//
// Simulation tab: replays real lander failures with two identical landers,
// one using Second Opinion and one using the baseline logic. Live rig tab:
// runs the same estimator on a webcam + Arduino ultrasonic rig.
#include <SDL3/SDL.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <future>
#include <memory>
#include <string>

#include "imgui.h"
#include "imgui_impl_sdl3.h"
#include "imgui_impl_sdlrenderer3.h"
#include "implot.h"
#include "live/rig.h"
#include "sim/simulation.h"
#include "views.h"

using namespace so;
using namespace so::app;

namespace {

struct SimTab {
  int scenario = 0;
  std::unique_ptr<sim::Simulation> sim;
  std::future<std::unique_ptr<sim::Simulation>> loading;
  bool playing = true;
  float speed = 1.0f;
  double accumulator = 0;
  bool showHazard = true;
  GrayTexture camTex;

  void restart() {
    const sim::Scenario sc = sim::builtinScenarios()[scenario];
    sim.reset();
    accumulator = 0;
    loading = std::async(std::launch::async, [sc] { return std::make_unique<sim::Simulation>(sc); });
  }
  bool ready() {
    if (loading.valid() && loading.wait_for(std::chrono::seconds(0)) == std::future_status::ready) sim = loading.get();
    return sim != nullptr;
  }
};

struct LiveTab {
  live::Rig rig;
  char serialPath[64] = "/dev/ttyACM0";
  char cameraPath[64] = "/dev/video0";
  int speedMm = 20;
  GrayTexture camTex;
};

void setupStyle() {
  ImGui::StyleColorsDark();
  ImGuiStyle& s = ImGui::GetStyle();
  s.WindowRounding = 0;
  s.ChildRounding = 6;
  s.FrameRounding = 5;
  s.GrabRounding = 5;
  s.FramePadding = ImVec2(10, 6);
  s.ItemSpacing = ImVec2(10, 8);
  s.WindowPadding = ImVec2(14, 12);
  ImVec4* c = s.Colors;
  c[ImGuiCol_WindowBg] = ImVec4(0.06f, 0.07f, 0.09f, 1);
  c[ImGuiCol_ChildBg] = ImVec4(0.09f, 0.10f, 0.13f, 1);
  c[ImGuiCol_FrameBg] = ImVec4(0.14f, 0.15f, 0.19f, 1);
  c[ImGuiCol_Button] = ImVec4(0.17f, 0.19f, 0.24f, 1);
  c[ImGuiCol_ButtonHovered] = ImVec4(0.24f, 0.27f, 0.34f, 1);
  c[ImGuiCol_ButtonActive] = ImVec4(0.30f, 0.86f, 0.64f, 0.6f);
  c[ImGuiCol_Header] = ImVec4(0.17f, 0.19f, 0.24f, 1);
  c[ImGuiCol_Tab] = ImVec4(0.12f, 0.13f, 0.17f, 1);
  c[ImGuiCol_TabSelected] = ImVec4(0.20f, 0.42f, 0.36f, 1);
  c[ImGuiCol_TabHovered] = ImVec4(0.24f, 0.50f, 0.42f, 1);
  c[ImGuiCol_SliderGrab] = colors::so;
  c[ImGuiCol_CheckMark] = colors::so;
  c[ImGuiCol_Border] = ImVec4(1, 1, 1, 0.08f);
  ImPlotStyle& ps = ImPlot::GetStyle();
  ps.Colors[ImPlotCol_PlotBg] = ImVec4(0.05f, 0.06f, 0.08f, 1);
  ps.Colors[ImPlotCol_FrameBg] = ImVec4(0, 0, 0, 0);
  ps.Colors[ImPlotCol_LegendBg] = ImVec4(0.05f, 0.06f, 0.08f, 0.85f);
  ps.PlotPadding = ImVec2(6, 6);
}

void loadFont() {
  ImGuiIO& io = ImGui::GetIO();
  const char* candidates[] = {
      "/usr/share/fonts/Adwaita/AdwaitaSans-Regular.ttf",
      "/usr/share/fonts/TTF/DejaVuSans.ttf",
      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
      "/usr/share/fonts/noto/NotoSans-Regular.ttf",
      "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
      "/System/Library/Fonts/Helvetica.ttc",
      "C:\\Windows\\Fonts\\segoeui.ttf",
  };
  for (const char* path : candidates) {
    if (FILE* f = std::fopen(path, "rb")) {
      std::fclose(f);
      if (io.Fonts->AddFontFromFileTTF(path, 17.0f)) return;
    }
  }
  ImFontConfig cfg;
  cfg.SizePixels = 17;
  io.Fonts->AddFontDefault(&cfg);
}

void sectionTitle(const char* text) {
  ImGui::Spacing();
  ImGui::TextColored(colors::dim, "%s", text);
  ImGui::Separator();
}

void simControls(SimTab& tab) {
  ImGui::TextColored(colors::so, "SECOND OPINION");
  ImGui::TextColored(colors::dim, "Camera cross-check for lander altitude sensors");

  sectionTitle("SCENARIO");
  const auto& scenarios = sim::builtinScenarios();
  ImGui::SetNextItemWidth(-1);
  if (ImGui::BeginCombo("##scenario", scenarios[tab.scenario].title.c_str())) {
    for (int i = 0; i < static_cast<int>(scenarios.size()); i++)
      if (ImGui::Selectable(scenarios[i].title.c_str(), i == tab.scenario)) {
        tab.scenario = i;
        tab.restart();
      }
    ImGui::EndCombo();
  }
  const sim::Scenario& sc = scenarios[tab.scenario];
  ImGui::PushTextWrapPos(0);
  ImGui::TextUnformatted(sc.story.c_str());
  ImGui::TextColored(colors::base, "Real outcome: %s", sc.realOutcome.c_str());
  ImGui::PopTextWrapPos();

  sectionTitle("PLAYBACK");
  const float bw = (ImGui::GetContentRegionAvail().x - 2 * ImGui::GetStyle().ItemSpacing.x) / 3;
  if (ImGui::Button(tab.playing ? "Pause" : "Play", ImVec2(bw, 0))) tab.playing = !tab.playing;
  ImGui::SameLine();
  if (ImGui::Button("Step", ImVec2(bw, 0)) && tab.sim) {
    tab.playing = false;
    tab.sim->step();
  }
  ImGui::SameLine();
  if (ImGui::Button("Restart", ImVec2(bw, 0))) tab.restart();
  ImGui::SetNextItemWidth(-1);
  ImGui::SliderFloat("##speed", &tab.speed, 0.1f, 4.0f, "speed %.2fx", ImGuiSliderFlags_Logarithmic);
  ImGui::Checkbox("Show hazard map", &tab.showHazard);
  if (tab.sim) ImGui::TextColored(colors::dim, "t = %.2f s", tab.sim->time());

  sectionTitle("BREAK THE RANGEFINDER (both landers)");
  if (tab.sim) {
    sim::Simulation& s = *tab.sim;
    const float hw = (ImGui::GetContentRegionAvail().x - ImGui::GetStyle().ItemSpacing.x) / 2;
    if (ImGui::Button("Cover sensor", ImVec2(hw, 0))) s.setFault({sim::RangeFault::Covered, 0});
    ImGui::SetItemTooltip("Something sits over the sensor: it reads ~3 cm (the rig demo).");
    ImGui::SameLine();
    if (ImGui::Button("No echo", ImVec2(hw, 0))) s.setFault({sim::RangeFault::Dropout, 0});
    ImGui::SetItemTooltip("No readings at all (Odysseus).");
    if (ImGui::Button("Freeze reading", ImVec2(hw, 0))) s.setFault({sim::RangeFault::Stuck, 0});
    ImGui::SameLine();
    if (ImGui::Button("Lag 1.5 s", ImVec2(hw, 0))) s.setFault({sim::RangeFault::Lag, 1.5});
    ImGui::SetItemTooltip("Readings arrive late (Resilience).");
    if (ImGui::Button("Spurious returns", ImVec2(hw, 0))) s.setFault({sim::RangeFault::Noisy, 0.3});
    ImGui::SameLine();
    if (ImGui::Button("Repair", ImVec2(hw, 0))) s.setFault({sim::RangeFault::None, 0});
    if (ImGui::Button("Slide a crater rim underneath", ImVec2(-1, 0))) s.dropBlock(0.3);
    ImGui::SetItemTooltip("Raises a block under the landers, like sliding cardboard under the rig.");
    ImGui::TextColored(colors::dim, "Current fault: %s", sim::toString(s.secondOpinion().rangefinder.fault.type));
  }

  sectionTitle("OUTCOME");
  if (tab.sim) {
    drawOutcome("Baseline", colors::base, tab.sim->baseline());
    ImGui::Spacing();
    drawOutcome("Second Opinion", colors::so, tab.sim->secondOpinion());
  }
  ImGui::Spacing();
  ImGui::TextColored(colors::dim, "Keys: Space play/pause, R restart, 1-5 scenario");
}

void simTab(SimTab& tab, SDL_Renderer* renderer, float realDt) {
  const bool ready = tab.ready();
  if (ready && tab.playing && !tab.sim->finished()) {
    tab.accumulator += realDt * tab.speed;
    // Cap work per frame so the UI stays responsive on slow machines.
    int steps = 0;
    while (tab.accumulator >= tab.sim->dt() && steps < 4) {
      tab.sim->step();
      tab.accumulator -= tab.sim->dt();
      steps++;
    }
    if (steps == 4) tab.accumulator = 0;
  }

  const float W = ImGui::GetContentRegionAvail().x;
  const float leftW = std::clamp(W * 0.22f, 290.f, 360.f), centreW = std::clamp(W * 0.32f, 330.f, 560.f);
  const float avail = ImGui::GetContentRegionAvail().y;
  ImGui::BeginChild("left", ImVec2(leftW, avail), ImGuiChildFlags_Borders);
  simControls(tab);
  ImGui::EndChild();
  ImGui::SameLine();

  // The controls above may have restarted the simulation this frame.
  if (!ready || !tab.sim) {
    ImGui::BeginChild("loading", ImVec2(0, avail), ImGuiChildFlags_Borders);
    ImGui::TextColored(colors::dim, "Generating moonscape...");
    ImGui::EndChild();
    return;
  }
  sim::Simulation& s = *tab.sim;
  sim::Lander& so = s.secondOpinion();

  ImGui::BeginChild("centre", ImVec2(centreW, avail), ImGuiChildFlags_Borders);
  ImGui::TextColored(colors::so, "Second Opinion's downward camera");
  tab.camTex.update(renderer, so.frame);
  CameraOverlay ov;
  ov.hazard = &so.hazard;
  ov.showHazard = tab.showHazard;
  if (so.ttc) {
    ov.ttc = so.ttc->ttc;
    ov.confidence = so.ttc->confidence;
  }
  ov.rangeOk = so.nav.rangeStatus == SensorStatus::Ok;
  if (so.siteLocked && so.nav.altitude > 0.5) {
    const auto& cam = s.camera();
    const double pxPerM = cam.focalPx / so.nav.altitude;
    ov.siteNX = (so.siteX - so.x) * pxPerM / (cam.width / 2.0);
    ov.siteNY = (so.siteY - so.y) * pxPerM / (cam.height / 2.0);
    ov.siteVisible = std::abs(ov.siteNX) < 1 && std::abs(ov.siteNY) < 1;
  }
  const float camW = ImGui::GetContentRegionAvail().x;
  drawCameraView(tab.camTex, ImVec2(camW, camW * 0.75f), ov);
  ImGui::TextColored(colors::dim, "Red: hazards (rocks, slopes). Green box: safest spot. Yellow ring: rangefinder.");
  sectionTitle("SECOND OPINION'S JUDGEMENT");
  drawHealth(so.nav, true);
  sectionTitle("BASELINE'S JUDGEMENT");
  drawHealth(s.baseline().nav, false);
  ImGui::EndChild();
  ImGui::SameLine();

  ImGui::BeginChild("right", ImVec2(std::max(420.f, ImGui::GetContentRegionAvail().x), avail), ImGuiChildFlags_Borders);
  const float w = ImGui::GetContentRegionAvail().x;
  const float h = ImGui::GetContentRegionAvail().y;
  drawProfile(s, ImVec2(w, h * 0.30f));
  drawAltitudePlot(s, h * 0.28f);
  drawTTCPlot(s, h * 0.17f);
  const float logH = ImGui::GetContentRegionAvail().y - ImGui::GetTextLineHeightWithSpacing() - 4;
  const float half = (w - ImGui::GetStyle().ItemSpacing.x) / 2;
  ImGui::BeginGroup();
  ImGui::TextColored(colors::so, "Second Opinion log");
  ImGui::PushID("so");
  ImGui::BeginChild("solog", ImVec2(half, logH));
  drawEvents("events", so.events(), logH);
  ImGui::EndChild();
  ImGui::PopID();
  ImGui::EndGroup();
  ImGui::SameLine();
  ImGui::BeginGroup();
  ImGui::TextColored(colors::base, "Baseline log");
  ImGui::PushID("base");
  ImGui::BeginChild("baselog", ImVec2(half, logH));
  drawEvents("events", s.baseline().events(), logH);
  ImGui::EndChild();
  ImGui::PopID();
  ImGui::EndGroup();
  ImGui::EndChild();
}

void liveTab(LiveTab& tab, SDL_Renderer* renderer, double now) {
  live::Rig& rig = tab.rig;
  rig.poll(now);
  const float avail = ImGui::GetContentRegionAvail().y;

  const float W = ImGui::GetContentRegionAvail().x;
  ImGui::BeginChild("liveleft", ImVec2(std::clamp(W * 0.22f, 290.f, 360.f), avail), ImGuiChildFlags_Borders);
  ImGui::TextColored(colors::so, "LIVE RIG");
  ImGui::PushTextWrapPos(0);
  ImGui::TextColored(colors::dim,
                     "Webcam + ultrasonic sensor on a stepper carriage over a 3D-printed moonscape. Flash "
                     "firmware/second_opinion onto the Arduino first.");
  ImGui::PopTextWrapPos();
  sectionTitle("CONNECT");
  ImGui::SetNextItemWidth(200);
  ImGui::InputText("##serial", tab.serialPath, sizeof tab.serialPath);
  ImGui::SameLine();
  if (ImGui::Button(rig.serial_.isOpen() ? "Reconnect##s" : "Arduino")) rig.connectSerial(tab.serialPath);
  ImGui::SetNextItemWidth(200);
  ImGui::InputText("##camera", tab.cameraPath, sizeof tab.cameraPath);
  ImGui::SameLine();
  if (ImGui::Button(rig.webcam_.isOpen() ? "Reconnect##c" : "Webcam")) rig.connectCamera(tab.cameraPath);
  if (!rig.status.empty()) {
    ImGui::PushTextWrapPos(0);
    ImGui::TextColored(colors::dim, "%s", rig.status.c_str());
    ImGui::PopTextWrapPos();
  }
  ImGui::TextColored(rig.serial_.isOpen() ? colors::good : colors::dim, "Arduino %s",
                     rig.serial_.isOpen() ? "connected" : "not connected");
  ImGui::TextColored(rig.webcam_.isOpen() ? colors::good : colors::dim, "Webcam %s",
                     rig.webcam_.isOpen() ? "connected" : "not connected");

  sectionTitle("CARRIAGE");
  ImGui::SetNextItemWidth(-1);
  ImGui::SliderInt("##speed", &tab.speedMm, 5, 60, "descent %d mm/s");
  const float bw = (ImGui::GetContentRegionAvail().x - ImGui::GetStyle().ItemSpacing.x) / 2;
  if (ImGui::Button("Descend", ImVec2(bw, 0))) rig.command("D" + std::to_string(tab.speedMm));
  ImGui::SameLine();
  if (ImGui::Button("Stop", ImVec2(bw, 0))) rig.command("S");
  if (ImGui::Button("Raise", ImVec2(bw, 0))) rig.command("U" + std::to_string(tab.speedMm * 2));
  ImGui::SameLine();
  if (ImGui::Button("Zero position", ImVec2(bw, 0))) rig.command("Z");
  if (ImGui::Button("Reset estimator", ImVec2(-1, 0))) rig.resetEstimator();
  ImGui::TextColored(colors::dim, "Position %.0f mm, speed %.0f mm/s", rig.position * 1000, rig.speed * 1000);
  if (rig.range)
    ImGui::TextColored(colors::range, "Ultrasonic %.0f mm", *rig.range * 1000);
  else
    ImGui::TextColored(colors::bad, "Ultrasonic: no echo");
  ImGui::TextColored(colors::dim, "Last line: %s", rig.lastLine.c_str());

  sectionTitle("DEMO SCRIPT");
  ImGui::PushTextWrapPos(0);
  ImGui::TextUnformatted("1. Descend over the moonscape: both sensors agree.");
  ImGui::TextUnformatted("2. Slide the cardboard rim underneath: the rangefinder jumps, the camera confirms, the "
                         "reading is kept (ispace 2023 would have rejected it).");
  ImGui::TextUnformatted("3. Cover the ultrasonic sensor: the camera disagrees, the rangefinder is declared failed and "
                         "the carriage keeps descending on the camera estimate (Resilience 2025).");
  ImGui::PopTextWrapPos();
  ImGui::EndChild();
  ImGui::SameLine();

  ImGui::BeginChild("livecentre", ImVec2(std::clamp(W * 0.32f, 330.f, 560.f), avail), ImGuiChildFlags_Borders);
  tab.camTex.update(renderer, rig.frame);
  CameraOverlay ov;
  ov.hazard = &rig.hazard;
  if (rig.ttc) {
    ov.ttc = rig.ttc->ttc;
    ov.confidence = rig.ttc->confidence;
  }
  ov.rangeOk = rig.nav.rangeStatus == SensorStatus::Ok;
  const float camW = ImGui::GetContentRegionAvail().x;
  drawCameraView(tab.camTex, ImVec2(camW, camW * 0.75f), ov);
  sectionTitle("JUDGEMENT");
  if (rig.nav.source == AltSource::None)
    ImGui::TextColored(colors::dim, "Waiting for sensor data. Connect the webcam and Arduino.");
  else
    drawHealth(rig.nav, true);
  ImGui::Text("Fused altitude: %.0f mm", rig.nav.altitude * 1000);
  if (rig.nav.cameraAltitude) ImGui::TextColored(colors::camera, "Camera altitude: %.0f mm", *rig.nav.cameraAltitude * 1000);
  ImGui::EndChild();
  ImGui::SameLine();

  ImGui::BeginChild("liveright", ImVec2(std::max(420.f, ImGui::GetContentRegionAvail().x), avail), ImGuiChildFlags_Borders);
  const float h = ImGui::GetContentRegionAvail().y;
  if (ImPlot::BeginPlot("Rig altitude", ImVec2(-1, h * 0.55f))) {
    ImPlot::SetupAxes("time (s)", "metres", ImPlotAxisFlags_AutoFit, ImPlotAxisFlags_AutoFit);
    if (!rig.history.empty()) {
      // deque isn't contiguous: copy into vectors for plotting.
      std::vector<double> t, r, c, f;
      for (const auto& s : rig.history) {
        t.push_back(s.t);
        r.push_back(s.range);
        c.push_back(s.cameraAlt);
        f.push_back(s.fused);
      }
      const int n = static_cast<int>(t.size());
      ImPlot::SetNextMarkerStyle(ImPlotMarker_Circle, 1.8f, colors::range, 0);
      ImPlot::PlotScatter("ultrasonic", t.data(), r.data(), n);
      ImPlot::SetNextLineStyle(colors::camera, 1.5f);
      ImPlot::PlotLine("camera (TTC x speed)", t.data(), c.data(), n);
      ImPlot::SetNextLineStyle(colors::so, 2.5f);
      ImPlot::PlotLine("Second Opinion", t.data(), f.data(), n);
    }
    ImPlot::EndPlot();
  }
  ImGui::TextColored(colors::so, "Log");
  drawEvents("livelog", rig.events(), ImGui::GetContentRegionAvail().y);
  ImGui::EndChild();
}

}  // namespace

int main(int argc, char** argv) {
  std::string startScenario, screenshot, cameraDev, serialDev;
  double screenshotAfter = 10;
  bool startLive = false;
  for (int i = 1; i < argc; i++) {
    if (!std::strcmp(argv[i], "--scenario") && i + 1 < argc) startScenario = argv[++i];
    else if (!std::strcmp(argv[i], "--screenshot") && i + 1 < argc) screenshot = argv[++i];
    else if (!std::strcmp(argv[i], "--seconds") && i + 1 < argc) screenshotAfter = std::atof(argv[++i]);
    else if (!std::strcmp(argv[i], "--live")) startLive = true;
    else if (!std::strcmp(argv[i], "--camera") && i + 1 < argc) cameraDev = argv[++i];
    else if (!std::strcmp(argv[i], "--serial") && i + 1 < argc) serialDev = argv[++i];
  }

  if (!SDL_Init(SDL_INIT_VIDEO)) {
    std::fprintf(stderr, "SDL_Init: %s\n", SDL_GetError());
    return 1;
  }
  SDL_Window* window = SDL_CreateWindow("Second Opinion", 1600, 980, SDL_WINDOW_RESIZABLE);
  SDL_Renderer* renderer = window ? SDL_CreateRenderer(window, nullptr) : nullptr;
  if (!renderer) {
    std::fprintf(stderr, "SDL window/renderer: %s\n", SDL_GetError());
    return 1;
  }
  SDL_SetRenderVSync(renderer, 1);

  IMGUI_CHECKVERSION();
  ImGui::CreateContext();
  ImPlot::CreateContext();
  ImGui::GetIO().IniFilename = nullptr;
  setupStyle();
  loadFont();
  ImGui_ImplSDL3_InitForSDLRenderer(window, renderer);
  ImGui_ImplSDLRenderer3_Init(renderer);

  // Heap-allocated so their textures are freed before the renderer.
  auto simPtr = std::make_unique<SimTab>();
  auto livePtr = std::make_unique<LiveTab>();
  SimTab& simState = *simPtr;
  LiveTab& liveState = *livePtr;
  if (!screenshot.empty()) simState.speed = 4;
  const auto& scenarios = sim::builtinScenarios();
  for (int i = 0; i < static_cast<int>(scenarios.size()); i++)
    if (scenarios[i].id == startScenario) simState.scenario = i;
  simState.restart();
  if (!cameraDev.empty()) {
    std::snprintf(liveState.cameraPath, sizeof liveState.cameraPath, "%s", cameraDev.c_str());
    liveState.rig.connectCamera(cameraDev);
    startLive = true;
  }
  if (!serialDev.empty()) {
    std::snprintf(liveState.serialPath, sizeof liveState.serialPath, "%s", serialDev.c_str());
    liveState.rig.connectSerial(serialDev);
    startLive = true;
  }
  bool selectLiveTab = startLive;

  const auto start = std::chrono::steady_clock::now();
  auto last = start;
  bool running = true;
  while (running) {
    SDL_Event e;
    while (SDL_PollEvent(&e)) {
      ImGui_ImplSDL3_ProcessEvent(&e);
      if (e.type == SDL_EVENT_QUIT) running = false;
      if (e.type == SDL_EVENT_WINDOW_CLOSE_REQUESTED && e.window.windowID == SDL_GetWindowID(window)) running = false;
    }
    const auto now = std::chrono::steady_clock::now();
    const float dt = std::min(0.1f, std::chrono::duration<float>(now - last).count());
    last = now;
    const double elapsed = std::chrono::duration<double>(now - start).count();

    ImGui_ImplSDLRenderer3_NewFrame();
    ImGui_ImplSDL3_NewFrame();
    ImGui::NewFrame();

    if (!ImGui::GetIO().WantTextInput) {
      if (ImGui::IsKeyPressed(ImGuiKey_Space)) simState.playing = !simState.playing;
      if (ImGui::IsKeyPressed(ImGuiKey_R)) simState.restart();
      for (int i = 0; i < static_cast<int>(scenarios.size()) && i < 9; i++)
        if (ImGui::IsKeyPressed(static_cast<ImGuiKey>(ImGuiKey_1 + i))) {
          simState.scenario = i;
          simState.restart();
        }
    }

    const ImGuiViewport* vp = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(vp->WorkPos);
    ImGui::SetNextWindowSize(vp->WorkSize);
    ImGui::Begin("Second Opinion", nullptr,
                 ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove |
                     ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoBringToFrontOnFocus |
                     ImGuiWindowFlags_HorizontalScrollbar);
    if (ImGui::BeginTabBar("mode")) {
      if (ImGui::BeginTabItem("Simulation")) {
        simTab(simState, renderer, dt);
        ImGui::EndTabItem();
      }
      if (ImGui::BeginTabItem("Live rig", nullptr, selectLiveTab ? ImGuiTabItemFlags_SetSelected : 0)) {
        liveTab(liveState, renderer, elapsed);
        ImGui::EndTabItem();
      }
      ImGui::EndTabBar();
    }
    selectLiveTab = false;
    ImGui::End();

    ImGui::Render();
    SDL_SetRenderDrawColor(renderer, 15, 17, 22, 255);
    SDL_RenderClear(renderer);
    ImGui_ImplSDLRenderer3_RenderDrawData(ImGui::GetDrawData(), renderer);

    const bool shotDue = startLive ? elapsed >= screenshotAfter : simState.sim && simState.sim->time() >= screenshotAfter;
    if (!screenshot.empty() && shotDue) {
      if (SDL_Surface* shot = SDL_RenderReadPixels(renderer, nullptr)) {
        SDL_SavePNG(shot, screenshot.c_str());
        SDL_DestroySurface(shot);
      }
      running = false;
    }
    SDL_RenderPresent(renderer);
  }

  if (simState.loading.valid()) simState.loading.wait();
  simPtr.reset();
  livePtr.reset();
  ImGui_ImplSDLRenderer3_Shutdown();
  ImGui_ImplSDL3_Shutdown();
  ImPlot::DestroyContext();
  ImGui::DestroyContext();
  SDL_DestroyRenderer(renderer);
  SDL_DestroyWindow(window);
  SDL_Quit();
  return 0;
}
