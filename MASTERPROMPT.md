# MASTERPROMPT — Subsidium (hackPHS 2026)

> Paste this into your AI coding assistant at the start of every session
> (or save it as `CLAUDE.md` / `.cursorrules` in the repo root).

## What we are building
**Subsidium** is a 2-of-3 altitude integrity monitor for lunar landers.

Recent commercial Moon landers crashed or tipped because they trusted the wrong altitude source (details in "Facts" below). We add a third, independent witness: a downward camera that measures **time-to-contact** (τ) from how fast the ground image expands. τ × descent rate = an altitude estimate that shares no hardware with the rangefinder.

Three witnesses vote:
- **inertial (NAV)**
- **rangefinder (RF)**
- **camera (CAM)**

The odd one out is excluded. If the disagreement can't be pinned on one witness, the system assumes the closest ground (fail-safe).

The dashboard runs two brains on the **same** sensor stream:
- **Legacy gate:** the textbook logic that crashed HAKUTO-R.
- **Subsidium:** ours.

The demo replays four real failures. The software runs first on a simulator; a tabletop rig (webcam plus ultrasonic sensor on a stepper winch) comes **last**.

## Hard rules for the assistant
1. **Do not rewrite working engine code** in `so/` unless a test proves a bug. Extend it.
2. **Keep the data contract in sync:** `so/pipeline.py` builds the state dict; `web/src/types.ts` mirrors it. If you change one, change the other.
3. Before saying something is "done", these must pass:
   - `python -m pytest tests`
   - `python -m so check`
   - `cd web && npm run build`
4. **Software first, hardware last.** Never block software work on the rig.
5. **No runtime CDNs or cloud calls in the demo path.** Venue Wi-Fi is unreliable. ElevenLabs clips are generated ahead of time into `web/public/audio/`.
6. **No new heavy dependencies** without a reason. Pin exact versions.
7. **Honest claims only.** No "NASA-approved" and no invented accuracy numbers. Every number on a slide comes from `tools/stats.py` or `eval/run_video.py` output.
8. The hackathon requires **documented AI use** and a **public repo**. Log what the AI wrote in `docs/AI_USE.md` as you go.

## Tech stack
| Layer | Choice | Where |
|---|---|---|
| Vision | Python 3.11+, OpenCV, NumPy (feature tracking → similarity fit → τ = Δt/(s−1); per-tile hazard map) | `so/vision/ttc.py` |
| Integrity monitor | Python: chi-square pair tests + triplex parity voting | `so/fusion/triplex.py` |
| Baseline brain | Python: textbook innovation gate | `so/fusion/legacy.py` |
| Fault injection | Python (rf_lag, rf_freeze, rf_drop, cam_bias, cam_blind) | `so/fusion/faults.py` |
| Sources | Simulator / live rig (pyserial + webcam) / recorded replay | `so/sources/` |
| Mission replays | TOML scripts | `scenarios/*.toml` |
| Server | FastAPI + WebSocket (state ~15 Hz) + MJPEG video | `so/server.py` |
| Web app | React 18 + Vite 5 + TypeScript 5; three.js via @react-three/fiber 8 + drei 9 | `web/` |
| Voice | ElevenLabs (pre-generated mp3) with browser speech fallback | `tools/make_callouts.py`, `web/src/voice.ts` |
| Real-data eval | OpenCV on Perseverance / Apollo footage vs true time-to-touchdown | `eval/run_video.py` |
| Tests | pytest | `tests/` |
| Firmware (last) | Arduino C++: stepper winch + Grove ultrasonic, no libraries | `firmware/rig/rig.ino` |
| Config | TOML (noise models, gates, rig constants) | `config.toml` |

## How data flows
```
Source (sim | live rig | replay) ──Sample{frame, rf_raw, steps, true_alt, h0}──▶ Pipeline.tick()
  ├─ navigation: h_nav = h0 − steps·mm_per_step ; v = d(steps)/dt   (stands in for IMU/Doppler)
  ├─ TTCEstimator(frame) → τ, quality, hazard grid, landing site
  ├─ FaultInjector → corrupted rf / τ  (raw values kept as ground truth)
  ├─ LegacyGate.step()      → belief
  ├─ TriplexMonitor.step()  → belief + σ + pair tests + exclusions + events
  └─ state dict ──WebSocket──▶ React app      camera+overlay ──MJPEG /video──▶ <img>
```
Commands go `POST /cmd/{name}`:
- Motion: `descend | stop | up | reset`
- Terrain: `terrain_up | terrain_down`
- Faults: `fault:<mode|clear>`
- Replays: `scenario:<id|stop>`
- Recording: `record_start | record_stop`

## Directory (status)
```
so/                 ENGINE — DONE, tested
  vision/ttc.py       time-to-contact + hazard map
  fusion/             triplex.py (ours), legacy.py, faults.py, types.py
  sources/            sim.py, live.py (rig), replay.py (record + replay)
  pipeline.py         the flight loop + state dict
  server.py           FastAPI app
  scenarios.py        mission replay runner
  check.py            `python -m so check` headless scoreboard
  __main__.py         CLI: `python -m so serve --sim | --port COM3 | --replay DIR`
scenarios/          5 replays: nominal, HAKUTO-R M1, Resilience, Odysseus IM-1, Athena IM-2 — DONE
web/                React app — STARTER (wired to live data, plain UI). BUILD THIS OUT.
  src/types.ts        state contract (mirror of pipeline.py)
  src/telemetry.ts    WebSocket hook + rolling 20 s history + cmd()
  src/voice.ts        callout lines, verdict banners, audio playback
  src/App.tsx         starter layout — replace placeholders with components below
web-lite/           single-file fallback dashboard (/lite) — keep working, don't extend
eval/run_video.py   real-footage scorer — DONE (`--selftest` passes); needs real data
tools/              make_callouts.py (ElevenLabs), stats.py (receipts), cam_check.py (webcam test)
firmware/rig/       Arduino sketch — written, NOT yet run on hardware
tests/              pytest: camera accuracy, monitor logic, all replays, record→replay
config.toml         all tunables
docs/               AI_USE.md (keep updated)
```

## Build order (2 people, software first)
**Person A: web app** (`web/src/components/`)
1. **Scene3D.tsx** (three.js), the hero visual. 1 unit = 100 mm.
   - Ground plane with a moon texture.
   - Solid true lander at `truth`.
   - Translucent **ghost landers**: red at `legacy.est`, green at `so.est`, with a ±σ band (`so.sigma`).
   - Rangefinder beam from the true lander, length = `rf`. It ends above or below the ground when the rangefinder is wrong.
   - Camera frustum: cyan, grey when `so.cam_abstain`.
   - Excluded sensors drawn dashed or grey.
   - Slow auto-orbit; draggable (OrbitControls).
   - *Done when* the HAKUTO-R replay visibly shows the red ghost ~6 cm too low and the green ghost on the true lander.
2. **VoteTriangle.tsx** (SVG).
   - Nodes NAV / RF / CAM with live altitudes from `so.witness`.
   - Edges = `so.pairs`, green if ≤ `so.gate`, red if above, each labelled with its value.
   - Excluded node crossed out. Camera node dashed while abstaining.
   - *Done when* every replay's verdict can be read off the triangle alone.
3. **AltitudePlot.tsx** (canvas, no chart library). Last 20 s from `history`:
   - truth (dotted white), rf (amber), nav (slate dashed), cam (cyan)
   - legacy belief (red, thick), Subsidium belief (green, thick) with σ band
4. **BrainCard / ScenarioPanel polish.**
   - Show the scenario summary, the expected outcome and the operator **cue** in large text.
   - Show the scoreboard (`score.legacy/so.max` and `.last`).
5. Keyboard: `1–5` replays, `D S U R`, `T/Y` plateau in/out, `0` clear faults. Big readable type for a projector.

**Person B: engine, data, voice**
1. **Real-footage validation.** Download Perseverance landing footage (downward EDL camera; raw frames on mars.nasa.gov raw images).
   - Use the sky-crane phase, where the descent rate is roughly constant. Find the touchdown frame.
   - Run `python eval/run_video.py --video ... --touchdown T --start ... --roi ...`.
   - Keep the PNG for the slides. Optionally do Apollo 11: fill `eval/truth/apollo11_template.csv` from the ALSJ transcript callouts (t, alt, rate).
2. **LRO texture:** `python -m so serve --sim --texture lro_nac.png` (use an LRO NAC image) so the sim looks like the Moon.
3. **Voice:** `ELEVENLABS_API_KEY=... python tools/make_callouts.py` writes to `web/public/audio/`. Lines live in `voice.ts` and `make_callouts.py`, so keep them identical.
4. **Backups:** record each replay with `record_start` / `record_stop`; replay with `python -m so serve --replay sessions/<dir>`.
5. Optional: tune `config.toml` if the camera is noisy on real footage (`cam_sigma_rel` ≈ 2× measured median error).

**Hardware (last, only after the software demo is solid)**
1. Flash `firmware/rig/rig.ino`. The Serial Monitor at 115200 should print `R,<ms>,<mm>,<steps>`. Match the stepper code to the actual Grove driver board.
2. Measure mm per step and set `rig.spool_mm` in config.
3. Check the webcam with `python tools/cam_check.py`: ≥60 tracked points with a smooth τ.
4. Run `python -m so serve --port <PORT>`, then do the replays physically. The plateau box slides OUT for HAKUTO-R.
5. Use `python tools/stats.py flight_log.jsonl` to get the real accuracy number for the slides.

## Facts (use these; don't invent others)
- **HAKUTO-R M1 (ispace, Apr 2023):** passing a ~3 km crater rim, the measured altitude **rose sharply**. The software judged the correct reading abnormal and filtered it out, and the lander believed it was at the surface while ~5 km up. Replay = plateau slides **out**.
- **Resilience (ispace, Jun 2025):** the laser rangefinder degraded and valid measurements came too late. Telemetry was lost ~193 m up at ~42 m/s.
- **Odysseus IM-1 (Feb 2024):** the rangefinders never fired because a safety-enable switch wasn't disabled before launch. The team improvised with NASA's experimental lidar; the lander tipped over.
- **Athena IM-2 (Mar 2025):** altimeter interference plus long shadows and low sun challenged the landing system; it landed on its side. **Cameras fail too**, which is why ours can be outvoted and abstains in low contrast.
- **Prior art to credit:**
  - ESA ACT (Izzo & de Croon, 2012): time-to-contact landing.
  - US patent 9728094: a camera choosing between two position sensors.
  - NASA SPLICE: terrain-relative navigation and lidar hazard detection.
  - ispace has said it will add visual navigation.
- **Our claim:** a cheap, dissimilar, scale-free cross-check using best-2-of-3 voting, aimed at the failure behind four recent landings. **Not** a new landing method.
- **Limits to state:** terminal descent only; real landers need IMU de-rotation for attitude; dust and lighting; on the rig the stepper stands in for IMU/Doppler velocity.

## UI style
Dark, calm, mission-console. Tokens are in `web/src/styles.css`:
- `--truth #f2f2f2`, `--rf #f2b84b`, `--nav #7d8fa6`, `--cam #4fd1e8`, `--legacy #ff5d5d`, `--so #5be38a`

Use the same colour for the same thing everywhere (3D, triangle, plot, cards). Monospace numbers. The judge must read the verdict from 3 m away.
