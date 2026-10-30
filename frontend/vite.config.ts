import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  cacheDir: "../var/vite-cache",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${process.env.BACKEND_PORT || "8010"}`,
        changeOrigin: true,
      },
      "/uploads": {
        target: `http://127.0.0.1:${process.env.BACKEND_PORT || "8010"}`,
        changeOrigin: true,
      },
    },
  },
});
