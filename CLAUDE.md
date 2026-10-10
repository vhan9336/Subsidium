# CLAUDE.md

Second Opinion: a camera-based cross-check for lander altitude sensors (HackPHS hackathon project). C++17, CMake. See README.md for the pitch, wiring and demo script.

## Commands

```sh
cmake -S . -B build && cmake --build build -j   # first configure downloads ImGui v1.91.9b + ImPlot v0.16
./build/so_tests                                # unit + end-to-end scenario tests (~1 min)
./build/so_sim_cli [scenario-id] [--events]     # headless replay; ids: nominal ispace-m1 ispace-m2 im1-odysseus im2-athena
./build/second_opinion [--scenario id] [--live] [--camera /dev/video0] [--serial /dev/ttyACM0]
```

- `-DSO_BUILD_APP=OFF` skips SDL3/ImGui (core, sim, CLI and tests only). `-DSO_NATIVE=OFF` drops `-march=native`.
- Screenshot without opening a window: `SDL_VIDEO_DRIVER=offscreen ./build/second_opinion --scenario ispace-m1 --screenshot out.png --seconds 9` (for `--live`, `--seconds` is wall-clock time).
- Tests are a plain executable with `CHECK` macros (`tests/tests.cpp`), no framework. `ctest --test-dir build` also works.

## Architecture

- `src/core/` (`so_core`, no dependencies). This is the product; it runs in both the sim and on the rig.
  - `ttc.*`: time-to-contact via Horn–Fang–Masaki direct least squares over (expansion c, drift tx, ty), with a 2-level pyramid and warp-and-refine. `TTCTracker` adapts the frame baseline so slow approaches (the rig) still move ~1 px. `fitCells` gives per-cell relative depth from residual motion along each cell's *expected* motion (expansion and parallax both scale with 1/Z).
  - `fusion.*`: `SecondOpinion` is a 3-way vote between rangefinder, camera (TTC × descent speed) and IMU dead reckoning. A rangefinder jump becomes *pending*: the camera agreeing with the new reading means terrain change (accept); the camera siding with dead reckoning means reject; the camera matching neither proves nothing (wait, then reject after 2× the window). `BaselineEstimator` deliberately reproduces ispace M1's logic (reject jumps, lock out after 1 s).
  - `hazard.*`: grid scores from local relief (relative to the neighbourhood median, not the whole image), slope from a 3×3 inverse-depth plane fit, and appearance roughness.
- `src/sim/` (`so_sim`): procedural terrain (heightmap, craters, boulders, optional cliff, cast-shadow shade map, band-limited albedo noise), camera ray-marcher, rangefinder fault models, two-lander `Simulation` with guidance and touchdown outcome, and the built-in `Scenario`s.
- `src/live/` (`so_live`, Linux only): V4L2 YUYV webcam, termios serial, and `Rig`, which wires them into the same core estimator at rig scale.
- `src/app/`: SDL3 + Dear ImGui + ImPlot visualizer (`views.*` drawing helpers, `main.cpp` tabs and loop).
- `firmware/second_opinion/`: Arduino sketch. Serial protocol `R,<ms>,<range_mm|-1>,<speed_mm_s>,<pos_mm>`; commands `D<mm/s>`, `U<mm/s>`, `S`, `Z`. Keep it in sync with `src/live/rig.cpp`.

## Invariants and gotchas

- `tests/tests.cpp` asserts the story: in every mission scenario Second Opinion lands and the baseline fails; in `nominal` both land. After changing fusion, hazard, guidance or terrain, run `so_tests` and also check several sim seeds (`Simulation(sc, seed)`); results were 25/25 across seeds 1–5.
- Sign conventions: `descentRate`/`vz` are positive when descending. Image x/y map to world x/y. Hazard `siteX/siteY` are normalised −1..1 across the image width/height.
- Camera influence on the fused altitude is clamped per tick (`maxStep`). One bad TTC frame once threw the estimate to 228 m; don't remove the clamp.
- Partly shadowed cells count as rough, *unless* next to a fully dark cell (that's a big shadow edge). Fully dark cells score 0.55: never chosen as a site, but not painted as rocks.
- Perf matters: the dev machine is a 2-core low-power i5. The camera render is the hot path (adaptive 2× supersampling, 2 fixed-point ray iterations seeded from the neighbouring pixel). Terrain generation runs async in the app (`SimTab::restart`). Anything in `simTab` after `simControls()` must re-check `tab.sim`, because the controls can restart it mid-frame.
- ImPlot breaks lines at NaN; `Sample` uses NaN for "no reading".
- The live webcam and Arduino paths and the firmware are untested on hardware (firmware is only syntax-checked). Don't turn on the user's webcam without asking.

## Style

Match the existing code: `so::` / `so::sim::` / `so::live::` / `so::app::` namespaces, 2-space indent, ~120 columns, `std::optional` for missing readings, short comments that explain *why*. Physical units are SI (metres, seconds) everywhere except the firmware and serial protocol (mm).
