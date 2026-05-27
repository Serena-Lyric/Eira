import { mount } from "@vue/test-utils"
import { describe, it, expect } from "vitest"
import GlassButton from "../GlassButton.vue"

describe("GlassButton", () => {
  it("emits click", async () => {
    const w = mount(GlassButton, { slots: { default: "OK" } })
    await w.trigger("click")
    expect(w.emitted("click")).toBeTruthy()
    expect(w.text()).toContain("OK")
  })
})
