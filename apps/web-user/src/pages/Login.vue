<script setup lang="ts">
import { ref } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "../stores/auth"

const email = ref("")
const password = ref("")
const err = ref("")
const auth = useAuthStore()
const router = useRouter()

async function submit() {
  try {
    await auth.login(email.value, password.value)
    router.push("/chat")
  } catch (e: any) {
    err.value = "登录失败，请检查账号密码"
  }
}
</script>
<template>
  <div class="login-shell">
    <h1 class="brand">Eira</h1>
    <div class="glass-card">
      <input class="glass-input" type="email" v-model="email" placeholder="邮箱" />
      <input class="glass-input" type="password" v-model="password" placeholder="密码" />
      <button class="glass-btn glass-btn-primary" @click="submit">登录</button>
      <p v-if="err" class="err">{{ err }}</p>
    </div>
  </div>
</template>
<style scoped>
.login-shell {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  gap: 24px;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
  font-family: 'PingFang SC', system-ui, sans-serif;
}
.brand {
  font-size: 2.5rem;
  color: #fff;
  font-weight: 700;
  letter-spacing: 0.05em;
}
.glass-card {
  width: 100%;
  max-width: 380px;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 24px;
  padding: 32px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
}
.glass-input {
  width: 100%;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  color: #fff;
  font-size: 15px;
  outline: none;
  transition: border 0.2s;
  box-sizing: border-box;
  font-family: inherit;
}
.glass-input::placeholder {
  color: rgba(255, 255, 255, 0.35);
}
.glass-input:focus {
  border-color: rgba(91, 146, 255, 0.5);
}
.glass-btn {
  padding: 14px 24px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}
.glass-btn-primary {
  background: linear-gradient(135deg, #5B92FF, #3867ED);
  border: none;
}
.glass-btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}
.glass-btn:active {
  transform: translateY(0);
}
.err {
  color: #e44;
  margin-top: 4px;
  font-size: 0.9rem;
  text-align: center;
}
</style>
