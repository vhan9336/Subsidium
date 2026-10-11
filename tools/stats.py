"""The 'receipts' slide: how good is the camera altitude on the real rig?

  python tools/stats.py flight_log.jsonl

Uses only fault-free, steady-descent samples and compares camera altitude (tau x v)
with the raw rangefinder. Writes receipts.png if matplotlib is installed.
"""
import json
import sys

import numpy as np

rows = [json.loads(l) for l in open(sys.argv[1] if len(sys.argv) > 1 else "flight_log.jsonl")]
ok = [r for r in rows if r["cam"] and r["truth"] and not r["faults"] and r["descending"] and r["truth"] > 60]
if not ok:
    sys.exit("no steady fault-free descent samples yet")
truth = np.array([r["truth"] for r in ok])
vis = np.array([r["cam"] for r in ok])
err = (vis - truth) / truth
print(f"samples {len(ok)}  |  camera altitude error: median {np.median(np.abs(err))*100:.1f}%  "
      f"p90 {np.percentile(np.abs(err), 90)*100:.1f}%  bias {np.mean(err)*100:+.1f}%")
for lo, hi in ((60, 150), (150, 250), (250, 400), (400, 700)):
    m = (truth >= lo) & (truth < hi)
    if m.sum() > 10:
        print(f"  {lo:3d}-{hi:3d} mm: median |err| {np.median(np.abs(err[m]))*100:.1f}%  (n={m.sum()})")
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(truth, vis, s=4, alpha=0.4)
    lim = [0, max(truth.max(), vis.max()) * 1.05]
    ax.plot(lim, lim, "k--", lw=1)
    ax.set(xlabel="rangefinder altitude (mm)", ylabel="camera altitude, tau x v (mm)", xlim=lim, ylim=lim,
           title=f"Camera vs rangefinder, {len(ok)} samples, median error {np.median(np.abs(err))*100:.1f}%")
    fig.tight_layout()
    fig.savefig("receipts.png", dpi=160)
    print("wrote receipts.png")
except ImportError:
    pass
