Things to settle before you
- Real-footage accuracy is unmeasured. The footage isn't downloaded here, so I couldn't run the real-foohe command in the READMEyourselves and write the number down. The only accuracy numbers in the guide are
  synthetic ones (0.3 to 0.
- Odysseus and Athena don't beat the legacy gate in numbers. The guide says to
  present them as a safety mera can be outvoted.HAKUTO-R and Resilience are the decisive demos.
- Subsidium's worst error os about 1.5 s to confirm the terrain change, so the guide tells you to say that before a judge asks.     The camera shares the desrtial. It is independent ofthe rangefinder and of inertial position drift, but not of speed. This is a likely hard question, and
- The rig may not have run yet. The project notes say the firmware was written but not run on hardware. Confthe team.
- The "next steps" answer is my guess. The last judge question suggests next steps, and I wrote that answer, real plans.
- The AI-use table still needs your input. docs/AI_USE.md still has "fill in as you go" in its human-changes quires that disclosure.

# Subsidium study guide

Everyone presenting should be able to answer anything in here without looking. Part 1 to 3 are the story (what, why, how it differs). Parts 4 to 6 are the machinery. Parts 7 to 11 are for the stage: evidence, limits, the demo, likely questions and a cheat sheet.

Where a number appears, the source is named. Where we have not measured something, the guide says so. Do not quote a number on stage that this guide marks as unmeasured.

Contents

1. The one-minute version
2. The real-world problem
3. How Subsidium is different from what came before
4. How it works
5. What the dashboard shows
6. The five replays, one by one
7. Evidence: what we can honestly claim
8. Limits and what never to say
9. Demo script and talk track
10. Questions judges will ask
11. Cheat sheet and glossary
12. Before you present: setup and checks
13. AI use and credits

---

## 1. The one-minute version

A lunar lander has to know how high it is above the ground, because that decides when to fire its engine to slow down. It gets that from several sensors. When two of them disagree, the landing software has to decide which one to believe, and several recent commercial Moon landers have believed the wrong one.

Subsidium adds a third, independent witness: a downward camera. The camera measures how fast the ground in the picture grows as the lander descends. That growth rate gives the time until contact with the ground (time to contact, written τ). Multiply τ by the descent speed and you get an altitude that shares no hardware with the laser rangefinder.

With three witnesses, a disagreement has an answer. Each pair of sensors is tested for agreement. The sensor that appears in both failing pairs is the odd one out and gets outvoted. If no single sensor can be blamed, the system assumes the closest ground, which is the safe assumption when braking.

The dashboard runs two brains on the same sensor stream: the textbook gate that matches what ispace reported for HAKUTO-R, and Subsidium. You watch the old logic believe the wrong altitude and Subsidium stay on the true one.

Short claim for the stage: a cheap, dissimilar, scale-free cross-check using best-2-of-3 voting, aimed at the failure behind four recent landings. It is not a new way to land.

---

## 2. The real-world problem

### Why altitude is the critical number

During the last minutes of a landing, the lander plans its braking from its altitude and speed. If it thinks it is lower than it is, it brakes too early and runs out of propellant. If it thinks it is higher than it is, it brakes too late and hits the ground. Either way a single wrong altitude can end the mission.

### Why sensors disagree

No altitude sensor is perfect, and each fails in its own way:

| Sensor | How it works | How it goes wrong |
|---|---|---|
| Inertial (navigation) | Adds up acceleration since a known starting point | Drifts the longer it runs without a correction. It also cannot see the ground, so if the terrain changes under the lander it does not notice |
| Rangefinder (laser or radar) | Measures the distance to the ground directly | Can degrade, lag behind reality, freeze on one value, or give no echo at all. Can also be left switched off |
| Camera (ours) | Watches the ground grow in the image | Needs a visible, textured surface. Fails in low contrast, harsh shadow or dust |

### Four real landings that went wrong

All four are described in the project's own facts list (MASTERPROMPT.md and the scenario files). The sources named in the scenario files are ispace's press release and debriefing for Mission 1, ispace's Mission 2 report, and Intuitive Machines briefings.

| Mission | Date | What happened | Which sensor problem it is |
|---|---|---|---|
| HAKUTO-R Mission 1 (ispace) | April 2023 | Passing a crater rim of about 3 km, the measured altitude rose sharply. The software judged the correct reading abnormal and filtered it out. The lander believed it was on the surface while about 5 km up, ran out of propellant and fell | Software trusted its internal estimate and threw away a correct rangefinder reading. This is the textbook gate we model as the legacy brain |
| Odysseus, IM-1 (Intuitive Machines) | February 2024 | The laser rangefinders never fired because a safety-enable switch had not been disabled before launch. The team switched to an experimental NASA lidar in flight. The lander touched down with sideways speed and tipped over | Rangefinder absent from the start |
| Athena, IM-2 (Intuitive Machines) | March 2025 | Altimeter interference plus long shadows and low sunlight near the south pole challenged the landing system. Athena landed on its side in a crater | Altimeter trouble, and a warning that cameras struggle in harsh shadow |
| Resilience, Mission 2 (ispace) | June 2025 | The laser rangefinder degraded and valid measurements came too late for the lander to slow down. Telemetry was lost about 193 m up, descending at about 42 m/s | Rangefinder slowly degrading and lagging |

The pattern across all four is that one altitude source was wrong or missing and the system had no independent way to know. That is the gap Subsidium fills.

### Why now

These four landings happened over just over two years, April 2023 to June 2025. A camera is light, cheap and passive, which is why it is a low-cost way to add a third witness. (The guide does not have a source for how many landers already carry a downward camera, so do not state that on stage.)

---

## 3. How Subsidium is different from what came before

### What existed

| Approach | What it does | Weakness for this problem |
|---|---|---|
| Single-source gate (the legacy logic) | Follows inertial and accepts the rangefinder only if it is close. After repeated rejections it declares the rangefinder failed for good | With two sensors it cannot tell which is wrong. If inertial is the one that is wrong, it throws out the correct reading. A slowly degrading sensor sneaks through because each small step looks plausible |
| Terrain-relative navigation and lidar hazard detection (NASA SPLICE, from the prior art list) | Matches what the sensors see to maps of the terrain and detects hazards | Powerful, but heavy: needs maps, lidar and more computing. It is a navigation method, not a cheap cross-check on the existing altitude sensors |
| Camera time-to-contact landing (ESA ACT, Izzo and de Croon, 2012) | Proposes landing using time to contact from a camera | It uses the camera as the landing method. We use it as a third voter |
| A camera choosing between two position sensors (US patent 9728094) | A camera picks between two sensors | A two-way choice. We use a full three-way vote with fault isolation |
| ispace's stated plan | ispace has said it will add visual navigation | Confirms that the industry sees the gap. It is a plan, not a published cross-check design |

### What Subsidium changes

1. A true third vote. With two witnesses, a disagreement can only be detected. With three, it can be isolated. The logic is triplex parity voting, the same idea used for redundant sensors in fly-by-wire aircraft.
2. Dissimilar redundancy. The three witnesses use different physics: acceleration, a laser echo, and image expansion. A failure that hurts one rarely hurts the others in the same way. Three copies of the same sensor would all fail together.
3. Scale-free camera. Time to contact needs no map, no known object size and no laser. It only needs the image to grow as the lander descends. This is why it shares no hardware with the rangefinder.
4. Honest about what it does not know. If the camera has no lock, it abstains instead of guessing. If the rangefinder is silent, the system says so. If no single sensor can be blamed, it assumes the closest ground. It never pretends to be sure.
5. It can be outvoted too. Cameras fail (Athena). Subsidium is built so that a bad camera is excluded by the other two, which is shown in the Athena replay.
6. Made visible. The same sensor stream feeds both brains side by side, scored against the true altitude, so the difference is something you watch, not something we claim.

### The claim, precisely

Our claim: a cheap, dissimilar, scale-free cross-check using best-2-of-3 voting, aimed at the failure behind four recent landings.

We do not claim: a new landing method, NASA approval, or that Subsidium would have saved any specific mission.

---

## 4. How it works

### 4.1 The three witnesses and their noise models

Each witness reports an altitude and an uncertainty (σ, one standard deviation). Values come from `config.toml`. The unit in the engine is millimetres on the tabletop rig scale.

| Witness | Altitude | Uncertainty (σ) |
|---|---|---|
| Inertial (NAV) | Start altitude minus distance descended | 3 mm at the moment it was last anchored, growing by 1 mm per second since: σ = √(3² + (1 × seconds since anchor)²) |
| Rangefinder (RF) | The raw range reading | 3 mm plus 1% of the range |
| Camera (CAM) | τ × v (time to contact times descent speed) | 4% of the altitude, divided by the lock quality (quality is floored at 0.3 in this formula) |

The camera is only used when its lock quality is at least 0.3 and the descent speed is above 1 mm per second. Below that it abstains.

Important honesty point: the camera altitude uses the descent speed v from navigation. So the camera shares nothing with the rangefinder, and it does not depend on inertial position drift, but it does depend on a speed estimate. On the rig, a stepper winch stands in for the inertial or Doppler velocity. A real lander would use its IMU or a Doppler velocimeter.

### 4.2 The camera: time to contact

Physics, in plain language: when you move toward a surface, things on it get bigger. The faster they grow, the sooner you will reach it.

Between two frames taken dt apart, the image scales by a factor s (s greater than 1 when approaching). The time to contact is:

τ = dt ÷ (s − 1)

Altitude is then h = τ × v.

How the code does it (`so/vision/ttc.py`):
1. Convert the frame to grey, shrink it to 320 px wide, equalize contrast.
2. Pick up to 400 good corner features in an older frame (at least 0.5 s old, the `lookback_s` setting).
3. Track them into the new frame with Lucas-Kanade optical flow.
4. Fit a similarity transform (scale, rotation, shift) to the tracked points, using RANSAC to ignore bad matches. The scale of that transform is s.
5. Compute quality from the fraction of points that agree, penalised if there are fewer than 60.
6. Take the median of recent τ values (age-corrected, since τ shrinks by one second per second) to smooth the result.

Two safeguards: if the image suddenly shrinks (ground fell away) or τ suddenly drops to under 40% of its recent value (ground jumped up), the look-back window restarts. This prevents averaging across two different surfaces.

Why this is believable: it is the same strategy diving gannets are thought to use (Lee and Reddish, Nature, 1981, cited in the code).

Hazard map (a secondary feature): the same math gives a relative height for each tile of the image, since a boulder is closer than the ground around it and so expands faster. The app divides the image into a 6 by 6 grid, colours the tiles and picks the safest landing tile. On oblique cameras (Blue Ghost) treat it as indicative only.

### 4.3 The vote

Step 1: test every pair. For each pair of witnesses a and b:

r² = (h_a − h_b)² ÷ (σ_a² + σ_b²)

This asks: is the gap between these two readings bigger than their combined uncertainty explains? It is a normalised squared error (a chi-square statistic with one degree of freedom). A value near 0 to 1 means they agree. A value above 9 means they are more than 3σ apart, which is very unlikely to be noise. The limit of 9 is `chi2_gate` in the config.

Step 2: average over time. Each pair's r² is averaged over the last 0.5 s (`window_s`) so a single noisy frame cannot decide anything.

Step 3: read the pattern. There are three pairs, so there are eight possible pass or fail patterns:

| NAV-RF | NAV-CAM | RF-CAM | Verdict | Action |
|---|---|---|---|---|
| pass | pass | pass | Nominal | Fuse all three |
| fail | fail | pass | Inertial is wrong (the ground really changed) | Re-anchor inertial to the rangefinder and camera |
| fail | pass | fail | Rangefinder is wrong | Exclude the rangefinder |
| pass | fail | fail | Camera is wrong | Exclude the camera |
| fail | fail | fail | Unresolved | Assume the closest ground |
| exactly one pair fails | | | Still developing | Hold the current verdict |

The rule: the faulty witness is the one that appears in both failing pairs while the third pair still agrees.

Step 4: persistence. A new verdict must hold for 0.6 s (`persist_s`) before the system acts on it. This is deliberately longer than camera transients.

Step 5: act.
- Nominal: the estimate is the inverse-variance weighted average of all witnesses (more certain sensors count more).
- A sensor is excluded: the estimate is fused from the remaining two.
- Terrain change: the inertial offset is corrected using the rangefinder and camera, its drift clock restarts, and the verdict returns to nominal. The event is labelled `terrain_change`.
- Unresolved: the estimate is the lowest reading among the witnesses, so the lander brakes for the nearest possible ground. The uncertainty shown is the spread between highest and lowest reading.

### 4.4 Cases with fewer than three witnesses

| Situation | What Subsidium does |
|---|---|
| Camera abstaining (no lock, low contrast, dark) | Only the NAV-RF pair exists. A disagreement can be detected but not pinned on one sensor. If they disagree, the status becomes unresolved and the closest ground is assumed. The camera abstaining is debounced: it must be gone for 0.6 s to count, but it comes back immediately |
| Rangefinder silent (no echo) | The rangefinder is marked silent. Inertial is checked against the camera instead |

The code's own words: it says so instead of guessing.

### 4.5 The legacy gate (the comparison)

`so/fusion/legacy.py`, with `config.toml` values:
1. Follow the inertial estimate.
2. If the rangefinder is within 30 mm of that estimate, accept it and move 30% of the way toward it (`alpha = 0.3`).
3. If it is farther away, reject it.
4. After 10 rejections in a row (`fail_after`), declare the rangefinder failed and never listen to it again.

Why it fails: if the ground really changes, the rangefinder is correct and inertial is wrong, but the gate trusts inertial. It throws out the correct reading, then permanently disables the sensor that was right. It also follows a slowly lagging rangefinder, because each tiny step stays inside the 30 mm gate. This matches ispace's published account of Mission 1.

### 4.6 Fault injection

To test both brains the same way flight software is tested, faults are injected in software. The raw, uncorrupted readings are kept as the answer key.

| Fault | What it does | Models |
|---|---|---|
| rf_lag | Rangefinder readings arrive later and later, ramping up to a 2.5 s delay over 4 s | Resilience |
| rf_freeze | Rangefinder stuck on one value | A frozen sensor |
| rf_drop | No echo at all | Odysseus |
| cam_bias | Camera time to contact multiplied by 1.35 | Athena-style misjudgement |
| cam_blind | Camera loses lock completely | Equivalent to switching the lamp off on the rig |

### 4.7 System architecture

```
Source (simulator | live rig | recorded replay | real footage)
   -> Pipeline (the flight loop)
        navigation estimate and speed
        camera estimator: time to contact, quality, hazard map
        fault injector: corrupted rangefinder or camera, raw values kept
        Legacy gate  -> its belief
        Subsidium    -> belief, uncertainty, pair tests, exclusions, events
   -> state dictionary
   -> FastAPI server -> WebSocket (about 15 updates per second) -> React app
                     -> camera image with overlay -> the browser
```

Key files:

| Part | File |
|---|---|
| Camera estimator | `so/vision/ttc.py` |
| Our monitor | `so/fusion/triplex.py` |
| Legacy gate | `so/fusion/legacy.py` |
| Fault injection | `so/fusion/faults.py` |
| Sources | `so/sources/` (sim, live rig, replay, video, hybrid) |
| Flight loop and state | `so/pipeline.py` |
| Server | `so/server.py` |
| Replay scripts | `scenarios/*.toml` |
| Real-footage clips | `clips.toml` |
| All tunables | `config.toml` |
| Web app | `web/src/` |
| Slides | `slides/` |
| Rig firmware | `firmware/rig/rig.ino` |
| Camera scoring on footage | `eval/run_video.py` |

Everything runs on the source's own clock, so replays and tests are reproducible.

### 4.8 The tabletop rig

A webcam and an ultrasonic sensor hang from a sled on a stepper-motor winch over a textured floor. The stepper's step count gives the inertial altitude and speed. The ultrasonic sensor stands in for the laser rangefinder. A box that slides in and out under the sled creates a 60 mm plateau, which reproduces the HAKUTO-R terrain change physically. The firmware is an Arduino sketch with no libraries. The project notes say it was written but not yet run on hardware when they were last updated, so confirm its status with the team before you describe it.

---

## 5. What the dashboard shows

### Main screen

- Left: one large picture. In the simulator you get a 3D view with the camera as a thumbnail. On real footage you get the footage with a software layer drawn over it.
- Press C or click the thumbnail to swap the two views.
- Right, top: one sentence that says what is happening now. The bar beside it is green (fine), amber (warning) or red (problem).
- Right, middle: a line saying what each brain would do or believe, with the size of the error in plain words.
- Right, bottom: three big numbers.
  1. True altitude
  2. Legacy gate: what it believes, with its error
  3. Subsidium: what it believes, with its error
- A number turns red when its error is above 25 mm (engine scale), a display threshold only.
- Over the footage: an altitude tape with a white line for the true altitude, red for the legacy gate, green for Subsidium, and one dot per witness. A dot that goes grey has been outvoted.

### Colours (the same everywhere)

| Meaning | Colour |
|---|---|
| True altitude | White |
| Rangefinder | Amber |
| Inertial | Slate blue |
| Camera | Cyan |
| Legacy gate | Red |
| Subsidium | Green |

### The math screen (press M)

This is the answer to "prove it". Top row has three live charts: every source on one scale, the vote triangle, and the last 20 seconds. Below it, seven numbered sections:

1. What each sensor says, its uncertainty, and where each reading comes from (measured, generated or reconstructed).
2. The camera altitude worked out with the live numbers: h = τ × v.
3. The pair tests with their r² values against the limit, marked pass or fail.
4. The rule table that picks the odd one out, with the current rule highlighted.
5. The legacy gate beside Subsidium, on the same readings.
6. Every replay scored (the same table as `python -m so check`).
7. Where this replay's numbers come from.

Hand controls (fly by hand, break a sensor, record) appear at the bottom of the math screen.

### Walkthrough slides (press E)

A slide deck built from the HTML files in `slides/`. Arrow keys move, Esc closes. Add or reorder slides by adding numbered files. See `slides/README.md`.

### Keyboard

| Key | Action |
|---|---|
| 1 to 5 | Run a mission replay |
| M | Math screen on or off |
| E | Walkthrough slides |
| C | Swap camera and 3D views |
| V | Voice callouts on or off |
| D, S, U, R | Descend, stop, up, reset |
| T, Y | Plateau in, plateau out |
| 0 | Clear injected faults |

### Voice

Short spoken callouts (for example "Rangefinder outvoted by camera and inertial. Rangefinder excluded.") play as events happen. They are pre-generated with ElevenLabs into `web/public/audio/` so the demo needs no internet, and the browser's speech synthesis is the fallback.

---

## 6. The five replays, one by one

Each replay is a script in `scenarios/` that sets up the scene and injects the fault at a set time. The scores below come from `python -m so check` run on the current code, in engine millimetres (a start altitude of about 450 mm on the rig scale). "Worst" is the largest error seen, "final" is the error at the end.

| Replay | What is injected | Legacy worst / final | Subsidium worst / final | Subsidium event |
|---|---|---|---|---|
| 1 Nominal | Nothing | 2 / 0 mm | 3 / 0 mm | None. All three agree |
| 2 HAKUTO-R M1 | Plateau slides out at 4.0 s | 60 / −60 mm | 38 / 0 mm | Terrain change at 5.5 s |
| 3 Resilience | Rangefinder lag from 3.0 s | 78 / +76 mm | 27 / 0 mm | Rangefinder excluded at 6.2 s |
| 4 Odysseus | Rangefinder silent from 0.2 s | 0 / 0 mm | 1 / 0 mm | Rangefinder silent at 0.9 s |
| 5 Athena | Camera bias from 3.5 s | 2 / 0 mm | 6 / 0 mm | Camera excluded at 4.3 s |

The legacy gate also logs "legacy rangefinder failed" at 4.4 s in the HAKUTO-R replay. That is the moment it permanently discards the correct sensor.

### Talk about each honestly

1. Nominal. The baseline. Both brains agree and are accurate. Purpose: show that adding the vote does not hurt a healthy landing.
2. HAKUTO-R M1. The headline demo. The ground drops away, the rangefinder and camera see it, inertial does not. The legacy gate rejects the correct rangefinder, declares it failed, and ends up 60 mm off for good. Subsidium outvotes inertial and returns to the true altitude. Subsidium's worst error of 38 mm is real: it takes about 1.5 s to confirm (the persistence timer and the averaging window), and during that time it is still off. Say this before someone asks.
3. Resilience. The rangefinder drifts later and later. The legacy gate follows it because each small step looks fine, and ends 76 mm off. Inertial and camera outvote the rangefinder. Worst error 27 mm before the exclusion at 6.2 s.
4. Odysseus. The rangefinder never works. In the simulator, inertial is perfect, so both brains stay accurate and the numbers do not separate them. The point of this replay is that Subsidium raises a "rangefinder silent" flag within about 0.7 s and switches to a cross-check of inertial against the camera, instead of trusting inertial alone. Do not claim a numeric win here. In a real landing, inertial drifts, and that is when the cross-check matters.
5. Athena. The camera misjudges. Subsidium excludes the camera in 0.8 s and stays accurate. The legacy gate ignores the camera, so it is not hurt either. The point is that adding the camera does not add a new weakness: a bad camera gets outvoted. Do not claim Subsidium beats the legacy gate here. Both are accurate.

Honest summary line: the replays are most decisive on HAKUTO-R and Resilience, where the legacy logic ends with a wrong altitude. On Odysseus and Athena the value is the extra safety net and the proof that the camera can be outvoted.

### Real footage and broadcasts

Run with `python -m so serve --video` after downloading the footage with `tools/fetch_data.py`.

| Clip | What it is | What runs |
|---|---|---|
| Blue Ghost Mission 1 | Real Moon landing video from NASA's four SCALPSS cameras, with altitude printed on every frame | All three witnesses on real footage. Faults can be injected. The camera is real, the rangefinder and inertial are generated from NASA's on-screen altitude labels |
| Perseverance | Real Mars descent camera | Camera tracking only. No altitude record was published with the video |
| DART | The camera of DART flying into Dimorphos | Camera tracking only. NASA's replay is an uneven time-lapse |
| HAKUTO-R and Resilience broadcasts | The missions' own live broadcasts | Replay with the on-screen altitude as the answer key. There is no descent camera in the broadcast, so the camera witness is reconstructed from the altitude, not measured |
| Odysseus and Athena broadcasts | NASA broadcasts with mission control and simulation | Used as the background view for those replays |

Each mission replay also descends over the NASA LRO orbiter image of where that lander really came down.

---

## 7. Evidence: what we can honestly claim

### Checks that run in the repo

| Check | Command | What it shows |
|---|---|---|
| Scoreboard | `python -m so check` | Legacy against Subsidium on all five replays. Currently prints PASS. The table in part 6 comes from this |
| Tests | `python -m pytest tests` | 16 tests: monitor logic (6), replays and record-then-replay (2), camera accuracy (1), real-footage behaviour (7) |
| Camera self-test | `python eval/run_video.py --selftest` | Currently: 355 frames, 96% coverage, median error 0.3%, 90th percentile 0.5%, bias +0.3%. This is a synthetic test, not real footage |
| Synthetic descent | `python -m tests.test_ttc` | Currently: 344 samples, median error 0.5%, 90th percentile 0.6%. Also synthetic |

I could not run `pytest` while writing this guide (it was not installed in the environment), so run it yourself before you say the tests pass.

### What is not measured yet

- Camera accuracy on real footage. The footage is not stored in the repo (it is downloaded). The command for it is in the README. Run it, write the result down, and only then quote a real-footage accuracy number. The project rule is that every number on a slide comes from that command or from `tools/stats.py`, nothing else.
- Camera accuracy on the physical rig. `tools/stats.py` produces that number from a rig flight log. If the rig has not been run, there is no such number.
- Any statement that Subsidium "would have saved" a real mission.

### Calibration caveat on Blue Ghost

The Blue Ghost cameras look outward, not straight down, so raw time to contact reads long. A correction factor (`tau_gain = 0.598`) was fitted on the first 4 seconds of the clip, and the rest is scored without refitting (`--calib-s 4`). Say "calibrated on the first four seconds" if asked. Do not present it as an uncalibrated result.

### What is real and what is reconstructed

| Item | Status |
|---|---|
| The failures themselves (what happened to each lander) | Real, from the sources named in the scenario files |
| LRO images of the four landing and impact sites | Real NASA images, with NASA's annotations painted out so the camera tracks terrain. Scale is not preserved: about 1 km of Moon stands in for the 0.7 m rig floor |
| Blue Ghost footage and its altitude labels | Real footage, real labels. Labels were read off the video frames, and the AI notes recommend spot-checking them |
| HAKUTO-R and Resilience altitude on the broadcast | Real display read every 5 seconds. The broadcast marks the panel "UPDATE" and "simulation" at times, so it is the broadcast's display of the descent, not guaranteed raw telemetry |
| The 5 km error in HAKUTO-R | Reported by ispace. The moment in the video where it begins is assumed (`offset_at = 133`), because ispace published the size but not the time |
| Sensor readings in the crash replays | A scaled reconstruction of the published failure. Not mission telemetry. No public descent-camera video or raw sensor telemetry exists for these four missions |

---

## 8. Limits and what never to say

### Limits to state openly

- Terminal descent only. It is a cross-check for the final approach, not a full guidance system.
- Real landers need to de-rotate the image using the attitude from the IMU. Our camera points straight down in the demos.
- The camera needs light and texture. Dust, glare, shadows and featureless ground degrade it. That is why it can abstain and be outvoted.
- The camera altitude uses a speed estimate from navigation. On the rig a stepper stands in for IMU or Doppler velocity.
- Verdicts take about 1 to 1.5 s to confirm. That delay is deliberate (it avoids false alarms) and it is why Subsidium's worst error is not zero.
- Noise values (`config.toml`) are tuned for the rig and the simulator. A real lander would need its own sensor models.
- With two working witnesses, a disagreement can be detected but not isolated. The system says so and falls back to the closest ground.
- The replays reconstruct failures from published accounts. They show that the logic would have behaved differently, not what would have happened to the real vehicle.

### Never say

- "NASA approved", "flight proven" or "flight ready".
- "This would have saved HAKUTO-R" (or any other mission).
- Any accuracy number you have not generated from the commands above.
- That the broadcasts contain descent-camera video. They do not.
- That Subsidium beats the legacy gate on Odysseus or Athena. It does not, in numbers.
- That this is a new landing method or the first use of time to contact. It is not (see prior art).

---

## 9. Demo script and talk track

### Suggested structure (about 5 minutes)

1. The problem (45 s). Four landers, two years, one pattern: one wrong altitude trusted. Use part 2.
2. The idea (45 s). Three different witnesses, best two of three. Use part 1 and 4.3. A good line: with two sensors a disagreement is a coin flip, with three it is a vote.
3. Live demo (2 min). Replay 2 first, then 3.
4. Prove it (45 s). Press M. Show the pair test and the rule table.
5. Honest limits and what is next (45 s). Use part 8.

### Replay 2 script (HAKUTO-R)

1. Press 2. Say: this is the failure ispace reported. The lander flies over a crater rim and the ground drops away.
2. Watch the right side. The legacy number turns red. Say: this is the logic that rejected the correct reading and then declared that sensor dead.
3. Point at the green number. Say: Subsidium saw that the rangefinder and the camera agreed with each other and not with inertial, so it outvoted inertial and corrected it.
4. Press M. Point to the rule table: the highlighted row is "inertial fails with both others, rangefinder and camera agree".
5. Say the honest part: it takes about a second and a half to be sure, and during that time it is off by up to 38 mm on our scale.

### Replay 3 script (Resilience)

Press 3. Say: this time the sensor does not break, it slowly lags, and the old logic follows it because each step is small. Subsidium notices the rangefinder disagrees with both others.

### If asked to prove the camera is independent

Press 5 (Athena). The camera is broken on purpose and Subsidium excludes it. Say: it can vote against any one of the three, including our own camera.

### If something fails on stage

- Engine offline message: start it with `python -m so serve --sim`; the page reconnects by itself.
- No audio: press V or ignore it. The text on screen says the same thing.
- Footage missing: run the simulator replays. They need nothing downloaded.
- Have the walkthrough slides (E) ready as a fallback to talk through the whole idea with no live data.

---

## 10. Questions judges will ask

Q: Why not just add another rangefinder?
A: A second copy of the same kind of sensor tends to fail the same way, for example through interference or the same software setting. Our witnesses use different physics, so one cause rarely takes out two. Odysseus lost its rangefinders to a single switch setting.

Q: Is the camera really independent if it uses a speed from navigation?
A: Independent of the rangefinder hardware, and independent of inertial position drift. It does share the speed estimate. A speed error scales the camera altitude proportionally, while a position error does not carry over. On a real lander the speed would come from the IMU or a Doppler velocimeter. This is on our limits list.

Q: What if the camera is the sensor that fails?
A: Then the other two outvote it. Athena is the replay for that. If it just cannot see (low contrast), it abstains and we are back to two witnesses, which can detect a disagreement but not isolate it.

Q: What happens if two sensors fail at once?
A: Best-2-of-3 cannot fix that. If all three pairs fail, the system declares the situation unresolved and assumes the closest ground, which is the safest choice for braking. We say this up front: it is a safety net for single faults, not a guarantee.

Q: Why assume the closest ground rather than the average?
A: If we do not know which reading is right, the cost of thinking you are higher than you are is a hard impact. The cost of thinking you are lower is braking early. Taking the lowest reading errs toward braking.

Q: Why 9 as the limit?
A: r² is a normalised squared error. A value of 9 means the two readings are 3 standard deviations apart, which noise alone almost never produces. It is a tunable setting in `config.toml`.

Q: Why does it take over a second to react?
A: Two deliberate delays: a 0.5 s averaging window and a 0.6 s persistence timer. They stop a single bad frame from flipping the verdict. That trade-off is shown in the HAKUTO-R replay, where Subsidium's worst error is 38 mm before it recovers. A real system would tune these against its descent rate.

Q: How accurate is the camera altitude?
A: On synthetic descents, the median error is about 0.3 to 0.5%. On real footage and on the rig, read the number from the commands in part 7 before answering. Do not quote one from memory.

Q: Is this real flight data?
A: The footage is real: NASA's Blue Ghost video, orbiter images of the four sites and the missions' own broadcasts. The sensor readings in the crash replays are a scaled reconstruction of the published failures, because no public telemetry exists for those missions.

Q: How is this different from NASA SPLICE or terrain-relative navigation?
A: Those match what the vehicle sees against maps and use lidar for hazards. They are navigation systems. Subsidium is a small cross-check on the altitude the vehicle already has, needs no map and no lidar, and is meant to be added cheaply.

Q: How is this different from the ESA time-to-contact work and the patent?
A: ESA's work proposes time to contact as a way to land. The patent (US 9728094) has a camera pick between two position sensors. We use time to contact as one voter in a three-way fault-isolating vote, and we show it against the failures of four real landings.

Q: Would this have saved HAKUTO-R?
A: We cannot say. What we can show is that the logic ispace described rejects the correct reading, and that a three-way vote outvotes the wrong estimate in our reconstruction of that failure.

Q: Does it work in the dark or in shadow?
A: No camera does. It abstains when its lock quality falls below 0.3, and the system continues on the other two. Athena is partly a lesson about long shadows.

Q: Could this run on a real lander's computer?
A: The vision step is standard feature tracking at 320 pixels wide, which is light. We have only run it on laptops and have not tested it on flight hardware.

Q: What is the AI's role?
A: Documented in `docs/AI_USE.md`, as the hackathon requires. Part 13 summarises it. The team should be ready to say what each person reviewed or changed.

Q: What would you do next?
A: Measure camera accuracy on the physical rig and on more real footage, add attitude de-rotation from IMU data, and test with a real Doppler or IMU speed. (Confirm the team's actual plans before saying this on stage.)

---

## 11. Cheat sheet and glossary

### Numbers to know

| Fact | Value | Source |
|---|---|---|
| Witnesses | 3: inertial, rangefinder, camera | Design |
| Pair tests | 3 | Design |
| Agreement limit on r² | 9 (3σ) | `config.toml` |
| Averaging window | 0.5 s | `config.toml` |
| Persistence before acting | 0.6 s | `config.toml` |
| Camera look-back | 0.5 s | `config.toml` |
| Camera abstains below quality | 0.3 | `config.toml` |
| Camera noise | 4% of altitude, divided by quality | `config.toml` |
| Rangefinder noise | 3 mm + 1% | `config.toml` |
| Inertial noise | 3 mm, growing 1 mm per second | `config.toml` |
| Legacy gate | 30 mm, 30% step, fail after 10 rejections | `config.toml` |
| Injected rangefinder lag | up to 2.5 s over 4 s | `config.toml` |
| Injected camera bias | ×1.35 | `config.toml` |
| Plateau height on the rig | 60 mm | `sim.py` docstring |
| Dashboard update rate | about 15 per second | `so/server.py` |
| Replays | 5 | `scenarios/` |
| HAKUTO-R: legacy / Subsidium final error | −60 mm / 0 mm | `python -m so check` |
| Resilience: legacy / Subsidium final error | +76 mm / 0 mm | `python -m so check` |
| Synthetic camera error (median) | 0.3 to 0.5% | self-test and `tests/test_ttc.py` |
| Mission facts | HAKUTO-R: about 5 km up, crater rim about 3 km. Resilience: lost about 193 m up at about 42 m/s | Scenario files |

### Glossary

Altitude: height above the ground directly below the lander.

Abstain: the camera reports that it cannot give a trustworthy reading, so it is left out of the vote.

Chi-square test: a standard way to ask whether a gap between two noisy measurements is bigger than noise explains.

Dead reckoning: working out position by adding up movement since a known start, as inertial navigation does. It drifts over time.

Dissimilar redundancy: using different kinds of sensor so one cause cannot break all of them.

Fail-safe: when unsure, choose the option that is safest. Here that means assuming the closest ground.

Fault injection: deliberately corrupting a sensor's data in software to test how the system responds.

Inertial (NAV): altitude from accelerometers and gyros, here simulated from the stepper's step count.

Legacy gate: the textbook rejection logic, modelled on ispace's account of Mission 1.

LRO: NASA's Lunar Reconnaissance Orbiter. Its camera supplied the images of the four sites.

Optical flow: tracking how points in an image move between frames.

Parity voting: finding the faulty unit among redundant ones by comparing every pair.

Rangefinder (RF): a direct distance sensor, such as a laser or ultrasonic sensor.

Re-anchor: correcting the inertial estimate to match the other two after a confirmed terrain change.

RANSAC: a method that fits a model while ignoring outliers.

σ (sigma): one standard deviation, the size of a sensor's typical error.

Time to contact (τ): the time until the lander reaches the surface at its current speed, found from how fast the image grows: τ = Δt ÷ (s − 1).

Triplex: three redundant channels, as in aircraft flight control.

Unresolved: every pair disagrees, so no single sensor can be blamed.

---

## 12. Before you present: setup and checks

### One-time setup (no hardware)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd web && npm install && npm run build && cd ..
python -m so serve --sim            # then open http://localhost:8000
```

### Optional downloads

```bash
pip install yt-dlp imageio-ffmpeg && python tools/fetch_data.py broadcasts
python tools/fetch_data.py footage maps texture
python -m so serve --video          # real footage mode
```

These files are git-ignored, so each teammate's machine needs them if you want the real-footage views. Do this on reliable Wi-Fi before the event.

### The morning-of checklist

1. `python -m so check` prints PASS.
2. `python -m pytest tests` passes (install pytest first if needed).
3. `cd web && npm run build` succeeds.
4. Press 1 to 5 and confirm each replay finishes with the expected outcome from part 6.
5. Press M and E to confirm both screens open.
6. Test the voice (V) on the venue speakers, or plan to leave it off.
7. If you show the rig, run `python tools/cam_check.py` first (the notes ask for at least 60 tracked points and a smooth τ), and run `tools/stats.py` on the log to get its accuracy number.
8. Close other windows so the dashboard fits one screen, since the layout is designed to be read from a distance.
9. If you restarted the engine after pulling changes, rebuild the web app (`npm run build`) so the page matches the code.

### Who should be able to explain what

Make sure at least two people can cover each topic, so no one is a single point of failure.

| Topic | Parts |
|---|---|
| The problem and the four missions | 2 |
| The prior art and what is new | 3 |
| Time to contact and the camera | 4.2 |
| The vote, the pair test and the rules | 4.3, 4.4 |
| The legacy gate | 4.5 |
| The demo and the dashboard | 5, 9 |
| Evidence, limits and honesty | 7, 8 |
| The rig | 4.8 |

---

## 13. AI use and credits

The hackathon requires documented AI use and a public repository. `docs/AI_USE.md` lists what the AI assistant wrote: the engine, tests, evaluation tools, firmware draft, web dashboard, real-footage mode, crash-site data work and the redesigns. The "human changes" column is still marked "fill in as you go". Before presenting, each team member should add what they reviewed, tested or rewrote, and spot-check the altitude readings the AI transcribed from the Blue Ghost and broadcast videos. This guide and the `slides/` walkthrough were also written with AI help.

Credits to name on a slide:
- LRO images: NASA/GSFC/Arizona State University.
- Blue Ghost footage: NASA / Firefly Aerospace.
- Perseverance: NASA/JPL-Caltech. DART: NASA/Johns Hopkins APL.
- HAKUTO-R and Resilience broadcasts: © ispace.
- Odysseus and Athena broadcasts: NASA with Intuitive Machines.
- Prior art: ESA ACT (Izzo and de Croon, 2012); US patent 9728094; NASA SPLICE; Lee and Reddish, Nature, 1981.

Full credits: `data/CATALOG.md` and `footage/SOURCES.md`.
