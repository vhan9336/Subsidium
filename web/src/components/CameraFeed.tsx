// The camera image, fetched one frame at a time. A plain <img> pointed at the MJPEG stream
// sometimes went black in Chrome and stayed that way. Fetching frames can't stall like that, and
// it recovers on its own if the engine restarts.
import { useEffect, useRef } from "react";

export default function CameraFeed({ alt, src = "/frame.jpg" }: { alt: string; src?: string }) {
  const img = useRef<HTMLImageElement>(null);
  useEffect(() => {
    let live = true;
    let timer = 0;
    let url = "";
    const next = async () => {
      let wait = 60;
      try {
        const r = await fetch(src, { cache: "no-store" });
        if (!r.ok) throw new Error(String(r.status));
        const fresh = URL.createObjectURL(await r.blob());
        if (live && img.current) img.current.src = fresh;
        if (url) URL.revokeObjectURL(url);
        url = fresh;
      } catch {
        wait = 600; // the engine isn't up yet
      }
      if (live) timer = window.setTimeout(next, wait);
    };
    next();
    return () => {
      live = false;
      clearTimeout(timer);
      if (url) URL.revokeObjectURL(url);
    };
  }, [src]);
  return <img ref={img} alt={alt} />;
}
