// The last 20 seconds of every altitude source and both beliefs, on a plain canvas.
import { useEffect, useRef, type MutableRefObject } from "react";
import { HISTORY_S } from "../telemetry";
import { C, DISPLAY, EVENT_LABEL, mm, niceStep } from "../theme";
import type { State } from "../types";

type Series = { label: string; color: string; width: number; dash: number[]; get: (s: State) => number | null };

// Drawn in this order, so the two beliefs end up on top.
const SERIES: Series[] = [
  { label: "NAV", color: C.nav, width: 1.5, dash: [6, 4], get: (s) => s.nav },
  { label: "RF", color: C.rf, width: 1.5, dash: [], get: (s) => s.rf },
  { label: "CAM", color: C.cam, width: 1.5, dash: [], get: (s) => s.cam },
  { label: "TRUE", color: C.truth, width: 1.5, dash: [2, 4], get: (s) => s.truth },
  { label: "LEGACY", color: C.legacy, width: 3, dash: [], get: (s) => s.legacy.est },
  { label: "SUBSIDIUM", color: C.so, width: 3, dash: [], get: (s) => s.so.est },
];
const PAD = { l: 46, r: 92, t: 18, b: 24 };
type Range = { lo: number; hi: number };

/** Draws the plot and returns the y range it used, so the next frame can ease toward a new one. */
function draw(cv: HTMLCanvasElement, h: State[], prev: Range | null): Range | null {
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth;
  const H = cv.clientHeight;
  cv.width = Math.round(W * dpr);
  cv.height = Math.round(H * dpr);
  const g = cv.getContext("2d")!;
  g.scale(dpr, dpr);
  if (!h.length || W < 120 || H < 80) return prev;

  // Fit the y axis to the data with some headroom, easing so the axis doesn't twitch.
  const all = h.flatMap((s) => SERIES.map((sr) => sr.get(s)).filter((v): v is number => v != null));
  const mid = (Math.min(...all) + Math.max(...all)) / 2;
  const half = Math.max(Math.max(...all) - Math.min(...all), 120) * 0.62;
  const range = prev
    ? { lo: prev.lo + (mid - half - prev.lo) * 0.15, hi: prev.hi + (mid + half - prev.hi) * 0.15 }
    : { lo: mid - half, hi: mid + half };

  const now = h[h.length - 1].t;
  const x = (t: number) => PAD.l + ((t - (now - HISTORY_S)) / HISTORY_S) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - (v - range.lo) / (range.hi - range.lo)) * (H - PAD.t - PAD.b);
  const line = (x1: number, y1: number, x2: number, y2: number) => {
    g.beginPath();
    g.moveTo(x1, y1);
    g.lineTo(x2, y2);
    g.stroke();
  };

  // gridlines and axis labels
  g.font = `13px ${DISPLAY}`;
  g.textBaseline = "middle";
  g.lineWidth = 1;
  const step = niceStep(range.hi - range.lo);
  for (let v = Math.ceil(range.lo / step) * step; v <= range.hi; v += step) {
    g.strokeStyle = C.line;
    line(PAD.l, y(v), W - PAD.r, y(v));
    g.fillStyle = C.dim;
    g.textAlign = "right";
    g.fillText(mm(v), PAD.l - 8, y(v));
  }
  g.textAlign = "center";
  for (let d = 0; d <= HISTORY_S; d += 5) g.fillText(d ? `−${d}s` : "now", x(now - d), H - 9);

  g.save();
  g.beginPath();
  g.rect(PAD.l, PAD.t - 6, W - PAD.l - PAD.r, H - PAD.t - PAD.b + 12);
  g.clip();

  // event markers: a dashed line and a label
  g.textAlign = "left";
  g.font = `600 11px ${DISPLAY}`;
  for (const s of h)
    for (const e of s.events) {
      if (!EVENT_LABEL[e] || e === "cam_lock") continue;
      g.strokeStyle = "rgba(232,236,241,0.28)";
      g.setLineDash([3, 3]);
      line(x(s.t), PAD.t, x(s.t), H - PAD.b);
      g.setLineDash([]);
      g.fillStyle = C.ink;
      const wide = g.measureText(EVENT_LABEL[e]).width;
      const flip = x(s.t) + wide + 10 > W - PAD.r; // no room on the right, so put the label on the left
      g.fillText(EVENT_LABEL[e], x(s.t) + (flip ? -5 - wide : 5), e.startsWith("legacy") ? H - PAD.b - 10 : PAD.t + 4);
    }

  // Subsidium's ±sigma band: the top edge forwards, then the bottom edge back
  const known = h.filter((s) => s.so.est != null && s.so.sigma != null);
  if (known.length > 1) {
    g.fillStyle = "rgba(91,227,138,0.18)";
    g.beginPath();
    known.forEach((s) => g.lineTo(x(s.t), y(s.so.est! + s.so.sigma!)));
    [...known].reverse().forEach((s) => g.lineTo(x(s.t), y(s.so.est! - s.so.sigma!)));
    g.fill();
  }

  // the lines. A missing reading breaks the line instead of joining across the gap.
  g.lineJoin = "round";
  for (const sr of SERIES) {
    g.strokeStyle = sr.color;
    g.lineWidth = sr.width;
    g.setLineDash(sr.dash);
    g.beginPath();
    let pen = false;
    for (const s of h) {
      const v = sr.get(s);
      if (v == null) pen = false;
      else {
        pen ? g.lineTo(x(s.t), y(v)) : g.moveTo(x(s.t), y(v));
        pen = true;
      }
    }
    g.stroke();
  }
  g.restore();

  // labels at the live end, pushed apart so they stay readable when the lines agree
  g.font = `600 13px ${DISPLAY}`;
  let floor = -Infinity;
  SERIES.map((sr) => ({ sr, v: sr.get(h[h.length - 1]) }))
    .filter((t): t is { sr: Series; v: number } => t.v != null)
    .sort((a, b) => y(a.v) - y(b.v))
    .forEach(({ sr, v }) => {
      floor = Math.max(Math.min(Math.max(y(v), PAD.t), H - PAD.b), floor + 14);
      g.fillStyle = sr.color;
      g.fillText(sr.label, W - PAD.r + 8, floor);
    });
  return range;
}

export default function AltitudePlot({ history, tick }: { history: MutableRefObject<State[]>; tick: number }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const range = useRef<Range | null>(null);
  const redraw = () => {
    if (canvas.current) range.current = draw(canvas.current, history.current, range.current);
  };

  useEffect(redraw, [history, tick]);
  useEffect(() => {
    const ro = new ResizeObserver(redraw);
    ro.observe(canvas.current!);
    return () => ro.disconnect();
  }, [history]);

  return (
    <div className="plot">
      <canvas ref={canvas} aria-label="Altitude over the last 20 seconds" />
    </div>
  );
}
