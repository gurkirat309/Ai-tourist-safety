import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev server proxies /api -> FastAPI backend on :8000 (no CORS needed).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // 127.0.0.1 + an 8xxx port avoids Windows/WinNAT reserved-range EACCES
    // (e.g. 5173 sits inside a reserved range on this machine).
    host: "127.0.0.1",
    port: 8080,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
