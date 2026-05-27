import { mount } from "@vue/test-utils"
import { describe, it, expect } from "vitest"
import Dashboard from "../src/pages/Dashboard.vue"

describe("Dashboard page", () => {
  it("renders placeholder", () => {
    const w = mount(Dashboard)
    expect(w.text()).toContain("Admin Dashboard placeholder")
  })
})
