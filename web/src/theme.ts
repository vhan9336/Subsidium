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

export const mm = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v)}`);

export const signed = (v: number | null | undefined) => {
  if (v == null) return "—";
  const r = Math.round(v);
  return `${r > 0 ? "+" : r < 0 ? "−" : "±"}${Math.abs(r)}`;
};

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
