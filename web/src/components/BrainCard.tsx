// One brain in one line: what it believes, how wrong that is, and what it is doing about it,
// in plain words. Sized to be read from across the room.
import { ERR_BAD_MM, mm, plainStatus, signed } from "../theme";
import type { Brain, Score } from "../types";

export default function BrainCard({ title, tone, b, truth, score }: {
  title: string;
  tone: "legacy" | "so";
  b: Brain;
  truth: number | null;
  score: Score;
}) {
  const err = b.est != null && truth != null ? b.est - truth : null;
  const bad = err != null && Math.abs(err) > ERR_BAD_MM;
  return (
    <div className={`brain ${tone}`}>
      <div className="who">
        <h3>{title}</h3>
        <p>{plainStatus(b.status, tone)}</p>
      </div>
      <div className="num">
        <b>{mm(b.est)}</b>
        <span>believes, mm</span>
      </div>
      <div className={`num ${err == null ? "" : bad ? "bad" : "good"}`}>
        <b>{signed(err)}</b>
        <span>off truth · worst {score.max.toFixed(0)}</span>
      </div>
    </div>
  );
}
