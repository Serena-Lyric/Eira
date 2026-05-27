import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('eira_access_token'));
  const user = ref<any | null>(null);

  function setToken(newToken: string) {
    token.value = newToken;
    localStorage.setItem('eira_access_token', newToken);
  }

  function clearAuth() {
    token.value = null;
    user.value = null;
    localStorage.removeItem('eira_access_token');
  }

  return {
    token,
    user,
    setToken,
    clearAuth
  };
});
