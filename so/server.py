"""The web server. It runs the pipeline on a background thread and streams the result to the browser.

  GET  /              the web app (build it first: cd web && npm run build)
  WS   /ws            the state dict about 15 times a second (shape in web/src/types.ts)
  GET  /frame.jpg     the latest camera frame, with the overlay drawn on
  GET  /video         the same frames as an MJPEG stream
  POST /cmd/{name}    descend | stop | up | reset | terrain_up | terrain_down | fault:<name or clear> |
                      scenario:<id or stop> | record_start | record_stop | clip:<id>
  GET  /scenarios     the mission replays
  GET  /clips         real-footage clips (only with `serve --video`)
  GET  /proof         the tuned settings and a scorecard of every replay, for the math screen
  GET  /slides.json   the slide files in order. The files themselves are under /slides/
"""
import asyncio
import datetime
import json
import threading
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT
from .pipeline import Pipeline

WEB = ROOT / "web" / "dist"
FPS = 15       # how often the browser gets an update


def create_app(pipe: Pipeline) -> FastAPI:
    app = FastAPI(title="Subsidium")
    shared = {"state": {}, "events": [], "jpeg": b""}   # the latest tick, shared with the request threads
    lock = threading.Lock()

    def fly():
        while True:
            st = pipe.tick()
            if st is None:                       # a replay ended, or the camera hiccuped
                time.sleep(0.05)
                continue
            with lock:
                shared["state"], shared["jpeg"] = st, pipe.jpeg
                shared["events"].extend(st["events"])
                del shared["events"][:-200]

    threading.Thread(target=fly, daemon=True).start()

    # static files: built web assets, voice clips, and the images the dashboard shows
    folders = {"assets": WEB / "assets", "textures": WEB / "textures",
               "audio": ROOT / "web" / "public" / "audio", "slides": ROOT / "slides",
               "sites": ROOT / "scenarios" / "sites", "broadcasts": ROOT / "footage" / "broadcasts"}
    for name, folder in folders.items():
        if folder.exists():
            app.mount(f"/{name}", StaticFiles(directory=folder), name=name)

    @app.get("/")
    def index():
        if (WEB / "index.html").exists():
            return FileResponse(WEB / "index.html")
        return PlainTextResponse("The web app isn't built yet. Run: cd web && npm install && npm run build")

    @app.get("/slides.json")
    def slide_list():
        # a leading underscore hides a slide (see slides/README.md)
        return sorted(f.name for f in (ROOT / "slides").glob("*.html") if not f.name.startswith("_"))

    @app.get("/scenarios")
    def scenarios():
        both = hasattr(pipe.src, "use")           # footage plus simulator: say which one each replay flies on
        keys = ("id", "name", "mission", "summary", "setup", "expect", "source")
        return [{**{k: s.get(k) for k in keys},
                 "footage": s.get("footage", True) if both else pipe.src.kind == "video",
                 "clip": s.get("clip") if both and s.get("clip") in pipe.src.video.clips else None}
                for s in pipe.scenarios.values()]

    @app.get("/clips")
    def clips():
        return pipe.src.catalog() if hasattr(pipe.src, "catalog") else []

    scorecard = {"rows": None, "busy": False}

    def score_all():
        from .check import EXPECT, passed, run_one
        rows = []
        for sid, want in EXPECT.items():
            st, events = run_one(pipe.cfg, pipe.src.mm_per_step, sid)
            sc = st["score"]
            rows.append({"id": sid, "legacy_max": sc["legacy"]["max"], "legacy_last": sc["legacy"]["last"] or 0.0,
                         "so_max": sc["so"]["max"], "so_last": sc["so"]["last"] or 0.0,
                         "ok": passed(st, events, want), "events": sorted({e for _, e in events})})
        scorecard["rows"] = rows

    @app.get("/proof")
    def proof():
        # the scorecard takes a few seconds, so compute it once in the background and let the page poll
        if scorecard["rows"] is None and not scorecard["busy"]:
            scorecard["busy"] = True
            threading.Thread(target=score_all, daemon=True).start()
        c = pipe.cfg
        return {"config": {**{k: c[k] for k in ("sensors", "monitor", "legacy", "faults")},
                           "camera": {k: c["camera"][k] for k in ("lookback_s", "min_quality")}},
                "scorecard": scorecard["rows"]}

    @app.post("/cmd/{name}")
    def cmd(name: str):
        if name == "record_start":
            pipe.start_recording(str(ROOT / "sessions" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
        else:
            pipe.command(name)
        return {"ok": True}

    def latest_jpeg() -> bytes:
        with lock:
            return shared["jpeg"]

    @app.get("/frame.jpg")
    def frame():
        jpg = latest_jpeg()
        return Response(jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"},
                        status_code=200 if jpg else 503)

    @app.get("/video")
    def video():
        def stream():
            while True:
                jpg = latest_jpeg()
                if jpg:
                    yield b"--f\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
                time.sleep(1 / FPS)
        return StreamingResponse(stream(), media_type="multipart/x-mixed-replace; boundary=f")

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        with lock:
            seen = len(shared["events"])            # only send events that happen after we connect
        try:
            while True:
                with lock:
                    st = dict(shared["state"])
                    events = shared["events"]
                    new, seen = events[min(seen, len(events)):], len(events)
                if st:
                    st["events"] = new
                    await sock.send_text(json.dumps(st))
                await asyncio.sleep(1 / FPS)
        except WebSocketDisconnect:
            pass

    return app
