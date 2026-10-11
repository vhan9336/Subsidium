import { useEffect, useRef, useState } from "react";
import CameraFeed from "./components/CameraFeed";
import Explain from "./components/Explain";
import FootageHud from "./components/FootageHud";
import LiveData from "./components/LiveData";
import Playback, { stepCommand } from "./components/Playback";
import Proof from "./components/Proof";
import ScenarioPanel, { playlist } from "./components/ScenarioPanel";
import Scene3D from "./components/Scene3D";
import { cmd, useTelemetry } from "./telemetry";
import { ERR_BAD_MM, EVENT_LABEL, mm, plainStatus, setUnit, signed, timeToContact, unit } from "./theme";
import type { ClipInfo, ScenarioInfo, State } from "./types";
import { voice } from "./voice";

type Logged = { key: string; t: number };
type View = "cam" | "3d";
type Tone = "good" | "warn" | "bad" | "idle";
const VIEW_NAME: Record<View, string> = { cam: "Lander camera", "3d": "3D view" };
const SOURCE = { sim: "Simulator", live: "Live rig", replay: "Recorded run", video: "Real footage" };

// keys that send a command straight to the engine
const KEYS: Record<string, string> = {
  d: "descend", s: "stop", u: "up", r: "reset", t: "terrain_up", y: "terrain_down", "0": "fault:clear",
};

/** What's going on right now in one sentence, read from the live state and not from old events. */
function headline(s: State, log: Logged[]): [string, Tone] {
  const so = s.so;
  if (so.status.startsWith("UNRESOLVED")) return ["The sensors disagree and none can be singled out. Assuming the closest ground.", "warn"];
  if (so.status.startsWith("RANGEFINDER SILENT")) return ["The rangefinder is silent. Inertial is being checked against the camera.", "warn"];
  if (so.excluded.includes("rf")) return ["The rangefinder was outvoted two to one. Subsidium is ignoring it.", "good"];
  if (so.excluded.includes("cam")) return ["The camera was outvoted two to one. Subsidium is ignoring it.", "good"];
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

/** Says how far off each brain is, in plain words. */
function consequence(legacyErr: number | null, soErr: number | null): string {
  if (legacyErr == null || soErr == null) return "";
  const off = (e: number) => `${mm(Math.abs(e))} ${unit()} too ${e < 0 ? "low" : "high"}`;
  const legacyBad = Math.abs(legacyErr) > ERR_BAD_MM;
  const soBad = Math.abs(soErr) > ERR_BAD_MM;
  if (legacyBad && !soBad) return `The legacy gate believes it is ${off(legacyErr)}. Subsidium is on the true altitude.`;
  if (legacyBad && soBad) return `The legacy gate is ${off(legacyErr)}; Subsidium is ${off(soErr)}.`;
  if (soBad) return `Subsidium is ${off(soErr)}; the legacy gate is on the true altitude.`;
  return "Both brains are on the true altitude.";
}

/**
 * When a brain thinks the ground will arrive, at the current descent speed. For a brain's own
 * estimate it also says how far that is from the real time, so a gate that believes it is lower
 * than it is reads as "early".
 */
function contactLine(altitude: number | null, truth: number | null, speed: number): string {
  const predicted = timeToContact(altitude, speed);
  if (predicted == null) return "";
  const text = `contact in ${predicted.toFixed(1)} s`;
  const actual = timeToContact(truth, speed);
  if (actual == null || altitude === truth) return text;
  const off = predicted - actual;
  return Math.abs(off) < 0.05 ? `${text}, on time` : `${text}, ${Math.abs(off).toFixed(1)} s ${off < 0 ? "early" : "late"}`;
}

export default function App() {
  const [log, setLog] = useState<Logged[]>([]); // recent events, which the headline reads
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [clips, setClips] = useState<ClipInfo[]>([]);
  const [voiceOn, setVoiceOn] = useState(false);
  const [picked, setPicked] = useState<View | null>(null); // the view the user chose to enlarge
  const [proof, setProof] = useState(false);
  const [explain, setExplain] = useState(false);
  const { state: s, connected, history } = useTelemetry((key, st) => {
    voice.say(key);
    if (EVENT_LABEL[key]) setLog((l) => [...l.filter((e) => e.t <= st.t).slice(-8), { key, t: st.t }]);
  });

  useEffect(() => {
    fetch("/scenarios").then((r) => r.json()).then(setScenarios).catch(() => {});
    fetch("/clips").then((r) => r.json()).then(setClips).catch(() => {});
  }, [connected]);

  const clip = s?.clip ?? null;
  setUnit(clip?.mm_per_m); // real footage is shown in the mission's metres, the rig in mm
  const rebuilt = clip?.camera === "reconstructed"; // a mission broadcast, so there's no descent camera in the picture
  const voting = !clip || clip.truth; // a clip with no altitude record is tracking only
  const sc = s?.scenario ?? null;

  // Real footage is one picture with the software layer over it. The simulator and the rig lead
  // with the 3D view and keep the camera as a thumbnail.
  const views: View[] = s?.kind === "video" ? ["cam"] : ["3d", "cam"];
  const main: View = picked && views.includes(picked) ? picked : views[0];
  const place = (v: View) => (v === main ? "is-main" : "is-thumb");
  const swapViews = () => setPicked(views[(views.indexOf(main) + 1) % views.length]);

  useEffect(() => setLog([]), [sc?.id]); // a new replay starts with a clean history
  useEffect(() => setPicked(null), [s?.kind]); // footage and simulator each lead with their own view

  // The key handler is set up once, so it reads the latest values through this ref.
  const items = playlist(scenarios, clips);
  const latest = useRef({ items, swapViews, playback: s?.playback });
  latest.current = { items, swapViews, playback: s?.playback };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
      if ((e.target as HTMLElement).closest?.("input, textarea")) return; // typing in a box isn't a shortcut
      const k = e.key.toLowerCase();
      const { items, swapViews, playback } = latest.current;
      if (k === "v") setVoiceOn(voice.toggle());
      else if (k === " " && playback) cmd(playback.paused ? "resume" : "pause");
      else if ((k === "arrowleft" || k === "arrowright") && playback) cmd(stepCommand(playback, k === "arrowleft" ? -1 : 1));
      else if (k === "e") {
        e.preventDefault(); // or the box that opens would receive this keystroke
        setExplain(true);
      }
      else if (k === "m") setProof((p) => !p);
      else if (k === "escape") setProof(false);
      else if (k === "c") swapViews();
      else if (KEYS[k]) {
        if (k === "r") setLog([]);
        cmd(KEYS[k]);
      } else if (Number(k) >= 1 && items[Number(k) - 1]) cmd(items[Number(k) - 1].command);
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, []);

  const legacyErr = s?.truth != null && s.legacy.est != null ? s.legacy.est - s.truth : null;
  const soErr = s?.truth != null && s.so.est != null ? s.so.est - s.truth : null;
  const reanchored = !!s && log.some((e) => e.key === "terrain_change" && s.t >= e.t && s.t - e.t < 4); // for the vote triangle
  // when scrubbing, only count events that had already happened at the moment on screen
  const seen = s ? log.filter((e) => e.t <= s.t) : log;
  const [line, tone] = s && voting ? headline(s, seen) : ["", "idle" as Tone];
  const badClass = (err: number | null) => (Math.abs(err ?? 0) > ERR_BAD_MM ? "bad" : "");

  return (
    <div className="app">
      <header className="bar">
        <h1>Subsidium</h1>
        <p>Three sensors report altitude. The odd one out is outvoted.</p>
        <div className="bar-right">
          {s?.faults.map((f) => <span key={f} className="fault">Injected fault: {f.replace("_", " ")}</span>)}
          <span className={`source ${connected ? "" : "down"}`}>{connected ? SOURCE[s?.kind ?? "sim"] : "Engine offline"}</span>
        </div>
      </header>

      {s && proof ? <Proof s={s} history={history} reanchored={reanchored} /> : s ? (
        <main>
          <section className="left">
            <div className={`stage main-${main} ${views.length === 1 ? "solo" : ""}`}>
              {/* both views stay mounted. C or a click on the thumbnail swaps which one is large */}
              <figure className={`view ${place("cam")} ${rebuilt ? "broadcast" : ""}`} onClick={() => setPicked("cam")}>
                <CameraFeed alt="Downward camera" />
                {voting && <FootageHud s={s} verdict={verdict(s, seen)} tone={tone} />}
                <figcaption>{VIEW_NAME.cam}</figcaption>
              </figure>
              <figure className={`view scene ${place("3d")}`} hidden={!views.includes("3d")} onClick={() => main !== "3d" && setPicked("3d")}>
                <Scene3D s={s} />
                <figcaption>{VIEW_NAME["3d"]}</figcaption>
              </figure>
            </div>
            <Playback s={s} />
          </section>

          {voting ? (
            // the picture on the left, and beside it: what happened, in one sentence and three numbers
            <aside className="right">
              <p className="mission">
                {sc ? <><b>{sc.name}</b> {sc.mission}</> : clip ? <><b>{clip.name}</b> {clip.mission}</>
                  : <>Press <b>1</b> to <b>{Math.max(items.length, 1)}</b> to replay a landing through both brains. Press <b>E</b> for the presentation.</>}
              </p>
              <h2 className={tone}>{line}</h2>
              <p className="then">{consequence(legacyErr, soErr)}</p>
              {/* a cue is an instruction for whoever is working the physical rig */}
              {sc?.cue && s.kind === "live" && <p className="cue">{sc.cue}</p>}

              <LiveData s={s} events={log} />

              <dl className="three">
                <div className="k-truth">
                  <dt>True altitude <span>{contactLine(s.truth, null, s.v) || "actual contact time appears once it descends"}</span></dt>
                  <dd>{mm(s.truth)}<small> {unit()}</small></dd>
                </div>
                <div className={`k-legacy ${badClass(legacyErr)}`}>
                  <dt>Legacy gate <span>{plainStatus(s.legacy.status, "legacy")}<br />{contactLine(s.legacy.est, s.truth, s.v)}</span></dt>
                  <dd>{mm(s.legacy.est)}<em>{signed(legacyErr)}</em></dd>
                </div>
                <div className={`k-so ${badClass(soErr)}`}>
                  <dt>Subsidium <span>{plainStatus(s.so.status, "so")}<br />{contactLine(s.so.est, s.truth, s.v)}</span></dt>
                  <dd>{mm(s.so.est)}<em>{signed(soErr)}</em></dd>
                </div>
              </dl>

              <p className="credit">
                {rebuilt ? clip.note
                  : clip ? <>Camera: real footage of {clip.name} landing on the Moon ({clip.credit}). Rangefinder and inertial come from NASA's on-screen altitude labels.{s.faults.length > 0 && " This mission's sensor failure is injected."}</>
                  : sc?.site_note}
                {" "}Press <b>M</b> for the math.
              </p>
            </aside>
          ) : (
            <aside className="right tracking">
              <h4>Camera only</h4>
              <dl>
                <div><dt>Time to contact</dt><dd>{s.tau_raw == null ? "—" : s.tau_raw.toFixed(1)}<small> s</small></dd></div>
                <div><dt>Tracking quality</dt><dd>{s.q_raw.toFixed(2)}</dd></div>
              </dl>
              <p>
                Time to contact assumes a steady approach straight toward the surface, so read this number as a
                rough guide. This video came with no altitude record, so there is nothing real to build the
                rangefinder and inertial readings from.
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

      <ScenarioPanel s={s} scenarios={scenarios} clips={clips} voiceOn={voiceOn} onVoice={() => setVoiceOn(voice.toggle())}
        proof={proof} onProof={() => setProof((p) => !p)} onExplain={() => setExplain(true)} />
      {explain && <Explain onClose={() => setExplain(false)} />}
    </div>
  );
}
