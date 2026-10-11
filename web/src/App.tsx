import { useEffect, useRef, useState } from "react";
import AltitudePlot from "./components/AltitudePlot";
import BrainCard from "./components/BrainCard";
import CameraFeed from "./components/CameraFeed";
import FootageHud from "./components/FootageHud";
import Lanes from "./components/Lanes";
import ScenarioPanel from "./components/ScenarioPanel";
import Scene3D from "./components/Scene3D";
import VoteTriangle from "./components/VoteTriangle";
import { cmd, useTelemetry } from "./telemetry";
import { ERR_BAD_MM, EVENT_LABEL, mm, signed } from "./theme";
import type { ClipInfo, ScenarioInfo, State } from "./types";
import { voice } from "./voice";

type Logged = { key: string; t: number };
type View = "tv" | "cam" | "3d";
type Tone = "good" | "warn" | "bad" | "idle";
const VIEW_NAME: Record<View, string> = { tv: "Mission broadcast", cam: "Lander camera", "3d": "3D view" };
const SOURCE = { sim: "Simulator", live: "Live rig", replay: "Recorded run", video: "Real footage" };

const KEYS: Record<string, string> = {
  d: "descend", s: "stop", u: "up", r: "reset", t: "terrain_up", y: "terrain_down", "0": "fault:clear",
};

/** What is going on right now, in one sentence, read from the live state (not from old events). */
function headline(s: State, log: Logged[]): [string, Tone] {
  const so = s.so;
  if (so.status.startsWith("UNRESOLVED")) return ["The sensors disagree and none can be singled out. Assuming the closest ground.", "warn"];
  if (so.status.startsWith("RANGEFINDER SILENT")) return ["The rangefinder is silent. Inertial is being checked against the camera.", "warn"];
  if (so.excluded.includes("rf")) return ["The rangefinder was outvoted two to one. Second Opinion is ignoring it.", "good"];
  if (so.excluded.includes("cam")) return ["The camera was outvoted two to one. Second Opinion is ignoring it.", "good"];
  if (log.some((e) => e.key === "terrain_change")) return ["The ground really did change. Camera and rangefinder outvoted inertial.", "good"];
  if (s.legacy.status !== "NOMINAL") return ["The legacy gate is rejecting its rangefinder.", "bad"];
  if (so.cam_abstain) return [s.v > 1 ? "The camera has no lock. Inertial and rangefinder agree." : "Standing by. The camera locks on once the descent starts.", "idle"];
  return ["All three witnesses agree.", "good"];
}

/** The same thing in a few words, for the layer over the footage. */
function verdict(s: State, log: Logged[]): string {
  const so = s.so;
  if (so.status.startsWith("UNRESOLVED")) return "No majority";
  if (so.status.startsWith("RANGEFINDER SILENT")) return "Rangefinder silent";
  if (so.excluded.includes("rf")) return "Rangefinder outvoted 2 to 1";
  if (so.excluded.includes("cam")) return "Camera outvoted 2 to 1";
  if (log.some((e) => e.key === "terrain_change")) return "Inertial outvoted 2 to 1";
  if (s.legacy.status !== "NOMINAL") return "Legacy rejecting rangefinder";
  return so.cam_abstain ? "2 witnesses agree" : "3 of 3 agree";
}

function consequence(legacyErr: number | null, soErr: number | null): string {
  const off = (e: number) => `${Math.abs(Math.round(e))} mm too ${e < 0 ? "low" : "high"}`;
  if (legacyErr == null || soErr == null) return "";
  const l = Math.abs(legacyErr) > ERR_BAD_MM;
  const o = Math.abs(soErr) > ERR_BAD_MM;
  if (l && !o) return `The legacy gate believes it is ${off(legacyErr)}. Second Opinion is on the true altitude.`;
  if (l && o) return `The legacy gate is ${off(legacyErr)}; Second Opinion is ${off(soErr)}.`;
  if (o) return `Second Opinion is ${off(soErr)}; the legacy gate is on the true altitude.`;
  return "Both brains are on the true altitude.";
}

export default function App() {
  const [log, setLog] = useState<Logged[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [clips, setClips] = useState<ClipInfo[]>([]);
  const [voiceOn, setVoiceOn] = useState(false);
  const [picked, setPicked] = useState<View | null>(null);
  const { state: s, connected, history } = useTelemetry((key: string, st: State) => {
    voice.say(key);
    if (EVENT_LABEL[key]) setLog((l) => [...l.filter((e) => e.t <= st.t).slice(-8), { key, t: st.t }]);
  });

  useEffect(() => {
    fetch("/scenarios").then((r) => r.json()).then(setScenarios).catch(() => {});
    fetch("/clips").then((r) => r.json()).then(setClips).catch(() => {});
  }, [connected]);

  const clip = s?.clip ?? null;
  const voting = !clip || clip.truth; // a clip without an altitude record is tracking-only
  const sc = s?.scenario ?? null;
  const broadcast = sc?.broadcast ?? null;

  // One view is large, the rest are thumbnails beside it. Real footage leads with the camera and
  // the software layer on it; the simulator leads with the 3D view. A mission's broadcast, when
  // there is one, is only ever a thumbnail unless picked.
  const views: View[] = !voting ? ["cam"]
    : [...(s?.kind === "video" ? ["cam", "3d"] : ["3d", "cam"]), ...(broadcast ? ["tv"] : [])] as View[];
  const main: View = picked && views.includes(picked) ? picked : views[0];
  const place = (v: View) => (v === main ? "is-main" : "is-thumb");
  const cycle = useRef(() => {});
  cycle.current = () => setPicked(views[(views.indexOf(main) + 1) % views.length]);
  const toggleVoice = () => setVoiceOn(voice.toggle());

  // a new replay starts with a clean history, and its broadcast from the chosen moment
  const tv = useRef<HTMLVideoElement>(null);
  const tvAt = sc?.broadcast_at ?? 0;
  useEffect(() => {
    setLog([]);
    if (tv.current) {
      tv.current.currentTime = tvAt;
      tv.current.play().catch(() => {});
    }
  }, [sc?.id, broadcast, tvAt]);

  useEffect(() => setPicked(null), [s?.kind]); // footage and simulator each lead with their own view

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
      const k = e.key.toLowerCase();
      if (k === "v") setVoiceOn(voice.toggle());
      else if (k === "c") cycle.current();
      else if (KEYS[k]) {
        if (k === "r") setLog([]);
        cmd(KEYS[k]);
      } else {
        const n = Number(k);
        if (n >= 1 && n <= scenarios.length) cmd(`scenario:${scenarios[n - 1].id}`);
      }
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [scenarios]);

  const legacyErr = s?.truth != null && s.legacy.est != null ? s.legacy.est - s.truth : null;
  const soErr = s?.truth != null && s.so.est != null ? s.so.est - s.truth : null;
  const reanchored = !!s && log.some((e) => e.key === "terrain_change" && s.t - e.t < 4);
  // inertial height minus true altitude: how far the ground under the lander has moved since reset
  const terrain = s?.truth != null ? s.nav_raw - s.truth : 0;
  const [line, tone] = s && voting ? headline(s, log) : ["", "idle" as Tone];
  const tau = s ? s.tau ?? s.tau_raw : null;

  return (
    <div className="app">
      <header className="bar">
        <h1>Second Opinion</h1>
        <p>Three sensors report altitude. The odd one out is outvoted.</p>
        <div className="bar-right">
          {s?.faults.map((f) => <span key={f} className="fault">Injected fault: {f.replace("_", " ")}</span>)}
          <span className={`source ${connected ? "" : "down"}`}>{connected ? SOURCE[s?.kind ?? "sim"] : "Engine offline"}</span>
        </div>
      </header>

      {s ? (
        <main>
          <section className="left">
            <div className={`stage main-${main} ${views.length === 1 ? "solo" : ""}`}>
              {/* every view stays mounted; C or a click on a thumbnail changes which one is large */}
              {broadcast && (
                <figure className={`view ${place("tv")}`} onClick={() => setPicked("tv")}>
                  <video ref={tv} src={`/broadcasts/${broadcast.split("/").pop()}`} muted autoPlay loop playsInline />
                  <figcaption>{VIEW_NAME.tv}</figcaption>
                </figure>
              )}
              <figure className={`view ${place("cam")}`} onClick={() => setPicked("cam")}>
                <CameraFeed alt="Downward camera" />
                {voting && <FootageHud s={s} verdict={verdict(s, log)} tone={tone} />}
                <figcaption>{VIEW_NAME.cam}</figcaption>
              </figure>
              <figure className={`view scene ${place("3d")}`} hidden={!voting} onClick={() => main !== "3d" && setPicked("3d")}>
                <Scene3D s={s} />
                <figcaption>{VIEW_NAME["3d"]}</figcaption>
              </figure>

              {voting && main !== "3d" && (
                // the software layer over the footage: one line, three numbers
                <dl className="lower">
                  <div className="k-truth"><dt>True altitude</dt><dd>{mm(s.truth)}<small> mm</small></dd></div>
                  <div className={`k-legacy ${Math.abs(legacyErr ?? 0) > ERR_BAD_MM ? "bad" : ""}`}>
                    <dt>Legacy gate</dt><dd>{mm(s.legacy.est)}<em>{signed(legacyErr)}</em></dd>
                  </div>
                  <div className={`k-so ${Math.abs(soErr ?? 0) > ERR_BAD_MM ? "bad" : ""}`}>
                    <dt>Second Opinion</dt><dd>{mm(s.so.est)}<em>{signed(soErr)}</em></dd>
                  </div>
                </dl>
              )}
            </div>

            <div className="story">
              {clips.length > 1 && clip && (
                <nav className="clips" aria-label="Footage">
                  {clips.map((c) => (
                    <button key={c.id} className={c.id === clip.id ? "on" : ""} onClick={() => cmd(`clip:${c.id}`)}>{c.name}</button>
                  ))}
                </nav>
              )}
              {voting ? (
                <>
                  <h2 className={tone}>{line}</h2>
                  <p className="then">{consequence(legacyErr, soErr)}</p>
                </>
              ) : (
                <>
                  <h2 className="idle">Camera only. This footage has no altitude record, so there is nothing to vote on.</h2>
                  <p className="then">The estimator tracks the real surface and reads time-to-contact from how fast it grows.</p>
                </>
              )}
              {/* cues are instructions for whoever is working the physical rig */}
              {sc?.cue && s.kind === "live" && <p className="cue">{sc.cue}</p>}
              {sc && (
                <p className="about">
                  <b>{sc.name}</b> <span>{sc.mission}</span> {sc.summary}
                </p>
              )}
              {clip && !sc && (
                <p className="about">
                  <b>{clip.name}</b> <span>{clip.mission}</span> {clip.note}
                </p>
              )}
              {sc && main === "tv" && sc.broadcast_note ? <p className="credit">{sc.broadcast_note}</p>
                : sc && clip ? (
                  <p className="credit">
                    Camera: real footage of {clip.name} landing on the Moon ({clip.credit}). This mission's sensor failure is
                    injected into the stream; rangefinder and inertial come from NASA's altitude labels, 10 mm = 1 m.
                  </p>
                ) : sc?.site_note && <p className="credit">{sc.site_note}</p>}
              {!sc && !clip && <p className="about">Press <b>1</b> to <b>{Math.max(scenarios.length, 1)}</b> to replay a real landing through both brains.</p>}
            </div>
          </section>

          {voting ? (
            <aside className="right">
              <section className="how-high">
                <h4>How high are we? <span>Everything that is not on the white line is wrong.</span></h4>
                <Lanes s={s} />
              </section>
              <section className="brains">
                <BrainCard title="Legacy gate" tone="legacy" b={s.legacy} truth={s.truth} score={s.score.legacy} />
                <BrainCard title="Second Opinion" tone="so" b={s.so} truth={s.truth} score={s.score.so} />
              </section>
              <p className="flight">
                {s.v > 1 ? `Descending at ${s.v.toFixed(0)} mm/s` : "Holding"}
                {tau != null && <> · camera says {tau.toFixed(1)} s to contact</>}
                {Math.abs(terrain) > 10 && <> · ground moved {signed(terrain)} mm since reset</>}
              </p>
              <section className="evidence">
                <div>
                  <h4>The vote <span>how strongly each pair disagrees</span></h4>
                  <VoteTriangle so={s.so} reanchored={reanchored} />
                </div>
                <div>
                  <h4>Last 20 seconds <span>mm</span></h4>
                  <AltitudePlot history={history} tick={s.t} />
                </div>
              </section>
            </aside>
          ) : (
            <aside className="right tracking">
              <h4>Camera only</h4>
              <dl>
                <div><dt>Time to contact</dt><dd>{s.tau_raw == null ? "—" : s.tau_raw.toFixed(1)}<small> s</small></dd></div>
                <div><dt>Tracking quality</dt><dd>{s.q_raw.toFixed(2)}</dd></div>
              </dl>
              <p>
                Time-to-contact assumes a steady approach straight toward the surface, so treat this number as
                indicative. No altitude record was published with this video, so the rangefinder and inertial
                witnesses have nothing honest to be built from.
              </p>
            </aside>
          )}
        </main>
      ) : (
        <main className="offline">
          <h2>{connected ? "Connected. Waiting for the first frame." : "No engine connection."}</h2>
          <p>Start it with <code>python -m so serve --sim</code> and this page picks it up on its own.</p>
        </main>
      )}

      <ScenarioPanel s={s} scenarios={scenarios} voiceOn={voiceOn} onVoice={toggleVoice} />
    </div>
  );
}
