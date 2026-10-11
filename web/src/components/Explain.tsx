// The slide walkthrough, opened with E. The slides are plain HTML files in the top-level slides/
// folder, listed by the engine in alphabetical order. Each one is drawn in an iframe on a fixed
// 1280 x 720 canvas that is scaled to fit the window. Left and right arrows move, Escape closes.
import { useEffect, useLayoutEffect, useRef, useState } from "react";

const W = 1280;
const H = 720;

export default function Explain({ onClose }: { onClose: () => void }) {
  const [files, setFiles] = useState<string[] | null>(null);
  const [failed, setFailed] = useState(false); // the slide list didn't load at all
  const [i, setI] = useState(0);
  const [scale, setScale] = useState(1);
  const box = useRef<HTMLDivElement>(null);
  const count = files?.length ?? 0;

  useEffect(() => {
    fetch("/slides.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((list) => setFiles(Array.isArray(list) ? list : []))
      .catch(() => setFailed(true));
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

  // The key handler reads the latest values through a ref, so it can be attached once.
  const latest = useRef({ count, onClose });
  latest.current = { count, onClose };
  const onKey = useRef((e: KeyboardEvent) => {
    const { count, onClose } = latest.current;
    const last = Math.max(count - 1, 0);
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "ArrowRight" || e.key === " " || e.key === "PageDown") setI((n) => Math.min(n + 1, last));
    else if (e.key === "ArrowLeft" || e.key === "PageUp") setI((n) => Math.max(n - 1, 0));
    else if (e.key === "Home") setI(0);
    else if (e.key === "End") setI(last);
    else if (e.key === "Escape" || e.key.toLowerCase() === "e") onClose();
    else return;
    e.preventDefault();
    e.stopImmediatePropagation(); // keep the dashboard's own shortcuts quiet while a slide is up
  });
  useEffect(() => {
    const handler = onKey.current;
    addEventListener("keydown", handler, true);
    return () => removeEventListener("keydown", handler, true);
  }, []);

  // Keys pressed while the slide itself has focus (after a click on it) go to the iframe, not to
  // this page, so listen there too.
  const hookSlideKeys = (e: React.SyntheticEvent<HTMLIFrameElement>) =>
    e.currentTarget.contentWindow?.addEventListener("keydown", onKey.current, true);

  const message = failed
    ? "Couldn't load the slide list. Restart the engine (python -m so serve) and reopen this."
    : files ? "No slides found. Add .html files to the slides folder." : "Loading slides…";

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
            onLoad={hookSlideKeys}
            style={{ width: W, height: H, transform: `translate(-50%, -50%) scale(${scale})` }}
          />
        </div>
      ) : (
        <div className="stage-box empty">{message}</div>
      )}
      <div className="explain-nav">
        <button onClick={() => setI((n) => Math.max(n - 1, 0))} disabled={i === 0}>Back</button>
        <div className="progress">
          {files?.map((f, n) => <button key={f} className={n === i ? "on" : ""} aria-label={f} onClick={() => setI(n)} />)}
        </div>
        <button onClick={() => setI((n) => Math.min(n + 1, count - 1))} disabled={i >= count - 1}>Next</button>
      </div>
    </div>
  );
}
