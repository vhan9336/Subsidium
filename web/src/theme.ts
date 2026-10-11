// Colour tokens for canvas and three.js, which can't read CSS variables. Keep identical to styles.css.
export const C = {
  bg: "#0b0b0c",
  panel: "#0b0b0c",
  line: "#272725",
  ink: "#ededea",
  dim: "#8f8f8a",
  off: "#5a5a55", // excluded / abstaining
  truth: "#f2f2f2",
  rf: "#f2b84b",
  nav: "#7d8fa6",
  cam: "#4fd1e8",
  legacy: "#ff5d5d",
  so: "#5be38a",
} as const;

export const MONO = '"Cascadia Mono", "Cascadia Code", Consolas, ui-monospace, Menlo, monospace';
/** Numerals and headings: a DIN-style face that ships with Windows, with close fallbacks. */
export const DISPLAY = 'Bahnschrift, "DIN Alternate", "Avenir Next Condensed", "Roboto Condensed", "Segoe UI", sans-serif';

/** The engine's status strings, said the way you would say them out loud. */
export function plainStatus(status: string, brain: "legacy" | "so"): string {
  if (brain === "legacy") {
    if (status === "RF REJECTED") return "Rejecting the rangefinder reading";
    if (status === "RF DECLARED FAILED") return "Has declared the rangefinder failed";
    return "Trusting inertial and rangefinder";
  }
  const noLock = status.includes("CAMERA ABSTAINING");
  if (status.startsWith("UNRESOLVED")) return "Can't tell which sensor is wrong: assuming the closest ground";
  if (status.startsWith("RANGEFINDER SILENT")) return "Rangefinder silent: checking inertial against the camera";
  if (status.startsWith("RANGEFINDER EXCLUDED")) return "Ignoring the rangefinder: it was outvoted";
  if (status.startsWith("CAMERA EXCLUDED")) return "Ignoring the camera: it was outvoted";
  return noLock ? "Inertial and rangefinder agree; camera has no lock" : "All three witnesses agree";
}

/** Error beyond this (mm) is shown as bad. A display threshold only, not an engine setting. */
export const ERR_BAD_MM = 25;

// The engine works in rig millimetres. Real footage is shown in the mission's own metres:
// setUnit() is called once per render with the clip's scale, and mm() / signed() convert.
let perMm = 1;
let unitName = "mm";
export function setUnit(mmPerM: number | null | undefined) {
  perMm = mmPerM ? 1 / mmPerM : 1;
  unitName = mmPerM ? "m" : "mm";
}
export const unit = () => unitName;
const show = (x: number) => (perMm < 1 ? x.toFixed(1) : Math.round(x).toLocaleString("en-US"));

export const mm = (v: number | null | undefined) => (v == null ? "—" : show(v * perMm));

export const signed = (v: number | null | undefined) => {
  if (v == null) return "—";
  const r = perMm < 1 ? Math.round(v * perMm * 10) / 10 : Math.round(v * perMm);
  return `${r > 0 ? "+" : r < 0 ? "−" : "±"}${show(Math.abs(r))}`;
};

/** A tick spacing (engine mm) that gives at most about six ticks up to `top`. */
export const niceStep = (top: number) => [25, 50, 100, 250, 500, 1000, 2500, 5000].find((st) => top / st <= 6.5) ?? 10000;

/** Short labels for engine events (plot markers and the event log). */
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
