// Last 20 s of every altitude source and both beliefs. Plain canvas, no chart library.
import { useEffect, useRef, type MutableRefObject } from "react";
import { HISTORY_S } from "../telemetry";
import { C, DISPLAY, EVENT_LABEL, mm, niceStep } from "../theme";
import type { State } from "../types";

type Series = {
  label: string;
  color: string;
  width: number;
  dash: number[];
  get: (s: State) => number | null;
};

// drawn in this order, so the two beliefs sit on top
const SERIES: Series[] = [
  { label: "NAV", color: C.nav, width: 1.5, dash: [6, 4], get: (s) => s.nav },
  { label: "RF", color: C.rf, width: 1.5, dash: [], get: (s) => s.rf },
  { label: "CAM", color: C.cam, width: 1.5, dash: [], get: (s) => s.cam },
  { label: "TRUE", color: C.truth, width: 1.5, dash: [2, 4], get: (s) => s.truth },
  { label: "LEGACY", color: C.legacy, width: 3, dash: [], get: (s) => s.legacy.est },
  { label: "2ND OP", color: C.so, width: 3, dash: [], get: (s) => s.so.est },
];

const PAD = { l: 46, r: 70, t: 18, b: 24 };

function draw(cv: HTMLCanvasElement, h: State[], range: { lo: number; hi: number } | null) {
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth;
  const H = cv.clientHeight;
  if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) {
    cv.width = Math.round(W * dpr);
    cv.height = Math.round(H * dpr);
  }
  const g = cv.getContext("2d")!;
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, W, H);
  if (!h.length || W < 120 || H < 80) return range;

  // y range: fit the data with some headroom, eased so the axis doesn't twitch
  let lo = Infinity;
  let hi = -Infinity;
  for (const s of h)
    for (const sr of SERIES) {
      const v = sr.get(s);
      if (v != null) {
        lo = Math.min(lo, v);
        hi = Math.max(hi, v);
      }
    }
  const half = Math.max(hi - lo, 120) * 0.62;
  const mid = (lo + hi) / 2;
  const want = { lo: mid - half, hi: mid + half };
  range = range ? { lo: range.lo + (want.lo - range.lo) * 0.15, hi: range.hi + (want.hi - range.hi) * 0.15 } : want;

  const now = h[h.length - 1].t;
  const x = (t: number) => PAD.l + ((t - (now - HISTORY_S)) / HISTORY_S) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - (v - range!.lo) / (range!.hi - range!.lo)) * (H - PAD.t - PAD.b);

  // grid
  g.font = `13px ${DISPLAY}`;
  g.textBaseline = "middle";
  const step = niceStep(range.hi - range.lo);
  for (let v = Math.ceil(range.lo / step) * step; v <= range.hi; v += step) {
    g.strokeStyle = C.line;
    g.lineWidth = 1;
    g.beginPath();
    g.moveTo(PAD.l, y(v));
    g.lineTo(W - PAD.r, y(v));
    g.stroke();
    g.fillStyle = C.dim;
    g.textAlign = "right";
    g.fillText(mm(v), PAD.l - 8, y(v));
  }
  g.textAlign = "center";
  g.fillStyle = C.dim;
  for (let d = 0; d <= HISTORY_S; d += 5) g.fillText(d ? `−${d}s` : "now", x(now - d), H - 9);

  g.save();
  g.beginPath();
  g.rect(PAD.l, PAD.t - 6, W - PAD.l - PAD.r, H - PAD.t - PAD.b + 12);
  g.clip();

  // events
  g.textAlign = "left";
  const rows: number[] = [];
  for (const s of h)
    for (const e of s.events) {
      if (!EVENT_LABEL[e] || e === "cam_lock") continue;
      g.strokeStyle = "rgba(232,236,241,0.28)";
      g.lineWidth = 1;
      g.setLineDash([3, 3]);
      g.beginPath();
      g.moveTo(x(s.t), PAD.t);
      g.lineTo(x(s.t), H - PAD.b);
      g.stroke();
      g.setLineDash([]);
      g.fillStyle = C.ink;
      g.font = `600 11px ${DISPLAY}`;
      // flip to the left of the marker when there's no room before the plot's right edge
      const wide = g.measureText(EVENT_LABEL[e]).width;
      const flip = x(s.t) + wide + 10 > W - PAD.r;
      const left = x(s.t) + (flip ? -5 - wide : 5);
      let row = 0; // drop to the next line rather than print over an earlier label
      while (rows[row] != null && rows[row] > left - 8) row++;
      rows[row] = left + wide;
      g.fillText(EVENT_LABEL[e], left, e.startsWith("legacy") ? H - PAD.b - 10 : PAD.t + 4 + row * 14);
    }

  // Second Opinion ±σ band
  g.fillStyle = "rgba(91,227,138,0.18)";
  let open = false;
  const closeBand = (from: number, to: number) => {
    for (let i = to; i >= from; i--) g.lineTo(x(h[i].t), y(h[i].so.est! - h[i].so.sigma!));
    g.closePath();
    g.fill();
  };
  let start = 0;
  h.forEach((s, i) => {
    const ok = s.so.est != null && s.so.sigma != null;
    if (ok && !open) {
      g.beginPath();
      g.moveTo(x(s.t), y(s.so.est! + s.so.sigma!));
      open = true;
      start = i;
    } else if (ok) g.lineTo(x(s.t), y(s.so.est! + s.so.sigma!));
    if (open && (!ok || i === h.length - 1)) {
      closeBand(start, ok ? i : i - 1);
      open = false;
    }
  });

  // lines (a null reading breaks the line)
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
      else if (pen) g.lineTo(x(s.t), y(v));
      else {
        g.moveTo(x(s.t), y(v));
        pen = true;
      }
    }
    g.stroke();
  }
  g.setLineDash([]);
  g.restore();

  // labels at the live end, nudged apart so they stay readable when the lines agree
  const last = h[h.length - 1];
  const tags = SERIES.map((sr) => ({ sr, v: sr.get(last) }))
    .filter((t): t is { sr: Series; v: number } => t.v != null)
    .map((t) => ({ ...t, py: Math.min(Math.max(y(t.v), PAD.t), H - PAD.b) }))
    .sort((a, b) => a.py - b.py);
  for (let i = 1; i < tags.length; i++) tags[i].py = Math.max(tags[i].py, tags[i - 1].py + 14);
  const over = tags.length ? tags[tags.length - 1].py - (H - PAD.b + 4) : 0;
  if (over > 0) for (let i = tags.length - 1; i >= 0; i--) tags[i].py = Math.min(tags[i].py, H - PAD.b + 4 - (tags.length - 1 - i) * 14);
  g.font = `600 13px ${DISPLAY}`;
  g.textAlign = "left";
  for (const t of tags) {
    g.fillStyle = t.sr.color;
    g.fillText(t.sr.label, W - PAD.r + 8, t.py);
  }
  return range;
}

export default function AltitudePlot({ history, tick }: { history: MutableRefObject<State[]>; tick: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const range = useRef<{ lo: number; hi: number } | null>(null);

  useEffect(() => {
    if (ref.current) range.current = draw(ref.current, history.current, range.current);
  }, [history, tick]);

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const ro = new ResizeObserver(() => (range.current = draw(cv, history.current, range.current)));
    ro.observe(cv);
    return () => ro.disconnect();
  }, [history]);

  return (
    <div className="plot">
      <canvas ref={ref} aria-label="Altitude over the last 20 seconds" />
    </div>
  );
}
