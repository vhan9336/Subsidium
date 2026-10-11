// The vote, readable on its own: three witnesses, three pair tests, who got outvoted.
import { mm, unit } from "../theme";
import type { SecondOpinion } from "../types";

type Key = "nav" | "rf" | "cam";
type Pair = keyof SecondOpinion["pairs"];

const R = 43;
const NODES: Record<Key, { x: number; y: number; name: string }> = {
  nav: { x: 190, y: 66, name: "NAV" },
  rf: { x: 66, y: 256, name: "RF" },
  cam: { x: 314, y: 256, name: "CAM" },
};
// label offset pushes each pair's value outward from the triangle's centre
const EDGES: { pair: Pair; a: Key; b: Key; dx: number; dy: number }[] = [
  { pair: "nav-rf", a: "nav", b: "rf", dx: -40, dy: -8 },
  { pair: "nav-cam", a: "nav", b: "cam", dx: 40, dy: -8 },
  { pair: "rf-cam", a: "rf", b: "cam", dx: 0, dy: 24 },
];

function verdict(so: SecondOpinion): [string, string] {
  if (so.status.startsWith("UNRESOLVED")) return ["NO ISOLATION", "warn"];
  if (so.status.startsWith("RANGEFINDER SILENT")) return ["RF SILENT", "warn"];
  if (so.excluded.includes("rf")) return ["RF OUTVOTED", "good"];
  if (so.excluded.includes("cam")) return ["CAM OUTVOTED", "good"];
  if (so.cam_abstain) return ["2 WITNESSES", "warn"];
  return ["3 AGREE", "good"];
}

export default function VoteTriangle({ so, reanchored }: { so: SecondOpinion; reanchored: boolean }) {
  const [word, tone] = verdict(so);
  return (
    <svg className="triangle" viewBox="0 0 380 330" role="img" aria-label={`Vote: ${word}`}>
      {EDGES.map(({ pair, a, b, dx, dy }) => {
        const A = NODES[a];
        const B = NODES[b];
        const v = so.pairs[pair];
        const state = v == null ? "none" : v > so.gate ? "fail" : "ok";
        const len = Math.hypot(B.x - A.x, B.y - A.y);
        const ux = (B.x - A.x) / len;
        const uy = (B.y - A.y) / len;
        const mx = (A.x + B.x) / 2 + dx;
        const my = (A.y + B.y) / 2 + dy;
        return (
          <g key={pair} className={`edge ${state}`}>
            <line x1={A.x + ux * R} y1={A.y + uy * R} x2={B.x - ux * R} y2={B.y - uy * R} />
            <rect x={mx - 34} y={my - 13} width={68} height={26} rx={5} />
            <text x={mx} y={my + 5}>{v == null ? "no test" : v.toFixed(1)}</text>
          </g>
        );
      })}

      <text className={`tri-verdict ${tone}`} x={190} y={196}>{word}</text>
      <text className="tri-gate" x={190} y={216}>pair fails above {so.gate.toFixed(1)}</text>

      {(Object.keys(NODES) as Key[]).map((k) => {
        const n = NODES[k];
        const w = so.witness[k];
        const out = so.excluded.includes(k);
        const abstain = k === "cam" && so.cam_abstain;
        const below = k === "nav" ? -R - 12 : R + 20;
        const note = out
          ? w ? "EXCLUDED" : "SILENT"
          : abstain ? "ABSTAINING"
          : k === "nav" && reanchored ? "RE-ANCHORED"
          : w ? `±${mm(w.sigma)} ${unit()}` : "";
        return (
          <g key={k} className={`node ${k} ${out ? "out" : ""} ${abstain ? "abstain" : ""} ${k === "nav" && reanchored ? "flash" : ""}`}>
            <circle cx={n.x} cy={n.y} r={R} />
            <text className="node-name" x={n.x} y={n.y - 13}>{n.name}</text>
            <text className="node-alt" x={n.x} y={n.y + 15}>{mm(w?.h)}</text>
            <text className="node-note" x={n.x} y={n.y + below}>{note}</text>
            {out && (
              <g className="cross">
                <line x1={n.x - R * 0.7} y1={n.y - R * 0.7} x2={n.x + R * 0.7} y2={n.y + R * 0.7} />
                <line x1={n.x + R * 0.7} y1={n.y - R * 0.7} x2={n.x - R * 0.7} y2={n.y + R * 0.7} />
              </g>
            )}
          </g>
        );
      })}
    </svg>
  );
}
