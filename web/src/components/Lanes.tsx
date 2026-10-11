// The whole argument in one instrument. One altitude scale; the white line is where the lander
// really is. Three witnesses on the left, the two brains on the right. Anything that is not on
// the white line is wrong, and you can see by how much.
import { C, ERR_BAD_MM, mm, niceStep, signed, unit } from "../theme";
import type { State } from "../types";

const W = 660;
const H = 264;
const TOP = 50;
const BOTTOM = 30;
const X0 = 46; // left end of the plot area

type Lane = { x: number; name: string; color: string };
const WITNESS: Record<"nav" | "rf" | "cam", Lane> = {
  nav: { x: 96, name: "INERTIAL", color: C.nav },
  rf: { x: 196, name: "RANGEFINDER", color: C.rf },
  cam: { x: 290, name: "CAMERA", color: C.cam },
};
const LEGACY: Lane = { x: 432, name: "LEGACY GATE", color: C.legacy };
const OURS: Lane = { x: 552, name: "SECOND OPINION", color: C.so };

export default function Lanes({ s }: { s: State }) {
  const truth = s.truth;
  const most = Math.max(s.h0, truth ?? 0, s.legacy.est ?? 0, s.so.est ?? 0, s.rf ?? 0);
  const step = niceStep(most);
  const top = Math.max(100, Math.ceil(most / step) * step);
  const y = (v: number) => TOP + (1 - Math.min(Math.max(v, 0), top) / top) * (H - TOP - BOTTOM);
  const ticks = Array.from({ length: Math.floor(top / step) + 1 }, (_, i) => i * step);
  const move = (v: number) => ({ transform: `translateY(${y(v)}px)` });

  const belief = (lane: Lane, est: number | null, sigma?: number | null) => {
    if (est == null) return null;
    const err = truth == null ? null : est - truth;
    const bad = err != null && Math.abs(err) > ERR_BAD_MM;
    return (
      <>
        {/* the gap between belief and truth, drawn to scale */}
        {truth != null && Math.abs(y(est) - y(truth)) > 3 && (
          <line className="gap" x1={lane.x} x2={lane.x} y1={y(truth)} y2={y(est)} stroke={lane.color} />
        )}
        <g className="marker" style={move(est)}>
          {sigma != null && <rect x={lane.x - 20} width={40} y={-Math.max((sigma / top) * (H - TOP - BOTTOM), 2)}
            height={Math.max((sigma / top) * (H - TOP - BOTTOM), 2) * 2} fill={lane.color} opacity={0.22} />}
          <rect x={lane.x - 20} width={40} y={-2} height={4} fill={lane.color} />
          <text className="val" x={lane.x + 26} y={-9} fill={C.ink}>{mm(est)}</text>
          {err != null && <text className={`err ${bad ? "bad" : ""}`} x={lane.x + 26} y={20}>{signed(err)}</text>}
        </g>
      </>
    );
  };

  return (
    <svg className="lanes" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Altitude of every source against the true altitude">
      {ticks.map((v) => (
        <g key={v}>
          <line className="grid" x1={X0} x2={W} y1={y(v)} y2={y(v)} />
          <text className="tick" x={X0 - 8} y={y(v) + 4}>{mm(v)}</text>
        </g>
      ))}
      <text className="unit" x={X0 - 8} y={16}>{unit()}</text>
      <line className="divide" x1={376} x2={376} y1={10} y2={H - BOTTOM} />

      {(Object.keys(WITNESS) as (keyof typeof WITNESS)[]).map((k) => {
        const lane = WITNESS[k];
        const w = s.so.witness[k];
        const out = s.so.excluded.includes(k);
        const note = out ? (w ? "outvoted" : "silent") : !w ? (k === "cam" ? "no lock" : "silent") : "";
        return (
          <g key={k} className={`lane ${out || !w ? "off" : ""}`}>
            <text className="head" x={lane.x} y={16} fill={lane.color}>{lane.name}</text>
            <text className="note" x={lane.x} y={32}>{note}</text>
            {w && (
              <g className="marker" style={move(w.h)}>
                <circle cx={lane.x} r={7} fill={out ? "none" : lane.color} stroke={lane.color} strokeWidth={2} />
                <text className="val small" x={lane.x + 12} y={-9}>{mm(w.h)}</text>
              </g>
            )}
          </g>
        );
      })}

      <text className="head" x={LEGACY.x} y={16} fill={LEGACY.color}>{LEGACY.name}</text>
      <text className="head" x={OURS.x} y={16} fill={OURS.color}>{OURS.name}</text>
      <text className="note" x={LEGACY.x} y={32}>believes</text>
      <text className="note" x={OURS.x} y={32}>believes</text>

      {truth != null && (
        <g className="marker" style={move(truth)}>
          <line className="truth" x1={X0} x2={W} y1={0} y2={0} />
          <text className="truth-label" x={376} y={-9}>TRUE {mm(truth)}</text>
        </g>
      )}
      {belief(LEGACY, s.legacy.est)}
      {belief(OURS, s.so.est, s.so.sigma)}
    </svg>
  );
}
