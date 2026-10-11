// What the three witnesses are called, and where each one's reading comes from.
import type { State } from "./types";

export const NAME = { nav: "Inertial", rf: "Rangefinder", cam: "Camera" } as const;
export type Sensor = keyof typeof NAME;
export const SENSORS = Object.keys(NAME) as Sensor[];

/** Says where a sensor's reading came from: the rig, the simulator, or a clip. */
export function origin(s: State, sensor: Sensor): string {
  const clip = s.clip;
  if (s.kind === "live") return sensor === "nav" ? "servo angle, or the ultrasonic's own trend with no motor" : "measured on the rig";
  if (!clip) return "simulated";
  if (sensor === "cam") return clip.camera === "reconstructed" ? "reconstructed from the true altitude" : "measured from the footage";
  if (clip.believed) return sensor === "nav" ? "the altitude on the broadcast display" : "reconstructed from the true altitude";
  return "generated from the on-screen altitude record";
}

/** How a witness is doing right now, in a word or two. */
export function sensorState(s: State, sensor: Sensor): string {
  const reading = s.so.witness[sensor];
  if (s.so.excluded.includes(sensor)) return reading ? "outvoted" : "silent";
  if (!reading) return sensor === "cam" ? "no lock" : "silent";
  return "voting";
}
