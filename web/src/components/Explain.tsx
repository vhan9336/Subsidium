// The slide walkthrough, opened with E. The slides are plain HTML files in the top-level slides/
// folder, listed by the engine in alphabetical order. Each one is drawn in an iframe on a fixed
// 1280 x 720 canvas that is scaled to fit the window. Left/right arrows move, Escape closes.
import { useEffect, useLayoutEffect, useRef, useState } from "react";

const W = 1280;
const H = 720;

export default function Explain({ onClose }: { onClose: () => void }) {
  const [files, setFiles] = useState<string[] | null>(null);
  const [i, setI] = useState(0);
  const [scale, setScale] = useState(1);
  const box = useRef<HTMLDivElement>(null);
  const count = files?.length ?? 0;
  const go = (d: number) => setI((n) => Math.min(Math.max(n + d, 0), Math.max(count - 1, 0)));

  useEffect(() => {
    fetch("/slides.json").then((r) => r.json()).then(setFiles).catch(() => setFiles([]));
  }, []);

  // fit the 16:9 canvas inside whatever room the window leaves
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const fit = () => setScale(Math.min(el.clientWidth / W, el.clientHeight / H));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [count]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "ArrowRight" || e.key === " " || e.key === "PageDown") go(1);
      else if (e.key === "ArrowLeft" || e.key === "PageUp") go(-1);
      else if (e.key === "Home") setI(0);
      else if (e.key === "End") setI(Math.max(count - 1, 0));
      else if (e.key === "Escape" || e.key.toLowerCase() === "e") onClose();
      else return;
      e.preventDefault();
      e.stopImmediatePropagation(); // the dashboard's own shortcuts stay quiet while a slide is up
    };
    addEventListener("keydown", onKey, true);
    return () => removeEventListener("keydown", onKey, true);
  }, [count, onClose]);

  return (
    <div className="explain" role="dialog" aria-label="Walkthrough">
      <div className="explain-top">
        <span>{count ? `${i + 1} / ${count}` : ""}</span>
        <button onClick={onClose}>Close <i>Esc</i></button>
      </div>
      {count > 0 ? (
        <div className="stage-box" ref={box}>
          <iframe
            key={files![i]}
            title={files![i]}
            src={`/slides/${files![i]}`}
            style={{ width: W, height: H, transform: `translate(-50%, -50%) scale(${scale})` }}
          />
        </div>
      ) : (
        <div className="stage-box empty">
          {files ? "No slides found. Add .html files to the slides folder." : "Loading slides…"}
        </div>
      )}
      <div className="explain-nav">
        <button onClick={() => go(-1)} disabled={i === 0}>Back</button>
        <div className="progress">
          {files?.map((f, n) => <button key={f} className={n === i ? "on" : ""} aria-label={f} onClick={() => setI(n)} />)}
        </div>
        <button onClick={() => go(1)} disabled={i >= count - 1}>Next</button>
      </div>
    </div>
  );
}
