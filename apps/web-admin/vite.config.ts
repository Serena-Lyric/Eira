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
      // Vendored Cubism SDK for Web 5 Framework (shared copy for admin preview).
      "@framework": path.resolve(__dirname, "src/live2d-framework"),
    },
  },
  server: { port: 5174, proxy: { "/api": { target: "http://localhost:8000", rewrite: (path: string) => path.replace(/^\/api/, "") } } },
  test: { environment: "happy-dom", globals: true },
})
