import { mount } from "@vue/test-utils"
import { describe, it, expect, vi } from "vitest"
import { createPinia } from "pinia"
import Login from "../src/pages/Login.vue"

vi.mock("vue-router", () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

describe("Login page", () => {
  it("renders email and password fields", () => {
    const w = mount(Login, {
      global: { plugins: [createPinia()] },
    })
    expect(w.find('input[type="email"]').exists()).toBe(true)
    expect(w.find('input[type="password"]').exists()).toBe(true)
  })
})
