<script setup lang="ts">
import { ref } from "vue"
import { useRouter } from "vue-router"
import { GlassButton, GlassInput, GlassCard } from "@eira/ui-shared"
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
    <GlassCard>
      <input type="email" v-model="email" placeholder="邮箱" />
      <input type="password" v-model="password" placeholder="密码" />
      <GlassButton variant="primary" @click="submit">登录</GlassButton>
      <p v-if="err" class="err">{{ err }}</p>
    </GlassCard>
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
}
.brand {
  font-size: 2.5rem;
  color: var(--eira-text-primary);
}
.err {
  color: #e44;
  margin-top: 8px;
  font-size: 0.9rem;
}
</style>
