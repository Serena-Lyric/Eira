import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import { fileURLToPath } from "node:url"
import path from "node:path"

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [vue()],
  resolve: {
    extensions: [".ts", ".js", ".mjs", ".json", ".vue"],
    alias: {
      // Vendored Cubism SDK for Web 5 Framework (copied into the repo).
      "@framework": path.resolve(__dirname, "src/live2d-framework"),
    },
  },
  server: { port: 5173, proxy: { "/api": { target: "http://localhost:8000", rewrite: (path: string) => path.replace(/^\/api/, "") } } },
  test: { environment: "happy-dom", globals: true },
})
