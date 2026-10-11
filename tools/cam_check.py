"""First real-hardware test. Webcam only, no Arduino needed.

  python tools/cam_check.py [camera_index]

Point the webcam down at the lunar printout from about 50 cm and lower it smoothly by hand.
Time to contact (tau) should shrink steadily toward zero. If it jumps around, add texture or
light, lock the autofocus, and lower it more smoothly. Press Q to quit.
"""
import sys
import time

import cv2

sys.path.insert(0, ".")
from so.vision.ttc import TTCEstimator  # noqa: E402

cap = cv2.VideoCapture(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
est = TTCEstimator()
while cap.isOpened():
    ok, frame = cap.read()
    if not ok:
        break
    r = est.update(time.monotonic(), frame)
    text = (f"tau {r.tau:5.2f}s  scale {r.scale:.4f}  points {r.n_inliers}  quality {r.quality:.2f}" if r.tau
            else f"no lock (points {r.n_inliers}, quality {r.quality:.2f}): move closer or add texture")
    cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    if r.points is not None:
        k = frame.shape[1] / est.width
        for p in r.points:
            cv2.circle(frame, (int(p[0] * k), int(p[1] * k)), 2, (255, 200, 0), -1)
    cv2.imshow("cam_check", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
