import { defineStore } from "pinia"
import axios from "axios"

export const useAuthStore = defineStore("auth", {
  state: () => ({
    accessToken: localStorage.getItem("eira:at") || "",
    refreshToken: localStorage.getItem("eira:rt") || "",
    user: null as null | { id: number; email: string; role: string },
  }),
  actions: {
    async login(email: string, password: string) {
      const r = await axios.post("/api/auth/login", { email, password })
      this.accessToken = r.data.access_token
      this.refreshToken = r.data.refresh_token
      localStorage.setItem("eira:at", this.accessToken)
      localStorage.setItem("eira:rt", this.refreshToken)
    },
    logout() {
      this.accessToken = ""
      this.refreshToken = ""
      this.user = null
      localStorage.removeItem("eira:at")
      localStorage.removeItem("eira:rt")
    },
  },
})
