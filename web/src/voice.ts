// Callouts: pre-generated ElevenLabs clips in /audio/<key>.mp3 (tools/make_callouts.py),
// falling back to the browser's speech synthesis if a clip is missing.

export const LINES: Record<string, string> = {
  cam_lock: "Camera locked on terrain.",
  terrain_change: "Ground fell away. Camera and rangefinder agree. Correcting the inertial estimate.",
  rf_fault: "Rangefinder outvoted by camera and inertial. Rangefinder excluded.",
  cam_fault: "Camera outvoted by inertial and rangefinder. Camera excluded.",
  rf_dropout: "Rangefinder silent. Cross-checking inertial with the camera.",
  unresolved: "Sources disagree and can't be isolated. Assuming the closest ground.",
  cam_abstain: "Camera abstaining. Not enough contrast.",
  cam_back: "Camera back.",
  recovered: "All three sources agree again.",
  rf_back: "Rangefinder back.",
};

/** One-line banner text and tone for each event. */
export const VERDICTS: Record<string, [string, "good" | "warn" | "bad"]> = {
  terrain_change: ["Real terrain change: camera + rangefinder outvote inertial", "good"],
  rf_fault: ["Rangefinder outvoted 2-to-1 and excluded", "good"],
  cam_fault: ["Camera outvoted 2-to-1 and excluded", "good"],
  rf_dropout: ["Rangefinder silent: inertial cross-checked by camera", "warn"],
  unresolved: ["Disagreement detected but not isolatable: assuming closest ground", "warn"],
  cam_abstain: ["Camera abstaining (low contrast)", "warn"],
  recovered: ["All three witnesses agree", "good"],
  legacy_rf_failed: ["Legacy gate declared a correct rangefinder failed", "bad"],
};

let enabled = false;
const last: Record<string, number> = {};

export const voice = {
  get enabled() {
    return enabled;
  },
  enable() {
    enabled = true;
  },
  toggle() {
    enabled = !enabled;
    return enabled;
  },
  say(key: string) {
    if (!enabled || !LINES[key]) return;
    const now = performance.now();
    if (last[key] && now - last[key] < 4000) return;
    last[key] = now;
    const a = new Audio(`/audio/${key}.mp3`);
    a.play().catch(() => {
      const u = new SpeechSynthesisUtterance(LINES[key]);
      u.rate = 1.05;
      speechSynthesis.speak(u);
    });
  },
};
