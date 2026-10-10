# Second Opinion

A camera-based cross-check for the moment a lander has to decide whether its own altitude sensor is lying.

Recent commercial Moon landings keep failing on the same question: how far away is the ground?

| Mission | What went wrong |
|---|---|
| ispace Mission 1 (Apr 2023) | Flew over a crater rim, the rangefinder reading jumped, software rejected the *correct* reading. Thought it had landed ~5 km up, ran out of fuel. |
| ispace Resilience (Jun 2025) | Laser rangefinder degraded, readings came too late to brake. |
| Intuitive Machines Odysseus (Feb 2024) | Rangefinders unusable; landed tipped over. |
| Intuitive Machines Athena (Mar 2025) | Altimeter trouble; ended up on its side in a crater. |

Each time one sensor gave a bad reading and the lander had nothing independent to check it against.

## How it works

1. **Time to impact from the camera.** A downward camera measures how fast the ground image expands, the same way flies land. It doesn't need the true altitude or scale. We use the direct least-squares method of Horn, Fang & Masaki (2007): every pixel's brightness change gives one equation in (expansion, drift x, drift y), solved coarse-to-fine (`src/core/ttc.cpp`).
2. **Three-way vote.** The rangefinder's distance divided by descent speed should match the camera's time to impact. Dead reckoning from the IMU is the third voter. When the rangefinder jumps, the jump is held as *pending* and the camera is asked:
   - If the camera follows the new reading, the terrain changed (a crater rim) and the reading is kept.
   - If the camera sides with dead reckoning, the rangefinder is wrong. Repeated failures bench it, and the lander flies on the camera estimate.
   - If the rangefinder and camera disagree but both look self-consistent, assume the ground is closer. Slowing early is survivable. (`src/core/fusion.cpp`)
3. **Hazard map.** Each grid cell's leftover motion after removing the global fit gives its depth relative to its neighbours: rocks stick out, and slopes show up as a gradient. Shading contrast and rock shadows add roughness. The lander diverts to the safest nearby cell (`src/core/hazard.cpp`).

The same estimator runs in the simulator and on the physical rig.

## Build

Needs CMake ≥ 3.20, a C++17 compiler and SDL3 (for the visualizer). Dear ImGui and ImPlot are downloaded by CMake.

```sh
cmake -S . -B build
cmake --build build -j
./build/so_tests            # unit + end-to-end scenario tests
./build/so_sim_cli --events # headless replay of every scenario
./build/second_opinion      # visualizer
```

`-DSO_BUILD_APP=OFF` builds only the core, simulator, CLI and tests (no SDL needed). `-DSO_NATIVE=OFF` drops `-march=native` for portable binaries.

## Visualizer

**Simulation tab.** Two identical landers fly the same descent with the same sensor faults. One uses Second Opinion; the other uses the baseline logic that rejects jumps and trusts dead reckoning.

- Camera feed with the hazard map, the safest spot and the divert target
- Side view showing where each lander *thinks* the ground is
- Altitude and time-to-impact plots: truth, rangefinder, camera, both estimates
- Sensor health, current verdict, and an event log per lander
- Live fault buttons: cover the sensor, no echo, freeze, lag, spurious returns, and "slide a crater rim underneath"

Keys: `Space` play/pause, `R` restart, `1`–`5` pick a scenario.

**Live rig tab.** Same estimator on a real webcam (V4L2) and the Arduino. `./build/second_opinion --camera /dev/video0 --serial /dev/ttyACM0` opens it connected.

### Scenario results (5 sensor-noise seeds each)

| Scenario | Baseline | Second Opinion |
|---|---|---|
| Nominal | landed 5/5 | landed 5/5 |
| ispace M1, crater rim | crashed 5/5 | landed 5/5 |
| ispace Resilience, late rangefinder | crashed 5/5 | landed 5/5 |
| Odysseus, no rangefinder | tipped 5/5 | landed 5/5 |
| Athena, noisy altimeter + boulders | tipped 5/5 | landed 5/5 |

## Demo rig

Webcam + HC-SR04 ultrasonic sensor (standing in for the laser rangefinder) on a stepper carriage over a 3D-printed moonscape.

| Part | Arduino pin |
|---|---|
| HC-SR04 TRIG / ECHO | D7 / D2 |
| Stepper driver STEP / DIR / EN | D3 / D4 / D8 |

Set `STEPS_PER_MM`, `MAX_TRAVEL_MM` and `DIR_DOWN_LEVEL` at the top of `firmware/second_opinion/second_opinion.ino`, flash it, raise the carriage to the top and press **Zero position**.

Demo script (~90 s):
1. **Descend** over the moonscape. Both sensors agree.
2. **Replay 2023:** slide a cardboard crater rim underneath. The rangefinder jumps, the camera confirms, and the reading is kept.
3. **Replay 2025:** cover the ultrasonic sensor. The camera disagrees, the rangefinder is declared failed, and the carriage keeps descending on the camera estimate.

Record backup footage once the rig works.

## Layout

```
src/core/   estimator: image utils, time-to-contact, fusion, hazard map (no dependencies)
src/sim/    procedural moonscape, camera renderer, rangefinder faults, landers, scenarios
src/live/   V4L2 webcam, serial port, rig controller
src/app/    SDL3 + Dear ImGui visualizer
src/cli/    headless scenario runner
tests/      unit and end-to-end tests
firmware/   Arduino sketch for the rig
```

## Honest limits

- The simulator is ours, so the results above show the logic works on terrain we generated, not on real flight data.
- The hazard map is noisy during fast sideways flight (12 m/s in the M1 scenario) and settles once the lander slows.
- Camera altitude needs a known descent speed (IMU, or the stepper speed on the rig) and visible texture. Over blank ground or in deep shadow it says so and steps aside.
- Camera-based hazard detection already exists at NASA and in research; what's new here is using it as the referee between sensors.
