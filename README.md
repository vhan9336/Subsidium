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

Press 1 to 5 to run a replay: Nominal, HAKUTO-R M1, Resilience, Odysseus, Athena. With `--video` (below), 6 and 7 play the real footage clips. The bar under the picture restarts the replay, pauses it and scrubs back through the last minute. Press M for the math behind the verdict and E for the presentation.

| Key | Does |
|---|---|
| 1 to 5 | Run a mission replay |
| 6, 7 | Play a real footage clip (Blue Ghost, Perseverance), when started with `--video` |
| M | Show or hide the math screen |
| E | Open the Canva presentation (set `canva_url` in `config.toml`, or paste the link the first time) |
| Space | Pause or resume the run |
| Left, right | Step back or forward one second (this pauses the run) |
| C | Swap the camera and 3D views |
| V | Voice callouts on or off |
| D, S, U, R | Descend, stop, up, reset |
| T, Y | Slide the 60 mm plateau in or out under the lander |
| 0 | Clear injected sensor faults |

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

## The rig

A webcam and an ultrasonic sensor hang from a stepper winch over a textured floor, and a box slides under it to make the plateau. The firmware is in `firmware/rig/rig.ino` and has not been run on hardware yet.

```bash
python -m so serve --port COM3          # or /dev/tty.usbmodem101
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
