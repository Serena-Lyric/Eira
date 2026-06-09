import { createApp } from "vue"
import { createPinia } from "pinia"
import { createRouter, createWebHistory } from "vue-router"
import App from "./App.vue"
import Login from "./pages/Login.vue"

import "@eira/ui-shared"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: Login },
    {
      path: "/",
      component: () => import("./layouts/AdminLayout.vue"),
      meta: { requiresAuth: true },
      children: [
        { path: "", redirect: "dashboard" },
        { path: "dashboard", component: () => import("./pages/Dashboard.vue") },
      ]
    }
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem("eira:admin:at")
  if (to.meta.requiresAuth && !token && to.path !== "/login") return "/login"
})

createApp(App).use(createPinia()).use(router).mount("#app")
