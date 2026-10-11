import { useEffect, useRef, useState } from "react";
import type { State } from "./types";

export const HISTORY_S = 20;

/** Live state over WebSocket, a rolling history for the plot, and an event callback. */
export function useTelemetry(onEvent: (key: string, s: State) => void) {
  const [state, setState] = useState<State | null>(null);
  const [connected, setConnected] = useState(false);
  const history = useRef<State[]>([]);
  const cb = useRef(onEvent);
  cb.current = onEvent;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closed) setTimeout(connect, 1000);
      };
      ws.onmessage = (m) => {
        const s: State = JSON.parse(m.data);
        const h = history.current;
        if (h.length && s.t < h[h.length - 1].t) h.length = 0; // replay looped / reset
        h.push(s);
        while (h.length && s.t - h[0].t > HISTORY_S) h.shift();
        s.events.forEach((e) => cb.current(e, s));
        setState(s);
      };
    };
    connect();
    return () => {
      closed = true;
      ws?.close();
    };
  }, []);

  return { state, connected, history };
}

export const cmd = (name: string) => fetch(`/cmd/${encodeURIComponent(name)}`, { method: "POST" });
