import { mount } from "@vue/test-utils"
import { describe, it, expect } from "vitest"
import Login from "../src/pages/Login.vue"

describe("Login page", () => {
  it("renders email and password fields", () => {
    const w = mount(Login)
    expect(w.find('input[type="email"]').exists()).toBe(true)
    expect(w.find('input[type="password"]').exists()).toBe(true)
  })
})
