"""FastAPI server: runs the pipeline on a background thread and streams it to the browser.

  GET  /            web app (web/dist if built, else web-lite fallback)
  GET  /video       MJPEG camera feed with hazard overlay
  GET  /frame.jpg   the latest camera frame on its own (what the dashboard polls)
  WS   /ws          state at ~15 Hz (see web/src/types.ts)
  POST /cmd/{name}  descend | stop | up | reset | terrain_up | terrain_down |
                    fault:<rf_lag|rf_freeze|rf_drop|cam_bias|cam_blind|clear> |
                    scenario:<id|stop> | record_start | record_stop | clip:<id>
  GET  /scenarios   mission replay list
  GET  /clips       real-footage clips (only with `serve --video`)
  GET  /proof       tuned constants + headless scorecard for the proof screen
"""
from __future__ import annotations

import asyncio
import datetime
import json
import threading
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT
from .pipeline import Pipeline


def create_app(pipe: Pipeline, loop_replay: bool = False) -> FastAPI:
    app = FastAPI(title="Second Opinion")
    shared = {"state": {}, "events": [], "jpeg": b""}
    lock = threading.Lock()

    def run():
        while True:
            st = pipe.tick()
            if st is None:                      # replay finished or camera hiccup
                time.sleep(0.05)
                continue
            with lock:
                shared["state"], shared["jpeg"] = st, pipe.jpeg
                shared["events"].extend(st["events"])
                del shared["events"][:-200]

    threading.Thread(target=run, daemon=True).start()

    dist = ROOT / "web" / "dist"
    audio = ROOT / "web" / "public" / "audio"
    if audio.exists():
        app.mount("/audio", StaticFiles(directory=audio), name="audio")
    for sub in ("assets", "textures"):
        if (dist / sub).exists():
            app.mount(f"/{sub}", StaticFiles(directory=dist / sub), name=sub)

    for name, folder in (("sites", ROOT / "scenarios" / "sites"), ("broadcasts", ROOT / "footage" / "broadcasts")):
        if folder.exists():
            app.mount(f"/{name}", StaticFiles(directory=folder), name=name)

    @app.get("/")
    def index():
        f = dist / "index.html"
        return FileResponse(f if f.exists() else ROOT / "web-lite" / "index.html")

    @app.get("/lite")
    def lite():
        return FileResponse(ROOT / "web-lite" / "index.html")

    @app.get("/scenarios")
    def scenarios():
        both = hasattr(pipe.src, "use")           # footage + simulator: say which one each replay flies on
        return [{**{k: s.get(k) for k in ("id", "name", "mission", "summary", "setup", "expect", "source")},
                 "footage": s.get("footage", True) if both else pipe.src.kind == "video",
                 "clip": s.get("clip") if both and s.get("clip") in pipe.src.video.clips else None}
                for s in pipe.scenarios.values()]

    @app.get("/clips")
    def clips():
        return pipe.src.catalog() if hasattr(pipe.src, "catalog") else []

    card = {"rows": None, "busy": False}

    def score():
        from .check import EXPECT, run_one
        rows = []
        for sid, want in EXPECT.items():
            st, events = run_one(pipe.cfg, pipe.src.mm_per_step, sid)
            sc, names = st["score"], {e for _, e in events}
            rows.append({"id": sid, "legacy_max": sc["legacy"]["max"], "legacy_last": sc["legacy"]["last"] or 0.0,
                         "so_max": sc["so"]["max"], "so_last": sc["so"]["last"] or 0.0,
                         "ok": want <= names and abs(sc["so"]["last"] or 0) < 12, "events": sorted(names)})
        card["rows"] = rows

    @app.get("/proof")
    def proof():
        """The tuned constants and the headless scorecard (`python -m so check`), for the proof screen."""
        if card["rows"] is None and not card["busy"]:
            card["busy"] = True
            threading.Thread(target=score, daemon=True).start()
        c = pipe.cfg
        return {"config": {**{k: c[k] for k in ("sensors", "monitor", "legacy", "faults")},
                           "camera": {k: c["camera"][k] for k in ("lookback_s", "min_quality")}},
                "scorecard": card["rows"]}

    @app.post("/cmd/{name}")
    def cmd(name: str):
        if name == "record_start":
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            pipe.start_recording(str(ROOT / "sessions" / stamp))
        else:
            pipe.command(name)
        return {"ok": True}

    @app.get("/frame.jpg")
    def frame():
        with lock:
            jpg = shared["jpeg"]
        return Response(jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"},
                        status_code=200 if jpg else 503)

    @app.get("/video")
    def video():
        def gen():
            while True:
                with lock:
                    jpg = shared["jpeg"]
                if jpg:
                    yield b"--f\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
                time.sleep(1 / 15)
        return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=f")

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        with lock:
            seen = len(shared["events"])
        try:
            while True:
                with lock:
                    st = dict(shared["state"])
                    ev = shared["events"]
                    new, seen = ev[min(seen, len(ev)):], len(ev)
                if st:
                    st["events"] = new
                    await sock.send_text(json.dumps(st))
                await asyncio.sleep(1 / 15)
        except WebSocketDisconnect:
            pass

    return app
