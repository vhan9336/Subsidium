// The playback bar under the picture: restart, step back, pause or resume, step forward, and a
// slider that scrubs back through the last minute of the run. The server keeps the history.
// Moving the slider pauses the run where it is, and Resume carries on live from the latest moment.
import { useState, type ReactNode } from "react";
import { cmd } from "../telemetry";
import type { Playback as PlaybackState, State } from "../types";

/** The seek command that moves one second back (-1) or forward (1). */
export function stepCommand(p: PlaybackState, direction: -1 | 1): string {
  // the server saves a varying number of moments per second, so work out how many make a second
  const perSecond = Math.round(p.n / Math.max(p.t1 - p.t0, 1));
  return `seek:${p.cursor + direction * perSecond}`;
}

// Icon paths in the style of the open-source Lucide set (ISC license), drawn inline so the
// dashboard needs no network.
const ICONS = {
  restart: <><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" /></>,
  back: <><polygon points="19 20 9 12 19 4 19 20" /><line x1="5" x2="5" y1="19" y2="5" /></>,
  forward: <><polygon points="5 4 15 12 5 20 5 4" /><line x1="19" x2="19" y1="5" y2="19" /></>,
  play: <polygon points="6 3 20 12 6 21 6 3" />,
  pause: <><rect x="14" y="4" width="4" height="16" rx="1" /><rect x="6" y="4" width="4" height="16" rx="1" /></>,
};

function IconButton({ icon, label, onClick, big, disabled }: {
  icon: keyof typeof ICONS; label: string; onClick: () => void; big?: boolean; disabled?: boolean;
}): ReactNode {
  return (
    <button className={big ? "icon big" : "icon"} onClick={onClick} disabled={disabled} title={label} aria-label={label}>
      <svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        {ICONS[icon]}
      </svg>
    </button>
  );
}

const seconds = (t: number) => `${t.toFixed(1)} s`;

export default function Playback({ s }: { s: State }) {
  const p = s.playback;
  const canScrub = p.n >= 2;
  // while the slider is being dragged, show where the thumb is and not the (slightly late) server value
  const [dragging, setDragging] = useState<number | null>(null);

  return (
    <div className="playback">
      <IconButton icon="restart" label="Restart this replay" onClick={() => cmd("restart")} />
      <IconButton icon="back" label="Back one second (left arrow)" onClick={() => cmd(stepCommand(p, -1))} disabled={!canScrub} />
      <IconButton icon={p.paused ? "play" : "pause"} label={p.paused ? "Resume (space)" : "Pause (space)"}
        onClick={() => cmd(p.paused ? "resume" : "pause")} big />
      <IconButton icon="forward" label="Forward one second (right arrow)" onClick={() => cmd(stepCommand(p, 1))} disabled={!canScrub} />
      <input
        type="range"
        min={0}
        max={Math.max(p.n - 1, 0)}
        value={dragging ?? p.cursor}
        disabled={!canScrub}
        aria-label="Scrub through the run"
        onChange={(e) => {
          setDragging(Number(e.target.value));
          cmd(`seek:${e.target.value}`);
        }}
        onPointerUp={() => setDragging(null)}
        onBlur={() => setDragging(null)}
      />
      <span className="clock">{seconds(Math.min(s.t - p.t0, p.t1 - p.t0))} / {seconds(p.t1 - p.t0)}</span>
    </div>
  );
}
