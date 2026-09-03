import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Port 8000 is occupied by Docker/WSL on some machines (BLOCKERS.md B6), so the API port
// is overridable: VITE_API_PORT=8123 npm run dev — `make dev` passes it through for you.
const apiPort = process.env.VITE_API_PORT ?? "8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // The SPA talks to the API on the same origin in dev; no CORS dance.
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${apiPort}`,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
