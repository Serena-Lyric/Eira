import { defineStore } from "pinia"
import axios from "axios"

export const useAuthStore = defineStore("auth", {
  state: () => ({
    accessToken: localStorage.getItem("eira:admin:at") || "",
    refreshToken: localStorage.getItem("eira:admin:rt") || "",
    user: null as null | { id: number; email: string; role: string },
  }),
  actions: {
    async login(email: string, password: string) {
      const r = await axios.post("/api/auth/login", { email, password })
      this.accessToken = r.data.access_token
      this.refreshToken = r.data.refresh_token
      localStorage.setItem("eira:admin:at", this.accessToken)
      localStorage.setItem("eira:admin:rt", this.refreshToken)
    },
    logout() {
      this.accessToken = ""
      this.refreshToken = ""
      this.user = null
      localStorage.removeItem("eira:admin:at")
      localStorage.removeItem("eira:admin:rt")
    },
  },
})
