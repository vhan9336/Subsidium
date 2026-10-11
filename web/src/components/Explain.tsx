// The presentation, opened with E: a Canva design filling the whole screen.
// The link comes from canva_url in config.toml, or from a box on the page the first time.
//
// It loads in the background as soon as the page does, so the first time you open it there's
// nothing to wait for. It stays mounted and is only hidden when closed, so the frame is never
// reloaded and reopening drops you on the slide you left.
import { useEffect, useRef, useState } from "react";

const SAVED = "subsidium-canva-url";

/**
 * Turns whatever was pasted into an address Canva will show inside an iframe. It accepts the share
 * link, the embed link, or the whole <iframe> snippet from Canva's Embed option.
 */
export function embedUrl(pasted: string): string | null {
  const fromSnippet = pasted.match(/src=["']([^"']+)["']/);
  const url = (fromSnippet ? fromSnippet[1] : pasted).trim();
  if (!/^https:\/\/([\w-]+\.)?canva\.com\//.test(url)) return null;
  if (/[?&]embed\b/.test(url)) return url;
  return url + (url.includes("?") ? "&embed" : "?embed");
}

function saved(): string {
  try {
    return localStorage.getItem(SAVED) ?? "";
  } catch {
    return ""; // storage can be blocked, so the page just asks again next time
  }
}

export default function Explain({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [url, setUrl] = useState<string | null>(embedUrl(saved()));
  const [pasted, setPasted] = useState("");
  const [bad, setBad] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    input.current?.focus(); // the paste box, if there is one
    // when the frame has focus the browser keeps its keys, so make sure they come back to the page on close
    return () => (document.activeElement as HTMLElement | null)?.blur();
  }, [open]);

  // a link set in config.toml wins over one pasted earlier
  useEffect(() => {
    fetch("/presentation.json")
      .then((r) => r.json())
      .then((d: { url: string }) => d.url && setUrl(embedUrl(d.url)))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const save = () => {
    const next = embedUrl(pasted);
    setBad(!next);
    if (!next) return;
    try {
      localStorage.setItem(SAVED, next);
    } catch {
      /* the link still works for this visit */
    }
    setUrl(next);
  };
  const forget = () => {
    try {
      localStorage.removeItem(SAVED);
    } catch {
      /* nothing to clear */
    }
    setUrl(null);
  };

  return (
    <div className={`explain ${open ? "" : "closed"}`} role="dialog" aria-label="Presentation" aria-hidden={!open}>
      {url ? (
        <iframe className="canva" title="Presentation" src={url} allow="fullscreen" allowFullScreen />
      ) : (
        <form className="canva-setup" onSubmit={(e) => { e.preventDefault(); save(); }}>
          <h2>Show your Canva presentation here</h2>
          <p>
            In Canva, open the design and choose Share, then More, then Embed, and copy the link. Paste it below.
            The page remembers it. To set it for good, put it in <code>canva_url</code> in <code>config.toml</code>.
          </p>
          <input value={pasted} onChange={(e) => setPasted(e.target.value)} placeholder="https://www.canva.com/design/…" aria-label="Canva link" ref={input} />
          <button type="submit">Show it</button>
          {bad && <p className="bad">That doesn't look like a Canva link. It should start with https://www.canva.com/.</p>}
        </form>
      )}
      <div className="explain-controls">
        {url && <button onClick={forget}>Change link</button>}
        <button onClick={onClose}>Close <i>Esc</i></button>
      </div>
    </div>
  );
}
