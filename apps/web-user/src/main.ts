import { createApp } from "vue"
import { createPinia } from "pinia"
import { createRouter, createWebHistory } from "vue-router"
import App from "./App.vue"
import Login from "./pages/Login.vue"
import { useAuthStore } from "./stores/auth"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: Login },
    {
      path: "/chat",
      component: () => import("./pages/Chat.vue"),
      meta: { requiresAuth: true },
    },
    { path: "/", redirect: "/chat" },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.accessToken) return "/login"
})

createApp(App).use(createPinia()).use(router).mount("#app")
