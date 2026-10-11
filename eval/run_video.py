"""Score the camera time-to-contact estimator on real landing footage.

Ground truth is time-to-touchdown, which tau should equal directly (no scale needed):
  --touchdown T      the video time (s) of touchdown; assumes roughly constant descent rate
                     over the evaluated span (e.g. Perseverance's sky-crane phase)
  --truth file.csv   columns t,alt,rate (any consistent units) -> truth tau = alt / rate,
                     linearly interpolated (e.g. Apollo callouts aligned to the film)

Examples
  python eval/run_video.py --video rdlc.mp4 --touchdown 41.2 --start 20 --end 40
  python eval/run_video.py --frames raw_edl/ --fps 30 --touchdown 41.2
  python eval/run_video.py --video a11_descent.mp4 --truth eval/truth/apollo11.csv --start 600 --roi 0,0,640,400
  python eval/run_video.py --selftest
Outputs <out>.csv (per frame), <out>.png (plot) and a metrics line.
"""
from __future__ import annotations

import argparse
import csv
import glob
import pathlib
import sys

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from so.vision.ttc import TTCEstimator  # noqa: E402


def frames_from(args):
    if args.video:
        cap = cv2.VideoCapture(args.video)
        fps = cap.get(cv2.CAP_PROP_FPS) or args.fps
        i = 0
        while True:
            ok, f = cap.read()
            if not ok:
                return
            yield i / fps, f
            i += 1
    else:
        files = sorted(glob.glob(str(pathlib.Path(args.frames) / "*")))
        for i, p in enumerate(files):
            f = cv2.imread(p)
            if f is not None:
                yield i / args.fps, f


def truth_fn(args):
    if args.touchdown is not None:
        return lambda t: args.touchdown - t
    rows = list(csv.DictReader(open(args.truth)))
    ts = np.array([float(r["t"]) for r in rows])
    if "rate" not in rows[0]:
        # altitude callouts only (columns t,alt_m): fit a cubic and take its slope as the descent rate
        p = np.polyfit(ts, np.array([float(r["alt_m"]) for r in rows]), 3)
        return lambda t: float(np.polyval(p, t) / -np.polyval(np.polyder(p), t)) if ts[0] <= t <= ts[-1] else None
    tau = np.array([float(r["alt"]) / float(r["rate"]) for r in rows])
    return lambda t: float(np.interp(t, ts, tau)) if ts[0] <= t <= ts[-1] else None


def evaluate(args):
    est = TTCEstimator(lookback_s=args.lookback)
    truth = truth_fn(args)
    roi = [int(v) for v in args.roi.split(",")] if args.roi else None
    rows = []
    for t, f in frames_from(args):
        if t < args.start:
            continue
        if args.end is not None and t > args.end:
            break
        if roi:
            x, y, w, h = roi
            f = f[y:y + h, x:x + w]
        r = est.update(t, f)
        tt = truth(t)
        rows.append((t, r.tau, tt, r.quality))
    out = pathlib.Path(args.out)
    with open(out.with_suffix(".csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["t", "tau_est", "tau_true", "quality"])
        w.writerows(rows)
    good = [(t, e, tr) for t, e, tr, q in rows if e is not None and tr is not None and tr > 0.5]
    if not good:
        print("no overlapping estimates; check --start/--end, texture and --roi")
        return None
    if args.calib_s:
        # A camera that is not pointing straight down reads a constant factor off. Fit that one
        # factor on the first seconds only, then score the rest, which the fit never saw.
        t_split = good[0][0] + args.calib_s
        fit = [tr / e for t, e, tr in good if t < t_split]
        gain = float(np.median(fit))
        raw = np.array([(e - tr) / tr for t, e, tr in good if t >= t_split])
        print(f"uncalibrated, held-out span: median |err| {np.median(np.abs(raw))*100:.1f}% | bias {np.mean(raw)*100:+.1f}%")
        print(f"gain {gain:.3f} fitted on the first {args.calib_s:g} s ({len(fit)} frames); scores below are on the rest")
        good = [(t, e * gain, tr) for t, e, tr in good if t >= t_split]
    err = np.array([(e - tr) / tr for _, e, tr in good])
    cover = len(good) / max(1, sum(1 for r in rows if r[2] is not None and r[2] > 0.5))
    print(f"{len(good)} frames | coverage {cover*100:.0f}% | median |err| {np.median(np.abs(err))*100:.1f}% | "
          f"p90 {np.percentile(np.abs(err), 90)*100:.1f}% | bias {np.mean(err)*100:+.1f}%")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 4.2))
        tt = [r[0] for r in rows if r[2] is not None]
        ax.plot(tt, [r[2] for r in rows if r[2] is not None], color="k", lw=1.5, label="true time to touchdown")
        ax.scatter([g[0] for g in good], [g[1] for g in good], s=6, color="#1f9bb5", label="camera τ")
        ax.set(xlabel="video time (s)", ylabel="seconds to touchdown",
               title=f"{args.label}: median error {np.median(np.abs(err))*100:.1f}% over {len(good)} frames")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(out.with_suffix(".png"), dpi=160)
        print("wrote", out.with_suffix(".png"))
    except ImportError:
        pass
    return float(np.median(np.abs(err)))


def selftest(tmp="eval_selftest"):
    """Render a synthetic constant-rate descent to video, then score it with this script."""
    from so.sources.sim import SimScene
    scene, v, fps, Z0, Zend = SimScene(), 30.0, 30, 450.0, 80.0
    path = f"{tmp}.mp4"
    wr = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (320, 240))
    n = int((Z0 - Zend) / v * fps)
    for i in range(n):
        wr.write(scene.render(Z0 - v * i / fps))
    wr.release()
    td = Z0 / v
    ns = argparse.Namespace(video=path, frames=None, fps=fps, touchdown=td, truth=None, start=0.0, end=None,
                            roi=None, lookback=0.5, calib_s=0.0, out=tmp, label="synthetic self-test")
    m = evaluate(ns)
    assert m is not None and m < 0.05, m
    print("selftest PASS")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--video")
    src.add_argument("--frames", help="folder of images in time order")
    ap.add_argument("--fps", type=float, default=30.0, help="frame rate for --frames (or if the video lacks one)")
    tr = ap.add_mutually_exclusive_group()
    tr.add_argument("--touchdown", type=float)
    tr.add_argument("--truth")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--roi", help="x,y,w,h crop: keep only ground (mask out vehicle parts / window frame)")
    ap.add_argument("--lookback", type=float, default=0.5)
    ap.add_argument("--calib-s", type=float, default=0.0,
                    help="fit one constant gain (tilted camera) on the first N seconds and score only the rest")
    ap.add_argument("--out", default="eval_result")
    ap.add_argument("--label", default="Real footage")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    elif not (a.video or a.frames) or not (a.touchdown is not None or a.truth):
        ap.error("need --video/--frames and --touchdown/--truth (or --selftest)")
    else:
        evaluate(a)
