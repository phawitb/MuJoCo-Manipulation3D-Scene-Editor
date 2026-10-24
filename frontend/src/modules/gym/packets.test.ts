import { expect, it } from "vitest";
import {
  mergePacket,
  visiblePacket,
  persistedJoints,
  type PacketCache,
} from "./packets";
import type { Snapshot, StatePacket } from "./types";
const empty: PacketCache = {
  snapshot: null,
  latest: null,
  revision: undefined,
};
const packet = (
  sequence: number,
  revision: number,
  type: "snapshot" | "state" = "snapshot",
  sessionId = "one",
) => ({ type, sequence, revision, sessionId }) as Snapshot | StatePacket;

it("keeps a late structural snapshot and the newer poses independently", () => {
  let cache = mergePacket(empty, packet(1, 1));
  cache = mergePacket(cache, packet(5, 2, "state"));
  cache = mergePacket(cache, packet(3, 2));
  expect(cache.snapshot?.revision).toBe(2);
  expect(visiblePacket(cache)?.sequence).toBe(5);
});

it("does not render newer revision poses against old geometry", () => {
  let cache = mergePacket(empty, packet(1, 1));
  cache = mergePacket(cache, packet(5, 2, "state"));
  expect(visiblePacket(cache)?.revision).toBe(1);
  expect(cache.latest?.sequence).toBe(5);
});

it("stale packets cannot regress the revision sent with the next edit", () => {
  let cache = mergePacket(empty, packet(10, 3));
  cache = mergePacket(cache, packet(9, 2));
  expect(cache.revision).toBe(3);
  expect(cache.snapshot?.sequence).toBe(10);
});

it("a new session resets its sequence and revision without retaining old geometry", () => {
  let cache = mergePacket(empty, packet(100, 9));
  cache = mergePacket(cache, packet(0, 1, "state", "two"));
  expect(cache.revision).toBe(1);
  expect(cache.snapshot).toBeNull();
  expect(visiblePacket(cache)).toBeNull();
});

it("persists measured joints while bounding compliant limit overshoot", () => {
  const measured = [0.42, 1.745355215093783, -0.17454];
  const limits = [
    { name: "arm", min: -2, max: 2 },
    { name: "upper", min: -0.174533, max: 1.7453292 },
    { name: "lower", min: -0.174533, max: 1.7453292 },
  ];
  expect(persistedJoints(measured, limits)).toEqual([
    0.42, 1.7453292, -0.174533,
  ]);
  expect(measured).toEqual([0.42, 1.745355215093783, -0.17454]);
});
