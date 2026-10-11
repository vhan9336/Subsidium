# Second Opinion

**A camera tiebreaker for lunar lander altimeters.** Three witnesses report altitude: inertial, rangefinder and camera time-to-contact. Best 2 of 3 wins. If no single witness can be blamed, the system assumes the closest ground. Built at hackPHS 2026.

## Quick start (no hardware)
```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd web && npm install && npm run build && cd ..
python -m so serve --sim                                 # → http://localhost:8000
```
Press **1–5** to run a mission replay: Nominal, HAKUTO-R M1, Resilience, Odysseus, Athena.

## The real crashes in the replays
Each mission replay (keys 2–5) descends over NASA's orbiter image of where that lander actually came down
(`scenarios/sites/`, committed), and, once downloaded, plays the mission's own landing broadcast as the large
view with both brains' verdicts drawn over it:
```bash
pip install yt-dlp imageio-ffmpeg && python tools/fetch_data.py broadcasts
```
The sensor readings in a replay are a scaled reconstruction of the published failure, not mission telemetry.

## Real landing footage
```bash
python tools/fetch_data.py footage maps texture     # NASA videos, LRO maps, moon ground texture
python -m so serve --video                          # real footage: HAKUTO-R and Resilience on their own broadcasts and on-screen telemetry, the rest on Blue Ghost. M opens the proof screen
```
Blue Ghost Mission 1 carries NASA's on-screen altitude labels, so all three witnesses run and faults can be
injected on real Moon footage. Perseverance and DART have no usable altitude record and are tracking-only.
Press **C** to swap the camera and 3D views. Sources and credits: `data/CATALOG.md`.

Camera accuracy on that footage (the number for slides comes from this command, nothing else):
```bash
python eval/run_video.py --video footage/blue_ghost_m1_landing_scalpss.mp4 --truth eval/truth/blue_ghost_m1_callouts.csv --roi 0,424,512,344 --end 14 --calib-s 4
```

For dashboard development with hot reload, run `python -m so serve --sim` and `cd web && npm run dev` together, then open http://localhost:5173.

## Check everything
```bash
python -m pytest tests          # camera accuracy, monitor logic, all replays, record→replay
python -m so check              # scoreboard: legacy vs Second Opinion on every replay
python eval/run_video.py --selftest
```

## Real rig (later)
```bash
python -m so serve --port COM3          # or /dev/tty.usbmodem101
```

See **MASTERPROMPT.md** for the architecture, build order and facts. AI use is documented in **docs/AI_USE.md**.
