import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  define: {
    "import.meta.env.VITE_APP_VERSION": JSON.stringify(process.env.npm_package_version || "0.1.0")
  },
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8020",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/u, "")
      }
    }
  },
  build: {
    outDir: "dist",
    emptyOutDir: true
  }
});
