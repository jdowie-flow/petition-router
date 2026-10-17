import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// While working on the pages, run the Python server too (uv run petition-router serve).
// Vite forwards /api to it.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": process.env.API_URL ?? "http://127.0.0.1:8000" },
  },
});
