import { afterEach, describe, expect, it, vi } from "vitest";
import { readPedestalHeight, rememberPedestalHeight } from "./robotPreferences";

afterEach(() => vi.unstubAllGlobals());
describe("base lift preference", () => {
  it("remembers metres and rejects invalid saved values", () => {
    let stored: string | null = null;
    vi.stubGlobal("localStorage", {
      getItem: () => stored,
      setItem: (_key: string, value: string) => {
        stored = value;
      },
    });
    expect(readPedestalHeight()).toBeNull();
    rememberPedestalHeight(0.0222);
    expect(readPedestalHeight()).toBe(0.0222);
    for (const value of ["-1", "0.21", '"0.02"', "{}", "invalid"]) {
      stored = value;
      expect(readPedestalHeight()).toBeNull();
    }
  });
});
