import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import vueJsx from "@vitejs/plugin-vue-jsx"

export default defineConfig({
  plugins: [vue(), vueJsx()],
  server: { port: 5174, proxy: { "/api": "http://localhost:8000" } },
  test: { environment: "happy-dom", globals: true },
})
