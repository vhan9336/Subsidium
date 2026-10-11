# Subsidium

A camera tiebreaker for lunar lander altimeters. Built at hackPHS 2026 for the theme "Into the Skies".

A lander about to touch down on the Moon has to know how high it is. It gets that from an inertial unit and a laser rangefinder, and when the two disagree, the software has to pick one. In the last few years four commercial landers got that choice wrong or had no way to make it: HAKUTO-R Mission 1 (2023), Odysseus (2024), Athena (2025) and Resilience (2025).

Subsidium adds a third witness, a downward camera. The camera watches how fast the ground grows in the picture, which gives the time until contact. Multiply that by the descent speed and you get an altitude that shares no hardware with the rangefinder. The three witnesses vote, and the odd one out is ignored. If no single sensor can be blamed, the system assumes the closest ground.

The dashboard runs two brains on the same sensor stream: the textbook gate that matches what ispace described for HAKUTO-R, and Subsidium. You can watch the old logic end up wrong while Subsidium stays on the true altitude.

This is a cross-check on the altitude a lander already has, not a new way to land. It covers terminal descent only, and the replays are scaled reconstructions of the published failures, not mission telemetry.

## Run it (no hardware needed)

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd web && npm install && npm run build && cd ..
python -m so serve --sim                                 # then open http://localhost:8000
```

The number keys run the numbered strip: the Nominal baseline, the real footage clips (with `--video`, below), then the four crashes (Odysseus, Athena, HAKUTO-R M1, Resilience). The bar under the picture restarts the replay, pauses it and scrubs back through the last minute. Press M for the math behind the verdict and E for the presentation.

| Key | Does |
|---|---|
| 1 to 7 | The numbered strip, in this order: Nominal baseline, the two real footage clips (only with `--video`), then Odysseus, Athena, HAKUTO-R and Resilience. Without `--video` the numbers just skip the footage |
| M | Show or hide the math screen |
| E | Open the Canva presentation (set `canva_url` in `config.toml`, or paste the link the first time) |
| Space | Pause or resume the run |
| Left, right | Step back or forward one second (this pauses the run) |
| C | Swap the camera and 3D views |
| V | Voice callouts on or off |
| D, S, U, R | Descend, stop, up, reset |
| T, Y | Slide the 60 mm plateau in or out under the lander |
| 0 | Clear injected sensor faults |
| J | Switch to the live rig, when the engine is started with `--rig` |

## The real crashes in the replays

Each mission replay (keys 2 to 5) descends over NASA's orbiter photo of where that lander really came down (`scenarios/sites/`). Once you download the mission's own landing broadcast, it plays as the large view with both brains' verdicts drawn over it:

```bash
pip install yt-dlp imageio-ffmpeg && python tools/fetch_data.py broadcasts
```

## Real landing footage

```bash
python tools/fetch_data.py footage maps texture     # NASA videos, LRO maps and the moon ground texture
python -m so serve --video                          # footage as the camera, HAKUTO-R and Resilience on their own broadcasts
```

Blue Ghost Mission 1 carries NASA's on-screen altitude labels, so all three witnesses run on real Moon footage and you can inject faults into it. Perseverance and DART have no usable altitude record, so they only show camera tracking. Sources and credits are in `data/CATALOG.md`.

To score the camera on that footage (quote accuracy numbers from this command and nothing else):

```bash
python eval/run_video.py --video footage/blue_ghost_m1_landing_scalpss.mp4 --truth eval/truth/blue_ghost_m1_callouts.csv --roi 0,424,512,344 --end 14 --calib-s 4
```

## Check everything

```bash
python -m pytest tests              # camera accuracy, voting logic, every replay, record then replay
python -m so check                  # legacy gate against Subsidium on every replay
python eval/run_video.py --selftest
```

For work on the dashboard with hot reload, run `python -m so serve --sim` and `cd web && npm run dev` together, then open http://localhost:5173.

## The live rig demonstration

A servo winch lowers a sled over a textured floor. An ultrasonic sensor stands in for the laser rangefinder, the servo angle stands in for the inertial unit, and a webcam looking down gives the camera. The Arduino sketch is `firmware/rig/rig.ino`.

```bash
python -m so serve --video --rig auto                 # --rig takes a port too, like COM3 or /dev/ttyACM0
python -m so serve --video --rig auto --cam 1         # if the laptop's own camera is number 0
```

Press **J** to switch to the rig, and J again to come back. While it's live:

| Key | Does |
|---|---|
| D | Demo descent: the sled creeps down and stops when the sensor says the legs are on the ground |
| U or R | Back to the top. R also zeros the starting altitude from the sensor |
| S | Stop where it is |
| X | Engine cut: the servo drops to the bottom at once (the crash drop) |
| 4 to 7 | Run a replay script on the rig. The plateau steps show up as a big amber cue for whoever works the box |
| T, Y | These do nothing on the rig. Slide the box by hand when the cue says so |

The fault buttons (rangefinder lag, freeze, silent, camera bias, camera blind) corrupt the live readings in software, so you can break a real sensor on cue. The altitude each brain is scored against is the raw ultrasonic reading.

The ultrasonic-only sketch (`firmware/ultrasonic/ultrasonic.ino`, no motor) works too: `rig.motor = false` in `config.toml` is the default. Lower the sensor and webcam by hand while you run it. D, U and X do nothing, because there is nothing to move, and the inertial reading and speed are derived from the ultrasonic. For the servo winch set `motor = true`.

Set `rig.mm_per_tenth` in `config.toml` to the millimetres of sled travel per tenth of a degree. The sketch assumes about 1 mm per degree, which is 0.1.

To try the whole thing with nothing plugged in, run the pretend Arduino and point a video file at it as the webcam:

```bash
python tools/fake_rig.py                              # prints a port, like /dev/pts/4
python -m so serve --video --rig /dev/pts/4 --cam footage/blue_ghost_m1_landing_scalpss.mp4
```

## Where things are

| Path | What |
|---|---|
| `so/` | The engine: camera vision, the voting monitor, the legacy gate, fault injection, sources, server |
| `web/` | The dashboard (React, three.js) |
| `scenarios/`, `clips.toml` | The five replays and the real-footage clips |
| `tests/`, `eval/`, `tools/` | Tests, camera scoring, data downloads |
| `config.toml` | Every tunable setting, with the noise models |
| `docs/AI_USE.md` | How AI was used in this project |

See `MASTERPROMPT.md` for the original architecture notes.
