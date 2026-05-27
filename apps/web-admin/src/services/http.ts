import axios from "axios"
import { useAuthStore } from "../stores/auth"

export const http = axios.create({ baseURL: "/api" })
http.interceptors.request.use((cfg) => {
  const t = useAuthStore().accessToken
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})
