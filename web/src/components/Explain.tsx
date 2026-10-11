// The presentation, opened with E. It's a Canva design shown in an iframe.
// Set canva_url in config.toml, or paste a link into the box the first time. The page remembers it.
import { useEffect, useState } from "react";

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

export default function Explain({ onClose }: { onClose: () => void }) {
  const [url, setUrl] = useState<string | null>(embedUrl(saved()));
  const [pasted, setPasted] = useState("");
  const [bad, setBad] = useState(false);

  // a link set in config.toml wins over one pasted earlier
  useEffect(() => {
    fetch("/presentation.json")
      .then((r) => r.json())
      .then((d: { url: string }) => d.url && setUrl(embedUrl(d.url)))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [onClose]);

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
    <div className="explain" role="dialog" aria-label="Presentation">
      <div className="explain-top">
        <span>{url ? <button onClick={forget}>Use a different link</button> : "Presentation"}</span>
        <button onClick={onClose}>Close <i>Esc</i></button>
      </div>
      {url ? (
        <iframe className="canva" title="Presentation" src={url} allow="fullscreen" allowFullScreen />
      ) : (
        <form className="canva-setup" onSubmit={(e) => { e.preventDefault(); save(); }}>
          <h2>Show your Canva presentation here</h2>
          <p>
            In Canva, open the design and choose Share, then More, then Embed, and copy the link. Paste it below.
            The page remembers it. To set it for good, put it in <code>canva_url</code> in <code>config.toml</code>.
          </p>
          <input value={pasted} onChange={(e) => setPasted(e.target.value)} placeholder="https://www.canva.com/design/…" aria-label="Canva link" autoFocus />
          <button type="submit">Show it</button>
          {bad && <p className="bad">That doesn't look like a Canva link. It should start with https://www.canva.com/.</p>}
        </form>
      )}
    </div>
  );
}
