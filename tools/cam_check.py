"""First real-hardware test — webcam only, no Arduino needed.

  python tools/cam_check.py [cam_index]

Hold the webcam pointing down ~50 cm above the lunar printout and lower it smoothly by
hand. tau (seconds to contact) should fall steadily toward 0. If it jumps around:
more texture, more light, lock autofocus, lower more smoothly. Q quits.
"""
import sys
import time

import cv2

sys.path.insert(0, ".")
from so.vision.ttc import TTCEstimator  # noqa: E402

cap = cv2.VideoCapture(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
est = TTCEstimator()
while True:
    ok, f = cap.read()
    if not ok:
        break
    r = est.update(time.monotonic(), f)
    txt = f"tau {r.tau:5.2f}s  scale {r.scale:.4f}  pts {r.n_inliers}  q {r.quality:.2f}" if r.tau else \
          f"no lock (pts {r.n_inliers}, q {r.quality:.2f}) - move closer / add texture"
    cv2.putText(f, txt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    if r.points is not None:
        k = f.shape[1] / est.width
        for p in r.points:
            cv2.circle(f, (int(p[0] * k), int(p[1] * k)), 2, (255, 200, 0), -1)
    cv2.imshow("cam_check", f)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
