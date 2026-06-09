import axios from "axios"
import { useAuthStore } from "../stores/auth"

export const http = axios.create({ baseURL: "/api" })

// Track refresh state to avoid concurrent refresh calls
let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (err: unknown) => void
}> = []

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error)
    } else {
      resolve(token!)
    }
  })
  failedQueue = []
}

// Request interceptor: attach access token
http.interceptors.request.use((cfg) => {
  const t = useAuthStore().accessToken
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})

// Response interceptor: auto-refresh on 401
http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // Only attempt refresh on 401 and if we haven't already retried
    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error)
    }

    // Don't try to refresh the refresh endpoint itself
    if (originalRequest.url === "/auth/refresh") {
      const auth = useAuthStore()
      auth.logout()
      window.location.href = "/login"
      return Promise.reject(error)
    }

    const auth = useAuthStore()
    const refreshToken = auth.refreshToken

    if (!refreshToken) {
      auth.logout()
      window.location.href = "/login"
      return Promise.reject(error)
    }

    if (isRefreshing) {
      // Queue this request until refresh completes
      return new Promise<string>((resolve, reject) => {
        failedQueue.push({ resolve, reject })
      }).then((token) => {
        originalRequest.headers.Authorization = `Bearer ${token}`
        return http(originalRequest)
      })
    }

    isRefreshing = true
    originalRequest._retry = true

    try {
      const { data } = await axios.post("/api/auth/refresh", {
        refresh_token: refreshToken,
      })
      auth.accessToken = data.access_token
      auth.refreshToken = data.refresh_token
      localStorage.setItem("eira:admin:at", data.access_token)
      localStorage.setItem("eira:admin:rt", data.refresh_token)

      processQueue(null, data.access_token)

      originalRequest.headers.Authorization = `Bearer ${data.access_token}`
      return http(originalRequest)
    } catch (refreshError) {
      processQueue(refreshError, null)
      auth.logout()
      window.location.href = "/login"
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  },
)
