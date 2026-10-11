// Mirrors the state dict built in so/pipeline.py (keep in sync).

export type Witness = { h: number; sigma: number };

export type Brain = {
  est: number | null;
  status: string;
  excluded: string[];
};

export type SecondOpinion = Brain & {
  sigma: number | null;
  pairs: Record<"nav-rf" | "nav-cam" | "rf-cam", number | null>;
  gate: number;
  cam_abstain: boolean;
  witness: Partial<Record<"nav" | "rf" | "cam", Witness>>;
};

export type ScenarioState = {
  id: string;
  name: string;
  mission?: string;
  summary?: string;
  expect?: string;
  setup?: string;
  cue?: string | null;
  site?: string | null; // orbiter image of the real crash site that the camera flies over
  site_note?: string | null;
  broadcast?: string | null; // the mission's real landing broadcast, when downloaded
  broadcast_at?: number; // seconds into that clip to start from
  broadcast_note?: string | null;
  t: number;
  done: boolean;
};

export type Score = { max: number; last: number | null };

/** Real-footage clip being played (only with `serve --video`). */
export type ClipState = {
  id: string;
  name: string;
  mission?: string | null;
  credit?: string | null;
  note?: string | null;
  truth: boolean; // false = tracking only: no altitude record, nothing is voted on
  mm_per_m?: number | null;
  tau_gain: number;
  pos: number;
  dur: number;
};

export type ClipInfo = { id: string; name: string; mission?: string | null; truth: boolean };

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
  tau_raw: number | null; // camera time-to-contact before the steady-descent gate and fault injection
  q_raw: number;
  clip: ClipState | null;
  h0: number;
  descending: boolean;
  legacy: Brain;
  so: SecondOpinion;
  hazard: number[][] | null;
  site: [number, number] | null;
  faults: string[];
  scenario: ScenarioState | null;
  events: string[];
  score: { legacy: Score; so: Score };
};

export type ScenarioInfo = {
  id: string;
  name: string;
  mission?: string;
  summary?: string;
  setup?: string;
  expect?: string;
  source?: string;
  footage?: boolean; // flies on real footage (true) or on the simulator (false)
};
