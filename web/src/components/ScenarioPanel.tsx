// Bottom bar: the mission replays (keys 1-5) and, quieter, the manual rig and fault controls.
import { cmd } from "../telemetry";
import type { ClipInfo, ScenarioInfo, State } from "../types";

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

export type PlaylistItem = { command: string; name: string; detail: string; hint?: string; scenarioId?: string; clipId?: string };

/**
 * Everything the number keys can start, in order: any real-footage clips, then the mission replays
 * (there are clips only when the engine runs with --video). Real footage comes first, to show what
 * Subsidium does. The replays follow: the healthy baseline, then the four crashes. The bottom bar
 * and the number keys share this list.
 */
export function playlist(scenarios: ScenarioInfo[], clips: ClipInfo[], mixed = false): PlaylistItem[] {
  const replays = scenarios.map((sc) => ({
    command: `scenario:${sc.id}`,
    scenarioId: sc.id,
    name: sc.name,
    detail: [sc.mission?.split(" · ").pop(), mixed && (sc.clip ? "real broadcast" : sc.footage ? "real footage" : "simulator")].filter(Boolean).join(" · "),
  }));
  const footage = clips.map((c) => ({
    command: `clip:${c.id}`,
    clipId: c.id,
    name: c.name,
    detail: c.truth ? "real footage" : "real footage, camera only",
    hint: c.truth ? "Has an altitude record, so all three witnesses run" : "No altitude record: camera tracking only",
  }));
  return [...footage, ...replays];
}

export default function ScenarioPanel({ s, scenarios, clips, voiceOn, onVoice, proof, onProof, onExplain }: {
  s: State | null;
  scenarios: ScenarioInfo[];
  clips: ClipInfo[];
  voiceOn: boolean;
  onVoice: () => void;
  proof: boolean;
  onProof: () => void;
  onExplain: () => void;
}) {
  const mixed = scenarios.some((sc) => sc.footage); // real footage is loaded: say what each replay flies on
  const items = playlist(scenarios, clips, mixed);
  const isOn = (item: PlaylistItem) => (item.clipId ? s?.clip?.id === item.clipId && !s?.scenario : s?.scenario?.id === item.scenarioId);
  return (
    <footer className="deck">
      <nav className="missions" aria-label="Replays and footage">
        {items.map((item, i) => (
          <button key={item.command} className={isOn(item) ? "on" : ""} onClick={() => cmd(item.command)} title={item.hint}>
            <i>{i + 1}</i>
            <span>{item.name}</span>
            <small>{item.detail}</small>
          </button>
        ))}
      </nav>
      <span className="tools">
        <button className="math" onClick={onExplain}>Presentation <i>E</i></button>
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
        {s?.scenario && <button onClick={() => cmd("scenario:stop")}>End replay</button>}
        <button className={s?.recording ? "on rec" : ""} onClick={() => cmd(s?.recording ? "record_stop" : "record_start")}>
          {s?.recording ? "Recording" : "Record"}
        </button>
        <button className={voiceOn ? "on" : ""} onClick={onVoice}>Voice {voiceOn ? "on" : "off"} <i>V</i></button>
      </div>}
    </footer>
  );
}
