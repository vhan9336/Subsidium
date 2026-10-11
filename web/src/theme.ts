// Colours for the canvas and three.js code, which can't read CSS variables.
// Keep these identical to the tokens at the top of styles.css.
export const C = {
  bg: "#0b0b0c",
  line: "#272725",
  ink: "#ededea",
  dim: "#8f8f8a",
  off: "#5a5a55", // outvoted or abstaining
  truth: "#f2f2f2",
  rf: "#f2b84b",
  nav: "#7d8fa6",
  cam: "#4fd1e8",
  legacy: "#ff5d5d",
  so: "#5be38a",
} as const;

export const DISPLAY = 'Bahnschrift, "DIN Alternate", "Avenir Next Condensed", "Roboto Condensed", "Segoe UI", sans-serif';

/** The engine's status strings, said the way you'd say them out loud. */
export function plainStatus(status: string, brain: "legacy" | "so"): string {
  if (brain === "legacy") {
    if (status === "RF REJECTED") return "Rejecting the rangefinder reading";
    if (status === "RF DECLARED FAILED") return "Has declared the rangefinder failed";
    return "Trusting inertial and rangefinder";
  }
  if (status.startsWith("UNRESOLVED")) return "Can't tell which sensor is wrong: assuming the closest ground";
  if (status.startsWith("RANGEFINDER SILENT")) return "Rangefinder silent: checking inertial against the camera";
  if (status.startsWith("RANGEFINDER EXCLUDED")) return "Ignoring the rangefinder: it was outvoted";
  if (status.startsWith("CAMERA EXCLUDED")) return "Ignoring the camera: it was outvoted";
  return status.includes("CAMERA ABSTAINING") ? "Inertial and rangefinder agree; camera has no lock" : "All three witnesses agree";
}

/** An error bigger than this (in engine mm) is drawn red. It only affects colour, not the engine. */
export const ERR_BAD_MM = 25;

// The engine works in rig millimetres, but real footage is shown in the mission's own metres.
// App calls setUnit() once per render with the clip's scale, and mm() and signed() convert.
let perMm = 1;
let unitName = "mm";
export function setUnit(mmPerM: number | null | undefined) {
  perMm = mmPerM ? 1 / mmPerM : 1;
  unitName = mmPerM ? "m" : "mm";
}
export const unit = () => unitName;

// whole numbers in mm, one decimal in metres
const show = (x: number) => (perMm < 1 ? x.toFixed(1) : Math.round(x).toLocaleString("en-US"));
export const mm = (v: number | null | undefined) => (v == null ? "—" : show(v * perMm));

export function signed(v: number | null | undefined) {
  if (v == null) return "—";
  const r = perMm < 1 ? Math.round(v * perMm * 10) / 10 : Math.round(v * perMm);
  return `${r > 0 ? "+" : r < 0 ? "−" : "±"}${show(Math.abs(r))}`;
}

/** A gridline spacing (engine mm) that gives about six lines up to `top`. */
export const niceStep = (top: number) => [25, 50, 100, 250, 500, 1000, 2500, 5000].find((s) => top / s <= 6.5) ?? 10000;

/** Short labels for engine events. They mark the plot and decide which events get a log entry. */
export const EVENT_LABEL: Record<string, string> = {
  cam_lock: "CAM LOCK",
  terrain_change: "TERRAIN CHANGE",
  rf_fault: "RF EXCLUDED",
  cam_fault: "CAM EXCLUDED",
  rf_dropout: "RF SILENT",
  unresolved: "UNRESOLVED",
  cam_abstain: "CAM ABSTAINS",
  cam_back: "CAM BACK",
  recovered: "RECOVERED",
  rf_back: "RF BACK",
  legacy_rf_failed: "LEGACY: RF FAILED",
};
