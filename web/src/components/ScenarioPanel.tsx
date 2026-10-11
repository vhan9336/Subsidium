// Bottom bar: the mission replays (keys 1-5) and, quieter, the manual rig and fault controls.
import { cmd } from "../telemetry";
import type { ScenarioInfo, State } from "../types";

const MOTION: [string, string, string][] = [
  ["D", "Descend", "descend"],
  ["S", "Stop", "stop"],
  ["U", "Up", "up"],
  ["R", "Reset", "reset"],
  ["T", "Plateau in", "terrain_up"],   // slides the 60 mm plateau under the lander
  ["Y", "Plateau out", "terrain_down"], // and takes it away again
];
const FAULTS: [string, string][] = [
  ["rf_lag", "Rangefinder lag"],
  ["rf_freeze", "Rangefinder freeze"],
  ["rf_drop", "Rangefinder silent"],
  ["cam_bias", "Camera bias"],
  ["cam_blind", "Camera blind"],
];

export default function ScenarioPanel({ s, scenarios, voiceOn, onVoice, proof, onProof, onExplain }: {
  s: State | null;
  scenarios: ScenarioInfo[];
  voiceOn: boolean;
  onVoice: () => void;
  proof: boolean;
  onProof: () => void;
  onExplain: () => void;
}) {
  const active = s?.scenario ?? null;
  const mixed = scenarios.some((sc) => sc.footage); // real footage is loaded: say what each replay flies on
  return (
    <footer className="deck">
      <nav className="missions" aria-label="Mission replays">
        {scenarios.map((sc, i) => (
          <button key={sc.id} className={active?.id === sc.id ? "on" : ""} onClick={() => cmd(`scenario:${sc.id}`)}>
            <i>{i + 1}</i>
            <span>{sc.name}</span>
            <small>{sc.mission}{mixed && <em>{sc.clip ? "real broadcast" : sc.footage ? "real footage" : "simulator"}</em>}</small>
          </button>
        ))}
      </nav>
      <span className="tools">
        <button className="math" onClick={onExplain}>Walkthrough <i>E</i></button>
        <button className={`math ${proof ? "on" : ""}`} onClick={onProof}>{proof ? "Back to the landing" : "The math"} <i>M</i></button>
      </span>
      {proof && <div className="manual">
        <span className="label">Fly by hand</span>
        {MOTION.map(([key, name, c]) => (
          <button key={c} className={c === "descend" && s?.descending ? "on" : ""} onClick={() => cmd(c)}>
            {name} <i>{key}</i>
          </button>
        ))}
        <span className="label">Break a sensor</span>
        {FAULTS.map(([c, name]) => (
          <button key={c} className={s?.faults.includes(c) ? "on hot" : ""} onClick={() => cmd(`fault:${c}`)}>{name}</button>
        ))}
        <button onClick={() => cmd("fault:clear")}>Clear <i>0</i></button>
        <span className="spacer" />
        {active && <button onClick={() => cmd("scenario:stop")}>End replay</button>}
        <button className={s?.recording ? "on rec" : ""} onClick={() => cmd(s?.recording ? "record_stop" : "record_start")}>
          {s?.recording ? "Recording" : "Record"}
        </button>
        <button className={voiceOn ? "on" : ""} onClick={onVoice}>Voice {voiceOn ? "on" : "off"} <i>V</i></button>
      </div>}
    </footer>
  );
}
