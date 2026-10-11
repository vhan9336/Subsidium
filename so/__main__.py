"""Command line.

  python -m so serve --sim [--texture lro.png]        simulator, no hardware
  python -m so serve --video [blue_ghost]             real landing footage as the camera
  python -m so serve --port COM3 [--cam 0]            real rig
  python -m so serve --replay sessions/2026...        re-run a recorded session
  python -m so check                                  run every mission replay headless and score both brains
"""
from __future__ import annotations

import argparse
import math

from .config import load


def main():
    ap = argparse.ArgumentParser(prog="so")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--sim", action="store_true")
    g.add_argument("--port", help="Arduino serial port, e.g. COM3 or /dev/tty.usbmodem101")
    g.add_argument("--replay", help="session folder")
    g.add_argument("--video", nargs="?", const="", metavar="CLIP",
                   help="real landing footage as the camera (clip id from clips.toml; default: the first)")
    s.add_argument("--cam", type=int, default=None)
    s.add_argument("--texture", help="image file for the simulated ground (e.g. an LRO NAC frame)")
    s.add_argument("--config", default=None)
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--http-port", type=int, default=8000)
    c = sub.add_parser("check")
    c.add_argument("--config", default=None)
    args = ap.parse_args()
    cfg = load(args.config)
    mmps = math.pi * cfg["rig"]["spool_mm"] / cfg["rig"]["steps_per_rev"]

    if args.cmd == "check":
        from .check import run_all
        raise SystemExit(0 if run_all(cfg, mmps) else 1)

    import uvicorn

    from .pipeline import Pipeline
    from .server import create_app
    if args.sim:
        from .sources.sim import SimSource
        src = SimSource(mmps, texture=args.texture, render=(640, 480))
    elif args.video is not None:
        from .sources.hybrid import HybridSource
        from .sources.sim import SimSource
        from .sources.video import VideoSource
        # the simulator stands in for the replays recorded footage cannot carry (a moving ground)
        src = HybridSource(VideoSource(mmps, args.video or None), SimSource(mmps, render=(640, 480)))
    elif args.replay:
        from .sources.replay import ReplaySource
        src = ReplaySource(args.replay, loop=True)
    else:
        from .sources.live import LiveSource
        cam = cfg["camera"]
        src = LiveSource(args.port, mmps, args.cam if args.cam is not None else cam["index"],
                         cam["width"], cam["height"], cfg["rig"]["baud"])
    app = create_app(Pipeline(cfg, src))
    print(f"Subsidium ({src.kind}) → http://localhost:{args.http_port}")
    uvicorn.run(app, host=args.host, port=args.http_port, log_level="warning")


if __name__ == "__main__":
    main()
