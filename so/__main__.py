"""Command line.

  python -m so serve --sim [--texture lro.png]    the simulator, no hardware needed
  python -m so serve --video [clip]               real landing footage as the camera
  python -m so serve --port COM3 [--cam 0]        the real rig
  python -m so serve --replay sessions/2026...    play back a recorded session
  python -m so check                              score both brains on every replay
"""
import argparse
import math

from .config import load


def build_source(args, cfg, mm_per_step):
    """Pick the source the command line asked for. Imports are local so unused ones never load."""
    if args.sim:
        from .sources.sim import SimSource
        return SimSource(mm_per_step, texture=args.texture, render=(640, 480))
    if args.video is not None:
        from .sources.hybrid import HybridSource
        from .sources.sim import SimSource
        from .sources.video import VideoSource
        # replays that need a moving ground can't run on recorded footage, so the simulator covers them
        return HybridSource(VideoSource(mm_per_step, args.video or None), SimSource(mm_per_step, render=(640, 480)))
    if args.replay:
        from .sources.replay import ReplaySource
        return ReplaySource(args.replay, loop=True)
    from .sources.live import LiveSource
    cam = cfg["camera"]
    return LiveSource(args.port, mm_per_step, args.cam if args.cam is not None else cam["index"],
                      cam["width"], cam["height"], cfg["rig"]["baud"])


def main():
    ap = argparse.ArgumentParser(prog="so")
    sub = ap.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve")
    which = serve.add_mutually_exclusive_group(required=True)
    which.add_argument("--sim", action="store_true")
    which.add_argument("--port", help="Arduino serial port, like COM3 or /dev/tty.usbmodem101")
    which.add_argument("--replay", help="a session folder")
    which.add_argument("--video", nargs="?", const="", metavar="CLIP",
                       help="real footage as the camera (a clip id from clips.toml; the first one if left out)")
    serve.add_argument("--cam", type=int, help="webcam index")
    serve.add_argument("--texture", help="photo to use as the simulated ground, like an LRO frame")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--http-port", type=int, default=8000)
    sub.add_parser("check")
    args = ap.parse_args()

    cfg = load()
    # how far the winch lowers the sled per motor step
    mm_per_step = math.pi * cfg["rig"]["spool_mm"] / cfg["rig"]["steps_per_rev"]
    if args.cmd == "check":
        from .check import run_all
        raise SystemExit(0 if run_all(cfg, mm_per_step) else 1)

    import uvicorn

    from .pipeline import Pipeline
    from .server import create_app
    src = build_source(args, cfg, mm_per_step)
    print(f"Subsidium ({src.kind}) → http://localhost:{args.http_port}")
    uvicorn.run(create_app(Pipeline(cfg, src)), host=args.host, port=args.http_port, log_level="warning")


if __name__ == "__main__":
    main()
