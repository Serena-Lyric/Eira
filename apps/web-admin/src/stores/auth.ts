import { defineStore } from "pinia"
import { authApi } from "../services/api"
import type { UserInfo } from "../services/types"

export const useAuthStore = defineStore("auth", {
  state: () => ({
    accessToken: localStorage.getItem("eira:admin:at") || "",
    refreshToken: localStorage.getItem("eira:admin:rt") || "",
    user: null as UserInfo | null,
  }),
  actions: {
    async login(email: string, password: string) {
      const result = await authApi.login({ email, password })
      this.accessToken = result.access_token
      this.refreshToken = result.refresh_token
      localStorage.setItem("eira:admin:at", this.accessToken)
      localStorage.setItem("eira:admin:rt", this.refreshToken)
      // Fetch user profile after successful login
      await this.fetchUser()
    },

    async fetchUser() {
      try {
        this.user = await authApi.getMe()
      } catch {
        // If getMe fails, we're still logged in (tokens are set)
        this.user = null
      }
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
