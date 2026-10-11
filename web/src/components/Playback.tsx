// The playback bar under the picture: restart, pause or resume, and a slider that scrubs back
// through the last minute of the run. The server keeps the history. Moving the slider pauses the
// run where it is, and Resume carries on live from the latest moment.
import { useState } from "react";
import { cmd } from "../telemetry";
import type { State } from "../types";

const seconds = (t: number) => `${t.toFixed(1)} s`;

export default function Playback({ s }: { s: State }) {
  const p = s.playback;
  // while the slider is being dragged, show where the thumb is and not the (slightly late) server value
  const [dragging, setDragging] = useState<number | null>(null);
  const position = dragging ?? p.cursor;

  return (
    <div className="playback">
      <button onClick={() => cmd("restart")} title="Run this replay again from the start">Restart</button>
      <button className="play" onClick={() => cmd(p.paused ? "resume" : "pause")}>
        {p.paused ? "Resume" : "Pause"} <i>Space</i>
      </button>
      <input
        type="range"
        min={0}
        max={Math.max(p.n - 1, 0)}
        value={position}
        disabled={p.n < 2}
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
