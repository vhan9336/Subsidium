"""The web server. It runs the pipeline on a background thread and streams the result to the browser.

  GET  /              the web app (build it first: cd web && npm run build)
  WS   /ws            the state dict about 15 times a second (shape in web/src/types.ts)
  GET  /frame.jpg     the latest camera frame, with the overlay drawn on
  GET  /video         the same frames as an MJPEG stream
  POST /cmd/{name}    descend | stop | up | reset | terrain_up | terrain_down | fault:<name or clear> |
                      scenario:<id or stop> | record_start | record_stop | clip:<id> |
                      pause | resume | restart | seek:<n>   (playback: seek scrubs back through the last minute)
  GET  /scenarios     the mission replays
  GET  /clips         real-footage clips (only with `serve --video`)
  GET  /proof         the tuned settings and a scorecard of every replay, for the math screen
  GET  /presentation.json   the Canva link for the walkthrough, from config.toml (can be empty)
"""
import asyncio
import collections
import copy
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
HISTORY = 900  # states and frames kept for scrubbing: about a minute at 15 per second


def create_app(pipe: Pipeline) -> FastAPI:
    app = FastAPI(title="Subsidium")
    shared = {"state": {}, "events": [], "jpeg": b"", "paused": False, "cursor": None}
    lock = threading.Lock()
    # Every other tick is kept as a (state, frame) pair, so the dashboard can scrub back through the run.
    history = collections.deque(maxlen=HISTORY)

    def fly():
        ticks = 0
        while True:
            if shared["paused"]:
                time.sleep(0.05)
                continue
            st = pipe.tick()
            if st is None:                       # a replay ended, or the camera hiccuped
                time.sleep(0.05)
                continue
            with lock:
                if history and st["t"] < history[-1][0]["t"]:
                    history.clear()              # time went backwards, so a replay or clip looped
                    shared["cursor"] = None
                ticks += 1
                if ticks % 2 == 0:
                    # the score dict is reused every tick, so keep a copy of what it said at this moment
                    history.append(({**st, "score": copy.deepcopy(st["score"])}, pipe.jpeg))
                shared["state"], shared["jpeg"] = st, pipe.jpeg
                shared["events"].extend(st["events"])
                del shared["events"][:-200]

    threading.Thread(target=fly, daemon=True).start()

    # static files: built web assets, voice clips, and the images the dashboard shows
    folders = {"assets": WEB / "assets", "textures": WEB / "textures",
               "audio": ROOT / "web" / "public" / "audio",
               "sites": ROOT / "scenarios" / "sites", "broadcasts": ROOT / "footage" / "broadcasts"}
    for name, folder in folders.items():
        if folder.exists():
            app.mount(f"/{name}", StaticFiles(directory=folder), name=name)

    @app.get("/")
    def index():
        if (WEB / "index.html").exists():
            return FileResponse(WEB / "index.html")
        return PlainTextResponse("The web app isn't built yet. Run: cd web && npm install && npm run build")

    @app.get("/presentation.json")
    def presentation():
        return {"url": pipe.cfg.get("presentation", {}).get("canva_url", "")}

    @app.get("/scenarios")
    def scenarios():
        both = hasattr(pipe.src, "use")           # footage plus simulator: say which one each replay flies on
        keys = ("id", "name", "mission", "summary", "setup", "expect", "source")
        return [{**{k: s.get(k) for k in keys},
                 "footage": (s.get("footage", True) and s.get("clip") in (None, *pipe.src.video.clips)) if both
                            else pipe.src.kind == "video",
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

    def playback(name: str):
        """Pause, resume, restart and seek. These act on the server's loop, not on the engine."""
        with lock:
            if name == "pause":
                shared["paused"] = True
            elif name.startswith("seek:") and history:
                shared["paused"] = True          # scrubbing freezes the run where it is
                shared["cursor"] = min(max(int(name[5:]), 0), len(history) - 1)
            else:                                # resume or restart: go live again
                shared["cursor"] = None
                pipe.src.resync()                # so the time spent paused isn't counted
                if name == "restart":
                    history.clear()
                    pipe.command("restart")
                shared["paused"] = False

    @app.post("/cmd/{name}")
    def cmd(name: str):
        if name in ("pause", "resume", "restart") or name.startswith("seek:"):
            playback(name)
        elif name == "reset" or name.startswith(("scenario:", "clip:")):
            with lock:                       # a new run starts the playback clock from zero, and un-pauses
                history.clear()
                shared["cursor"] = None
                pipe.src.resync()
                shared["paused"] = False
            pipe.command(name)
        elif name == "record_start":
            pipe.start_recording(str(ROOT / "sessions" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
        else:
            pipe.command(name)
        return {"ok": True}

    def latest_jpeg() -> bytes:
        with lock:
            return history[shared["cursor"]][1] if shared["cursor"] is not None else shared["jpeg"]

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
                    cursor = shared["cursor"]
                    events = shared["events"]
                    new, seen = events[min(seen, len(events)):], len(events)
                    st = dict(history[cursor][0] if cursor is not None else shared["state"])
                    st["playback"] = {"paused": shared["paused"], "n": len(history),
                                      "cursor": len(history) - 1 if cursor is None else cursor,
                                      "t0": history[0][0]["t"] if history else st.get("t", 0),
                                      "t1": history[-1][0]["t"] if history else st.get("t", 0)}
                if st.get("t") is not None:
                    st["events"] = [] if cursor is not None else new    # scrubbing mustn't replay old callouts
                    await sock.send_text(json.dumps(st))
                await asyncio.sleep(1 / FPS)
        except WebSocketDisconnect:
            pass

    return app
