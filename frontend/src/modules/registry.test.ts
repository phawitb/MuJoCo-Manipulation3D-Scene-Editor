import { describe, expect, it } from "vitest";
import { enabledModules, selectedModule } from "./registry";
describe("independent studio tabs", () => {
  it("enables all by default", () =>
    expect(enabledModules()).toEqual(["gym", "connection", "blender"]));
  it("allows a standalone module and removes unknown/duplicates", () =>
    expect(enabledModules("blender,unknown,blender")).toEqual(["blender"]));
  it("falls back from unavailable saved tab", () =>
    expect(selectedModule("gym", ["connection"])).toBe("connection"));
  it("rejects an empty deployment instead of silently enabling hardware", () =>
    expect(() => enabledModules("missing")).toThrow());
});
