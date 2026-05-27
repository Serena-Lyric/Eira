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
      children: [
        { path: "", redirect: "dashboard" },
        { path: "dashboard", component: () => import("./pages/Dashboard.vue") },
        { path: "content/personas", component: () => import("./pages/Content/Personas.vue") },
        { path: "content/knowledge", component: () => import("./pages/Content/Knowledge.vue") },
        { path: "content/live2d", component: () => import("./pages/Content/Live2D.vue") },
      ]
    }
  ],
})

// Temporarily commented for UI testing
// router.beforeEach((to) => {
//   const token = localStorage.getItem('eira_access_token');
//   if (to.meta.requiresAuth && !token) return "/login"
// })

createApp(App).use(createPinia()).use(router).mount("#app")
