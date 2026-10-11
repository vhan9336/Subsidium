"""Synthetic descent: does vision-derived altitude (tau * v) match the true altitude?
Run:  python -m pytest tests  (or python -m tests.test_ttc for a printout)
"""
import numpy as np

from so.sources.sim import SimScene
from so.vision.ttc import TTCEstimator


def test_camera_altitude_accuracy():
    e, _, _ = run()
    assert np.median(np.abs(e)) < 0.03


def run(v=30.0, fps=30, Z0=450.0, Zend=90.0, boulders=((0.25, -0.15, 22.0, 30.0),)):
    scene = SimScene(boulders=boulders)
    est = TTCEstimator()
    errs, last = [], None
    t, Z = 0.0, Z0
    while Z > Zend:
        r = est.update(t, scene.render(Z))
        if r.tau is not None:
            h_vis = r.tau * v
            errs.append((Z, h_vis, (h_vis - Z) / Z))
            last = r
        t += 1 / fps
        Z -= v / fps
    e = np.array([x[2] for x in errs])
    return e, last, errs


if __name__ == "__main__":
    e, last, errs = run()
    print(f"samples={len(e)}  median |err|={np.median(np.abs(e))*100:.1f}%  p90={np.percentile(np.abs(e),90)*100:.1f}%  bias={np.mean(e)*100:+.1f}%")
    for Z, h, er in errs[:: max(1, len(errs) // 8)]:
        print(f"  true {Z:6.1f} mm   vision {h:6.1f} mm   err {er*100:+5.1f}%")
    np.set_printoptions(precision=2, suppress=True)
    print("hazard grid (height above ground, fraction of altitude):\n", last.hazard)
    print("chosen site:", last.site)
    assert np.median(np.abs(e)) < 0.06, "vision altitude too noisy"
    print("PASS")
