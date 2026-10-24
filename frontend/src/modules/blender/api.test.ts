import { afterEach, expect, it, vi } from "vitest";
import { addToGym, readResponse } from "./api";
import type { PortableObject } from "./types";

afterEach(() => vi.unstubAllGlobals());
const object = {
  id: "image_test",
  name: "Object",
  position: [0.06, 0, 0.802],
  mesh: {
    vertices: [-0.05, -0.01, -0.05, 0.05, 0.01, 0.05],
    faces: [0, 1, 0],
    filename: "object.glb",
  },
} as PortableObject;

it("adds only to the chosen session, using its revision and table height", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          revision: 12,
          running: false,
          scene: { table: { height: 0.9 } },
        }),
      ),
    )
    .mockResolvedValueOnce(new Response(JSON.stringify({ revision: 13 })));
  vi.stubGlobal("fetch", fetcher);
  await addToGym("chosen-session", object);
  expect(fetcher.mock.calls[0][0]).toBe("/api/sessions/chosen-session");
  expect(fetcher.mock.calls[1][0]).toBe("/api/sessions/chosen-session/command");
  const command = JSON.parse(fetcher.mock.calls[1][1].body);
  expect(command.revision).toBe(12);
  expect(command.type).toBe("object_add");
  expect(command.object.position[2]).toBeCloseTo(0.952);
  expect(command.object.id).not.toBe(object.id);
  expect(object.position[2]).toBe(0.802);
});

it("requires an explicit session and does not stop a running Gym", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(new Response(JSON.stringify({ running: true })));
  vi.stubGlobal("fetch", fetcher);
  await expect(addToGym("", object)).rejects.toThrow("Choose");
  expect(fetcher).not.toHaveBeenCalled();
  await expect(addToGym("chosen", object)).rejects.toThrow("Pause");
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it("shows server validation errors and stale revisions without silent retry", async () => {
  await expect(
    readResponse(
      new Response(JSON.stringify({ detail: "Stale scene revision" }), {
        status: 409,
      }),
    ),
  ).rejects.toThrow("Stale scene revision");
  await expect(
    readResponse(new Response("<html>offline</html>", { status: 502 })),
  ).rejects.toThrow("502");
});
