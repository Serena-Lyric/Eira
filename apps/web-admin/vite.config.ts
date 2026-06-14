import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import vueJsx from "@vitejs/plugin-vue-jsx"
import { fileURLToPath } from "node:url"
import path from "node:path"

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [vue(), vueJsx()],
  resolve: {
    alias: {
      "@shared/live2d": path.resolve(__dirname, "../shared/live2d"),
      // Vendored Cubism SDK for Web 5 Framework (shared copy for admin preview).
      "@framework": path.resolve(__dirname, "src/live2d-framework"),
      // Resolve jszip for shared/live2d module (pnpm strict mode)
      jszip: path.resolve(__dirname, "../../node_modules/.pnpm/jszip@3.10.1/node_modules/jszip"),
    },
  },
  server: { port: 5174, proxy: { "/api": { target: "http://localhost:8000", rewrite: (path: string) => path.replace(/^\/api/, "") }, "/oss": { target: "http://localhost:9000", changeOrigin: true, rewrite: (path: string) => path.replace(/^\/oss/, "") } } },
  test: { environment: "happy-dom", globals: true },
})
