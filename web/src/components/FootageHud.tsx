// The software layer drawn over the camera image: what the picture is, what the camera estimator
// is doing with it, the vote, and an altitude tape. The tape uses the same colours as everything
// else: white line = true altitude, red = legacy gate, green = Subsidium, dots = witnesses.
import { mm, niceStep, unit } from "../theme";
import type { State } from "../types";

type Tone = "good" | "warn" | "bad" | "idle";
const WITNESS = ["nav", "rf", "cam"] as const;

export default function FootageHud({ s, verdict, tone }: { s: State; verdict: string; tone: Tone }) {
  const clip = s.clip;
  const most = Math.max(s.h0, s.truth ?? 0, s.legacy.est ?? 0, s.so.est ?? 0, s.rf ?? 0);
  const step = niceStep(most);
  const top = Math.max(100, Math.ceil(most / step) * step);
  const rebuilt = clip?.camera === "reconstructed"; // a mission broadcast, not a descent camera
  const at = (v: number) => ({ transform: `translateY(${(1 - Math.min(Math.max(v, 0), top) / top) * 100}cqh)` });
  const ticks = Array.from({ length: Math.floor(top / step) + 1 }, (_, i) => i * step);
  const tau = s.tau ?? s.tau_raw;
  const out = s.so.excluded.includes("cam");
  const locked = s.cam != null && !out;

  return (
    <div className={`hud ${rebuilt ? "broadcast" : ""}`}>
      {clip && <i className="hud-progress" style={{ transform: `scaleX(${Math.min(clip.pos / clip.dur, 1)})` }} />}
      <div className="hud-source">
        <b>{rebuilt ? "The real broadcast" : clip ? "Real footage" : "Simulated camera"}</b>
        {rebuilt ? <span>{clip.name} · {clip.credit}</span>
          : clip ? <span>{clip.name} landing on the Moon · {clip.credit}</span> : <span>the rig's downward camera, rendered</span>}
        {!rebuilt && (
          <p className={locked ? "lock" : ""}>
            {locked ? "Camera locked on the surface" : out ? "Camera outvoted" : "Camera has no lock yet"}
            {tau != null && <> · contact in {tau.toFixed(1)} s</>}
          </p>
        )}
      </div>
      <p className={`hud-verdict ${tone}`}>{verdict}</p>

      <div className="tape" aria-hidden="true">
        {ticks.map((v) => <span key={v} className="tape-tick" style={at(v)}>{mm(v)}</span>)}
        {s.truth != null && <i className="tape-truth" style={at(s.truth)} />}
        {WITNESS.map((k) => {
          const w = s.so.witness[k];
          return w && <i key={k} className={`tape-dot ${k} ${s.so.excluded.includes(k) ? "out" : ""}`} style={at(w.h)} />;
        })}
        {s.legacy.est != null && <i className="tape-caret legacy" style={at(s.legacy.est)}><b>Legacy</b></i>}
        {s.so.est != null && <i className="tape-caret so" style={at(s.so.est)}><b>Subsidium</b></i>}
        <small>{unit()}</small>
      </div>
    </div>
  );
}
