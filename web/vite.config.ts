import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` proxies the engine (python -m so serve ...) on :8000
const engine = "http://localhost:8000";
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/ws": { target: engine.replace("http", "ws"), ws: true },
      "/video": engine,
      "/frame.jpg": engine,
      "/broadcasts": engine,
      "/cmd": engine,
      "/scenarios": engine,
      "/clips": engine,
      "/proof": engine,
      "/sites": engine,
    },
  },
});
