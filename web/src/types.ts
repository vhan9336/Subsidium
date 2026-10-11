// The shape of the state dict that so/pipeline.py sends over the WebSocket. Keep the two in sync.

export type Witness = { h: number; sigma: number };

/** What the legacy gate believes. */
export type Brain = { est: number | null; status: string; excluded: string[] };

/** What Subsidium believes, plus the evidence behind it. */
export type Subsidium = Brain & {
  sigma: number | null;
  pairs: Record<"nav-rf" | "nav-cam" | "rf-cam", number | null>; // each pair's disagreement score
  gate: number; // a pair fails above this
  cam_abstain: boolean;
  witness: Partial<Record<"nav" | "rf" | "cam", Witness>>;
};

/** The mission replay that is running. */
export type ScenarioState = {
  id: string;
  name: string;
  mission?: string;
  summary?: string;
  expect?: string;
  setup?: string;
  cue?: string | null; // what the operator should do next on the real rig
  site?: string | null; // orbiter photo of the real crash site the camera flies over
  site_note?: string | null;
  t: number;
  done: boolean;
};

export type Score = { max: number; last: number | null };

/** The real-footage clip that is playing (only with `serve --video`). */
export type ClipState = {
  id: string;
  name: string;
  mission?: string | null;
  credit?: string | null;
  note?: string | null;
  truth: boolean; // false means tracking only: no altitude record, so nothing is voted on
  mm_per_m?: number | null;
  tau_gain: number;
  camera?: "measured" | "reconstructed"; // reconstructed: there's no descent camera in this footage, so one is drawn
  alt_view?: string | null; // a second picture to offer, like "Control center"
  believed?: boolean; // the altitude record is what the lander believed, not where it was
  pos: number;
  dur: number;
};

export type State = {
  t: number;
  kind: "sim" | "live" | "replay" | "video";
  recording: boolean;
  truth: number | null;
  nav: number;
  nav_raw: number;
  rf: number | null;
  rf_raw: number | null;
  cam: number | null;
  v: number;
  tau: number | null;
  q: number;
  tau_raw: number | null; // time to contact before the steady-descent check and fault injection
  q_raw: number;
  clip: ClipState | null;
  h0: number;
  descending: boolean;
  legacy: Brain;
  so: Subsidium;
  hazard: number[][] | null;
  site: [number, number] | null; // the safest tile of the hazard grid, as [row, column]
  rig: boolean; // whether a live rig is attached, so J can switch to it
  hazard_shown: boolean; // whether the grid is drawn over this camera image
  faults: string[];
  scenario: ScenarioState | null;
  events: string[];
  score: { legacy: Score; so: Score };
  playback: Playback;
};

/** Where the run is in its recorded history. The server keeps about a minute so you can scrub back through it. */
export type Playback = {
  paused: boolean;
  n: number; // how many moments are saved
  cursor: number; // which one is on screen (the last one when live)
  t0: number; // the time of the first and last saved moment, in seconds
  t1: number;
};

/** One entry in the list of footage clips from /clips (only with `serve --video`). */
export type ClipInfo = { id: string; name: string; truth: boolean };

/** One entry in the list of replays from /scenarios. */
export type ScenarioInfo = {
  id: string;
  name: string;
  mission?: string;
  footage?: boolean; // flies on real footage (true) or on the simulator (false)
  clip?: string | null; // flies on its own mission's broadcast
};
