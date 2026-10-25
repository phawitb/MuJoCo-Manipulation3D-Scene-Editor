import { expect, test, vi } from "vitest";
import { LatestTarget } from "./latestTarget";

test("bursts replace unsent targets and never overlap requests", async () => {
  vi.useFakeTimers();
  let finish!: () => void;
  const send = vi.fn(
    () =>
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
  );
  const queue = new LatestTarget(send, vi.fn());
  queue.push([1]);
  queue.push([2]);
  await vi.advanceTimersByTimeAsync(35);
  expect(send).toHaveBeenCalledExactlyOnceWith([2]);
  queue.push([3]);
  queue.push([4]);
  await vi.advanceTimersByTimeAsync(100);
  expect(send).toHaveBeenCalledTimes(1);
  finish();
  await vi.advanceTimersByTimeAsync(35);
  expect(send).toHaveBeenLastCalledWith([4]);
  finish();
  await queue.cancel();
  queue.dispose();
  vi.useRealTimers();
});

test("cancel drains active request and drops all future queued commands", async () => {
  vi.useFakeTimers();
  const send = vi.fn(async () => {});
  const queue = new LatestTarget(send, vi.fn());
  queue.push([1]);
  await queue.cancel();
  await vi.advanceTimersByTimeAsync(100);
  expect(send).not.toHaveBeenCalled();
  queue.dispose();
  queue.push([2]);
  await vi.advanceTimersByTimeAsync(100);
  expect(send).not.toHaveBeenCalled();
  vi.useRealTimers();
});

test("cancel clears pending immediately even when an accepted request has no response", async () => {
  vi.useFakeTimers();
  let finish!: () => void;
  const send = vi.fn(
    () =>
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
  );
  const queue = new LatestTarget(send, vi.fn());
  queue.push([1]);
  await vi.advanceTimersByTimeAsync(35);
  queue.push([2]);
  const draining = queue.cancel(); // Stop/Torque off intentionally do not await this.
  await vi.advanceTimersByTimeAsync(100);
  expect(send).toHaveBeenCalledTimes(1);
  finish();
  await draining;
  await vi.advanceTimersByTimeAsync(100);
  expect(send).toHaveBeenCalledTimes(1);
  queue.dispose();
  vi.useRealTimers();
});
