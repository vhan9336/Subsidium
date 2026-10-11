// The math screen (press M): every number behind the verdict, live. It has the readings, the
// test each pair of sensors goes through, the rule that picks the odd one out, the legacy
// gate's rule beside it, and where each number on screen comes from. It's the answer to "prove it".
import { useEffect, useState, type MutableRefObject } from "react";
import { NAME, SENSORS, origin, type Sensor } from "../readings";
import { mm, signed, timeToContact, unit } from "../theme";
import type { State } from "../types";
import AltitudePlot from "./AltitudePlot";
import Lanes from "./Lanes";
import VoteTriangle from "./VoteTriangle";

type ScoreRow = { id: string; legacy_max: number; legacy_last: number; so_max: number; so_last: number; ok: boolean };
// the tuned settings from config.toml, as /proof sends them
type Config = {
  sensors: { rf_sigma_mm: number; rf_sigma_rel: number; cam_sigma_rel: number; nav_sigma_mm: number; nav_drift_mm_s: number };
  monitor: { window_s: number; chi2_gate: number; persist_s: number };
  legacy: { gate_mm: number; alpha: number; fail_after: number };
  camera: { lookback_s: number; min_quality: number };
};
type ProofData = { config: Config; scorecard: ScoreRow[] | null };

const PAIRS: [Sensor, Sensor][] = [["nav", "rf"], ["nav", "cam"], ["rf", "cam"]];

// What the vote does for each pattern of failing pairs. The row matching the engine's status lights up.
const RULES: { when: string; then: string; active: (status: string) => boolean }[] = [
  { when: "all three pairs agree", then: "all agree: fuse all three", active: (st) => st.startsWith("NOMINAL") },
  { when: "inertial fails with both others, rangefinder and camera agree", then: "inertial is wrong (the ground changed): re-anchor it", active: () => false },
  { when: "rangefinder fails with both others, inertial and camera agree", then: "rangefinder is wrong: exclude it", active: (st) => st.startsWith("RANGEFINDER EXCLUDED") },
  { when: "camera fails with both others, inertial and rangefinder agree", then: "camera is wrong: exclude it", active: (st) => st.startsWith("CAMERA EXCLUDED") },
  { when: "all three pairs fail", then: "cannot tell: assume the closest ground", active: (st) => st.startsWith("UNRESOLVED") },
  { when: "rangefinder gives no echo", then: "check inertial against the camera", active: (st) => st.startsWith("RANGEFINDER SILENT") },
];

/** Time until contact at the current speed, as text. */
const seconds = (altitude: number | null, speed: number) => {
  const t = timeToContact(altitude, speed);
  return t == null ? "—" : `${t.toFixed(1)} s`;
};

/** Loads the settings and the all-replays scorecard. The scorecard takes a few seconds, so keep asking until it arrives. */
function useProof() {
  const [data, setData] = useState<ProofData | null>(null);
  useEffect(() => {
    let alive = true;
    let timer = 0;
    const load = () => fetch("/proof").then((r) => r.json()).then((d: ProofData) => {
      if (!alive) return;
      setData(d);
      if (!d.scorecard) timer = window.setTimeout(load, 2000);
    }).catch(() => {});
    load();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, []);
  return data;
}

export default function Proof({ s, history, reanchored }: { s: State; history: MutableRefObject<State[]>; reanchored: boolean }) {
  const data = useProof();
  const cfg = data?.config;
  const witness = s.so.witness;
  const scale = s.clip?.mm_per_m;
  const errorOf = (est: number | null) => (s.truth == null || est == null ? null : est - s.truth);
  const camAltitude = s.tau != null ? s.tau * s.v : null;

  return (
    <main className="proof">
      <section className="live">
        <div><h4>Every source on one scale <span>off the white line = wrong</span></h4><Lanes s={s} /></div>
        <div><h4>The vote <span>how strongly each pair disagrees</span></h4><VoteTriangle so={s.so} reanchored={reanchored} /></div>
        <div><h4>Last 20 seconds <span>{unit()}</span></h4><AltitudePlot history={history} tick={s.t} /></div>
      </section>

      <section>
        <h4>1. What each sensor says <span>{unit()}</span></h4>
        <table>
          <thead><tr><th>Sensor</th><th>Reads</th><th>± 1σ</th><th>Where the reading comes from</th></tr></thead>
          <tbody>
            {SENSORS.map((k) => (
              <tr key={k} className={s.so.excluded.includes(k) ? "out" : ""}>
                <td className={k}>{NAME[k]}</td>
                <td>{witness[k] ? mm(witness[k]!.h) : "—"}</td>
                <td>{witness[k] ? mm(witness[k]!.sigma) : "—"}</td>
                <td>{origin(s, k)}</td>
              </tr>
            ))}
            <tr><td className="truth">True altitude</td><td>{mm(s.truth)}</td><td /><td>not given to either brain; used only to score them</td></tr>
          </tbody>
        </table>
        {cfg && (
          <p className="fine">
            Noise models (engine units, mm): rangefinder σ = {cfg.sensors.rf_sigma_mm} + {cfg.sensors.rf_sigma_rel * 100}% of range ·
            camera σ = {cfg.sensors.cam_sigma_rel * 100}% of altitude ÷ lock quality ·
            inertial σ = √({cfg.sensors.nav_sigma_mm}² + ({cfg.sensors.nav_drift_mm_s} × seconds since anchor)²).
            {scale ? ` On this footage 1 engine mm = ${1 / scale} m.` : ""}
          </p>
        )}

        <h4>2. Camera altitude</h4>
        <p className="eq">
          h<sub>cam</sub> = τ × v = {s.tau == null ? "—" : `${s.tau.toFixed(2)} s`} × {(s.v / (scale ?? 1)).toFixed(1)} {unit()}/s
          = <b>{mm(camAltitude)}</b> {unit()}
        </p>
        <p className="fine">
          τ is the time to contact, read from how fast the image grows between two frames {cfg?.camera.lookback_s ?? "—"} s apart:
          τ = Δt ÷ (scale − 1). It needs no map, no known object size and no laser.
          {s.clip?.camera === "reconstructed"
            ? " This footage has no descent camera in it, so here τ is reconstructed from the true altitude, not measured."
            : s.clip ? ` Measured on the footage; × ${s.clip.tau_gain} corrects for this camera not pointing straight down. Lock quality ${s.q_raw.toFixed(2)}.`
            : ` Lock quality ${s.q_raw.toFixed(2)}; below ${cfg?.camera.min_quality ?? "—"} the camera abstains.`}
        </p>
      </section>

      <section>
        <h4>3. Does each pair agree?</h4>
        <p className="eq">r² = (h<sub>a</sub> − h<sub>b</sub>)² ÷ (σ<sub>a</sub>² + σ<sub>b</sub>²)</p>
        <table>
          <thead><tr><th>Pair</th><th>Apart by</th><th>r², averaged</th><th>Limit</th><th /></tr></thead>
          <tbody>
            {PAIRS.map(([a, b]) => {
              const r2 = s.so.pairs[`${a}-${b}` as keyof typeof s.so.pairs];
              const gap = witness[a] && witness[b] ? Math.abs(witness[a]!.h - witness[b]!.h) : null;
              const verdict = r2 == null ? "" : r2 > s.so.gate ? "fail" : "pass";
              return (
                <tr key={a + b}>
                  <td>{NAME[a]} vs {NAME[b]}</td>
                  <td>{mm(gap)}</td>
                  <td>{r2 == null ? "no test" : r2.toFixed(2)}</td>
                  <td>{s.so.gate.toFixed(1)}</td>
                  <td className={verdict}>{verdict.toUpperCase()}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {cfg && (
          <p className="fine">
            Averaged over {cfg.monitor.window_s} s. A limit of {cfg.monitor.chi2_gate} is 3σ. A verdict must hold for {cfg.monitor.persist_s} s before it is acted on.
          </p>
        )}

        <h4>4. Who is the odd one out? <span>the sensor that is in both failing pairs</span></h4>
        <table className="rules">
          <tbody>
            {RULES.map((rule) => (
              <tr key={rule.when} className={rule.active(s.so.status) ? "now" : ""}><td>{rule.when}</td><td>{rule.then}</td></tr>
            ))}
          </tbody>
        </table>
        <p className="fine">Engine status right now: {s.so.status}</p>
      </section>

      <section>
        <h4>5. The legacy gate, on the same readings</h4>
        {cfg && (
          <p className="fine">
            Follow inertial. Accept the rangefinder only if it is within {cfg.legacy.gate_mm} mm of that, then move {cfg.legacy.alpha * 100}% toward it.
            After {cfg.legacy.fail_after} rejections in a row, declare the rangefinder failed and never listen to it again.
            It has no third opinion to check against.
          </p>
        )}
        <table>
          <thead><tr><th /><th>Believes</th><th>Off truth</th><th>Worst</th><th>Contact in</th><th>Status</th></tr></thead>
          <tbody>
            <tr><td className="legacy">Legacy gate</td><td>{mm(s.legacy.est)}</td><td>{signed(errorOf(s.legacy.est))}</td><td>{mm(s.score.legacy.max)}</td><td>{seconds(s.legacy.est, s.v)}</td><td>{s.legacy.status}</td></tr>
            <tr><td className="so">Subsidium</td><td>{mm(s.so.est)}</td><td>{signed(errorOf(s.so.est))}</td><td>{mm(s.score.so.max)}</td><td>{seconds(s.so.est, s.v)}</td><td>± {mm(s.so.sigma)}</td></tr>
            <tr><td className="truth">Actual</td><td>{mm(s.truth)}</td><td /><td /><td>{seconds(s.truth, s.v)}</td><td /></tr>
          </tbody>
        </table>

        <h4>6. Every replay, scored <span>simulator, engine mm · same as <code>python -m so check</code></span></h4>
        {data?.scorecard ? (
          <table>
            <thead><tr><th>Replay</th><th>Legacy worst / final</th><th>Subsidium worst / final</th><th /></tr></thead>
            <tbody>
              {data.scorecard.map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td>{r.legacy_max.toFixed(0)} / {r.legacy_last.toFixed(0)}</td>
                  <td>{r.so_max.toFixed(0)} / {r.so_last.toFixed(0)}</td>
                  <td className={r.ok ? "pass" : "fail"}>{r.ok ? "pass" : "FAIL"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="fine">Running all five replays through both brains…</p>}

        <h4>7. Where this replay's numbers come from</h4>
        <ul className="fine">
          {s.clip?.note && <li>{s.clip.note}</li>}
          {s.clip && <li>Footage: {s.clip.mission}. {s.clip.credit}.</li>}
          {s.scenario?.summary && <li>{s.scenario.summary}</li>}
          {s.faults.length > 0 && <li>Injected into the sensor stream: {s.faults.join(", ").replace(/_/g, " ")}.</li>}
          {!s.clip && <li>Simulated rig: every reading is generated, and the true altitude is known exactly.</li>}
        </ul>
      </section>
    </main>
  );
}
