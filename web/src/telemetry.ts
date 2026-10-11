import { useEffect, useRef, useState } from "react";
import type { State } from "./types";

export const HISTORY_S = 20;

/** Live state over a WebSocket, plus the last 20 seconds of it for the plot. Calls onEvent for each engine event. */
export function useTelemetry(onEvent: (key: string, s: State) => void) {
  const [state, setState] = useState<State | null>(null);
  const [connected, setConnected] = useState(false);
  const history = useRef<State[]>([]);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    let ws: WebSocket;
    let closed = false;
    const connect = () => {
      ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closed) setTimeout(connect, 1000); // the engine may just be restarting
      };
      ws.onmessage = (m) => {
        const s: State = JSON.parse(m.data);
        const h = history.current;
        if (h.length && s.t < h[h.length - 1].t) h.length = 0; // time went backwards: a replay looped or reset
        h.push(s);
        while (s.t - h[0].t > HISTORY_S) h.shift();
        s.events.forEach((e) => onEventRef.current(e, s));
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
