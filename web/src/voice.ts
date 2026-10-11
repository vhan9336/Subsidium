// Spoken callouts. Each event plays a pre-made clip from /audio/<event>.mp3 (made by
// tools/make_callouts.py) and falls back to the browser's voice if the clip is missing.
// Keep these lines identical to LINES in tools/make_callouts.py.
const LINES: Record<string, string> = {
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

let enabled = false;
const lastSaid: Record<string, number> = {};

export const voice = {
  toggle() {
    enabled = !enabled;
    return enabled;
  },
  say(key: string) {
    if (!enabled || !LINES[key]) return;
    const now = performance.now();
    if (now - (lastSaid[key] ?? -Infinity) < 4000) return; // don't repeat the same line right away
    lastSaid[key] = now;
    new Audio(`/audio/${key}.mp3`).play().catch(() => {
      const u = new SpeechSynthesisUtterance(LINES[key]);
      u.rate = 1.05;
      speechSynthesis.speak(u);
    });
  },
};
