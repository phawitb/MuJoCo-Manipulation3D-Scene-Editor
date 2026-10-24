import type { PortableObject } from "./types";

export async function readResponse(response: Response) {
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    throw Error(
      typeof detail === "string"
        ? detail
        : `Request failed (${response.status}). Check the local server and try again.`,
    );
  }
  if (!data) throw Error("The server returned an empty response");
  return data;
}

export async function addToGym(sessionId: string, object: PortableObject) {
  if (!sessionId) throw Error("Choose a Gym session first");
  const endpoint = `/api/sessions/${encodeURIComponent(sessionId)}`;
  const current = await readResponse(await fetch(endpoint));
  if (current.running)
    throw Error("Pause the selected Gym simulation before adding an object");
  let lowest = Infinity;
  for (let i = 2; i < object.mesh.vertices.length; i += 3)
    lowest = Math.min(lowest, object.mesh.vertices[i]);
  const placed = {
    ...object,
    id: `image_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`,
    position: [
      object.position[0],
      object.position[1],
      current.scene.table.height + 0.002 - lowest,
    ],
  };
  return readResponse(
    await fetch(`${endpoint}/command`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        type: "object_add",
        object: placed,
        revision: current.revision,
      }),
    }),
  );
}
