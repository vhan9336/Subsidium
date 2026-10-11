# Code tour: the parts a judge will ask about

Everything important is in `so/`. If you only read three files, read these, in this order.

## 1. The camera: `so/vision/ttc.py` (the OpenCV part)

This is where the computer vision is. `TTCEstimator.update()` takes each camera frame and returns a time to contact (tau).

1. `_prep` (line ~52): turn the frame grey, shrink it to 320 px wide, and equalize the contrast so shadows don't fool it.
2. `update` (line ~57): keep a short buffer of recent frames. Pick the newest one that is at least `lookback_s` (0.5 s) old and compare it with the current frame.
3. `_compare` (line ~75) does the real work, using three OpenCV calls:
   - `cv2.goodFeaturesToTrack` (line ~76) picks up to 400 corners that are easy to follow in the old frame.
   - `cv2.calcOpticalFlowPyrLK` (line ~79), the Lucas-Kanade tracker, finds where each corner went in the new frame.
   - `cv2.estimateAffinePartial2D` with RANSAC (line ~85) fits one similarity transform (scale, rotation, shift) to all the moved points and throws out bad matches. The **scale** `s` of that transform is how much the ground grew.
4. From the scale: `tau = dt / (s - 1)` (line ~107). If the picture grew 2% over 0.5 s, the ground arrives in 0.5 / 0.02 = 25 s. No map, no laser, no known object size.
5. `quality` (line ~92) is the share of tracked points that agreed, penalised if there were fewer than 60. Below 0.3 the camera abstains instead of guessing.
6. Safeguards (lines ~93 to 106): if the image suddenly shrinks or tau drops under 40% of its recent value, the ground just changed (a crater rim, a plateau pulled out), so the look-back window restarts. tau is the median of recent values, corrected for the fact that it shrinks 1 s per second.
7. `_hazard` (line ~114) reuses the same tracked points. A tile whose points grow faster than the whole image is closer to the camera than the ground, so its height is `1 - (s_global - 1) / (s_tile - 1)` as a fraction of altitude. `_pick_site` (line ~151) picks the flattest 3×3 neighbourhood. That is the red-to-green grid.

The camera's altitude is `tau × v`, where `v` is the descent speed. `v` comes from the stepper or servo slope in `Pipeline.descent_speed` (`so/pipeline.py`, line ~110). The camera is independent of the rangefinder hardware but still shares that speed.

## 2. The vote: `so/fusion/triplex.py`

`TriplexMonitor.step()` (line ~170) is the heart of the project.

- `witnesses` (line ~68): each sensor becomes an altitude plus an uncertainty (sigma). Camera: `tau × v`, with sigma 10% of altitude divided by lock quality (the 10% is measured on real Blue Ghost footage). Rangefinder: 3 mm + 1%. Inertial: 3 mm that grows 1 mm per second since its last correction.
- Pair test: `r² = (h_a − h_b)² / (σ_a² + σ_b²)`, averaged over 0.5 s (`pair_stats`, line ~80). Above 9 (3σ) a pair fails.
- `candidate` (line ~150) is the voting table. The sensor in both failing pairs is the odd one out. All three failing means "unresolved", and the output is the lowest reading (the closest ground, the safe choice when braking).
- `weigh_camera` (line ~132): the camera is noisy, so when inertial and the rangefinder disagree it can't settle it in one look. It builds up evidence over time instead.
- `confirmed` (line ~90): a verdict has to hold for 0.6 s, so one bad frame can't flip it.
- `fuse` (line ~97) averages the sensors that are left, trusting the precise ones more. `smooth` (line ~104) carries the answer forward with inertial between readings. The camera only votes while inertial and the rangefinder are healthy, so it doesn't blur a good answer.

## 3. The thing we compare against: `so/fusion/legacy.py`

About 50 lines. Follow inertial, accept the rangefinder only if it is within 30 mm, give up on the rangefinder for good after 10 rejections. With two sensors it can't tell which is wrong. That is what the ispace report describes for HAKUTO-R.

## How it connects

`so/pipeline.py`, `Pipeline.tick()` (line ~131), runs every frame: read a sample from the source, get tau from the camera (`read_camera`, line ~118), apply any injected fault, build one `Inputs`, feed the same `Inputs` to both brains (line ~161), score both against the true altitude, and return the state the dashboard draws.

| Where | What |
|---|---|
| `so/fusion/faults.py` | Breaks sensors on purpose (lag, freeze, drop, camera bias, camera blind) |
| `so/sources/` | Where frames and readings come from: `sim.py` (renders the camera), `video.py` (real footage), `live.py` (the Arduino rig), `replay.py` |
| `so/scenarios.py`, `scenarios/*.toml` | The replay scripts |
| `so/check.py` | The scoreboard, `python -m so check` |
| `so/server.py` | Streams the state to the browser |
| `web/src/` | The dashboard |
| `config.toml` | Every tuned number, with what it means |

## Questions a judge will probably ask

- **Where is the computer vision?** `so/vision/ttc.py`, `_compare`. Corner features, optical flow, RANSAC scale fit, then tau = dt / (s − 1).
- **Isn't the camera just another sensor?** Yes, on purpose. A third sensor with different physics turns an ambiguous disagreement into a vote.
- **What if the camera is wrong?** The other two outvote it, or it abstains when its lock quality drops below 0.3.
- **How accurate is it?** 7.2% median error on real Blue Ghost footage, 0.3% on synthetic. Both come from `python eval/run_video.py`. Say which one you mean.
- **What is not real?** The crash replays are scaled reconstructions of published failures, not mission telemetry, and the camera in the ispace replays is simulated over the real LRO photo of the site.
