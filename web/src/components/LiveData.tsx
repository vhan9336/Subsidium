// Everything the engine knows right now, in one small panel: each witness's reading and how it's
// doing, the camera's time to contact and lock quality, the pair tests, and the running scores.
// The big numbers beside it say what happened. This says why.
import { NAME, SENSORS, sensorState, type Sensor } from "../readings";
import { EVENT_LABEL, mm, unit } from "../theme";
import type { State } from "../types";

const PAIRS: [Sensor, Sensor][] = [["nav", "rf"], ["nav", "cam"], ["rf", "cam"]];

export default function LiveData({ s, events }: { s: State; events: { key: string; t: number }[] }) {
  const clip = s.clip;
  const perSecond = `${unit()}/s`;
  // real footage runs in the mission's metres, and the engine's speed is in rig mm
  const speed = s.v / (clip?.mm_per_m ?? 1);

  return (
    <section className="livedata" aria-label="Live data">
      <h4>
        Live data
        <span>
          {s.t.toFixed(1)} s{clip ? ` · clip ${clip.pos.toFixed(1)} of ${clip.dur.toFixed(1)} s` : ""}
        </span>
      </h4>

      <table>
        <tbody>
          {SENSORS.map((k) => {
            const w = s.so.witness[k];
            return (
              <tr key={k} className={`${k} ${sensorState(s, k) === "voting" ? "" : "off"}`}>
                <td>{NAME[k]}</td>
                <td>{w ? mm(w.h) : "—"}</td>
                <td>± {w ? mm(w.sigma) : "—"}</td>
                <td>{sensorState(s, k)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <p className="line">
        {speed.toFixed(1)} {perSecond} · camera contact in {s.tau_raw == null ? "—" : `${s.tau_raw.toFixed(1)} s`} · lock {s.q_raw.toFixed(2)}
      </p>

      <div className="pairs">
        {PAIRS.map(([a, b]) => {
          const r2 = s.so.pairs[`${a}-${b}` as keyof typeof s.so.pairs];
          const state = r2 == null ? "none" : r2 > s.so.gate ? "fail" : "pass";
          return (
            <span key={a + b} className={state} title={`How strongly ${NAME[a]} and ${NAME[b]} disagree. Above ${s.so.gate} they fail.`}>
              {NAME[a].slice(0, 3)} vs {NAME[b].slice(0, 3)} <b>{r2 == null ? "—" : r2.toFixed(1)}</b>
            </span>
          );
        })}
      </div>

      <p className="line">
        Worst error so far: <b className="legacy">legacy {mm(s.score.legacy.max)} {unit()}</b> · <b className="so">Subsidium {mm(s.score.so.max)} {unit()}</b>
      </p>

      {/* the engine's own announcements, newest first */}
      <ol className="events">
        {events.filter((e) => e.t <= s.t).slice(-4).reverse().map((e) => (
          <li key={e.key + e.t}><time>{e.t.toFixed(1)} s</time> {EVENT_LABEL[e.key]}</li>
        ))}
      </ol>
    </section>
  );
}
