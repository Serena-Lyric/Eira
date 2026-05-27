import axios from 'axios';

export function useHttp() {
  const baseUrl = typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL
    ? import.meta.env.VITE_API_BASE_URL
    : '/api/v1';

  const api = axios.create({
    baseURL: baseUrl,
    timeout: 15000,
  });

  // Request interceptor to inject JWT
  api.interceptors.request.use((config) => {
    const token = localStorage.getItem('eira_access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  // Response interceptor for token refresh (placeholder logic)
  api.interceptors.response.use(
    (response) => response,
    async (error) => {
      // Add refresh token logic here
      return Promise.reject(error);
    }
  );

  return { api };
}
