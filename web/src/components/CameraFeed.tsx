// The camera image, pulled one frame at a time. A plain <img> on the MJPEG stream sometimes went
// black in Chrome and stayed black; fetching frames cannot stall that way, and it recovers on
// its own when the engine restarts.
import { useEffect, useRef } from "react";

export default function CameraFeed({ alt }: { alt: string }) {
  const ref = useRef<HTMLImageElement>(null);
  useEffect(() => {
    let live = true;
    let timer = 0;
    let last = "";
    const next = async () => {
      let wait = 60;
      try {
        const r = await fetch("/frame.jpg", { cache: "no-store" });
        if (!r.ok) throw new Error(String(r.status));
        const url = URL.createObjectURL(await r.blob());
        if (live && ref.current) ref.current.src = url;
        if (last) URL.revokeObjectURL(last);
        last = url;
      } catch {
        wait = 600; // engine not up yet
      }
      if (live) timer = window.setTimeout(next, wait);
    };
    next();
    return () => {
      live = false;
      clearTimeout(timer);
      if (last) URL.revokeObjectURL(last);
    };
  }, []);
  return <img ref={ref} alt={alt} />;
}
