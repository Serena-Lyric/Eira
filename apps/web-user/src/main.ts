import { createApp } from "vue"
import { createPinia } from "pinia"
import { createRouter, createWebHistory } from "vue-router"
import App from "./App.vue"
import Login from "./pages/Login.vue"

// Global UI Tokens
import "@eira/ui-shared"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: Login },
    {
      path: "/chat",
      component: () => import("./pages/Chat.vue"),
      // meta: { requiresAuth: true }, // Temporarily disabled for UI testing
    },
    { path: "/", redirect: "/chat" },
  ],
})

// router.beforeEach((to) => {
//   const token = localStorage.getItem('eira_access_token');
//   if (to.meta.requiresAuth && !token) return "/login"
// })

createApp(App).use(createPinia()).use(router).mount("#app")
